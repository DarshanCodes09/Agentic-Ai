"""
Assessment service: orchestrates evaluation, approval, modification, and access authorization.
"""

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    AppException,
    InsufficientPermissionsError,
    ResourceNotFoundError,
)
from app.models.assessment import AssessmentFeedback, AssessmentResult, AssessmentStatus
from app.models.assignment import Assignment
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User, UserRole
from app.services.assessment.assessment_agent import get_assessment_agent
from app.services.assessment.feedback_agent import get_feedback_agent
from app.services.assessment.preparation_service import get_assessment_preparation_service
from app.services.llm.client import get_llm_service

logger = logging.getLogger(__name__)


async def assess_submission(
    db: Session,
    submission_id: int,
    current_faculty: User,
    force_reassess: bool = False,
) -> AssessmentResult:
    """
    Execute AI evaluation for a student submission.
    Accessible only by the faculty member owning the subject.
    """
    if current_faculty.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()

    # Load submission with assignment and subject
    stmt = (
        select(Submission)
        .options(
            selectinload(Submission.assignment).selectinload(Assignment.subject),
            selectinload(Submission.assessment).selectinload(AssessmentResult.feedback),
        )
        .where(Submission.id == submission_id)
    )
    submission = db.scalar(stmt)
    if not submission:
        raise ResourceNotFoundError(f"Submission with ID {submission_id} not found.")

    assignment = submission.assignment
    if not assignment or assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError("Only the faculty teaching this course can trigger assessment.")

    # Check if already assessed
    existing_assessment = submission.assessment
    if existing_assessment and not force_reassess:
        return existing_assessment

    # 1. Prepare assessment context (Submission text, rubric, questions, RAG chunks)
    prep_service = get_assessment_preparation_service()
    context = prep_service.prepare_context(db, submission_id)

    # 2. Run Assessment Agent
    assessment_agent = get_assessment_agent()
    eval_output = await assessment_agent.evaluate(context)

    # 3. Run Feedback Agent
    feedback_agent = get_feedback_agent()
    feedback_output = await feedback_agent.generate_feedback(context, eval_output)

    # 4. Persist AssessmentResult and AssessmentFeedback
    model_name = get_llm_service().provider_name

    criteria_data = [c.model_dump() for c in eval_output.criteria_scores]
    concept_data = [cm.model_dump() for cm in eval_output.concept_mastery]

    if existing_assessment:
        existing_assessment.ai_score = eval_output.ai_score
        existing_assessment.final_score = eval_output.ai_score
        existing_assessment.max_score = context.total_max_marks
        existing_assessment.criteria_scores = criteria_data
        existing_assessment.concept_mastery = concept_data
        existing_assessment.retrieved_context = context.retrieved_chunks
        existing_assessment.strengths = eval_output.strengths
        existing_assessment.weaknesses = eval_output.weaknesses
        existing_assessment.status = AssessmentStatus.COMPLETED
        existing_assessment.model_name = model_name

        if existing_assessment.feedback:
            existing_assessment.feedback.summary = feedback_output.summary
            existing_assessment.feedback.detailed_feedback = feedback_output.detailed_feedback
            existing_assessment.feedback.actionable_steps = feedback_output.actionable_steps
            existing_assessment.feedback.suggested_topics = feedback_output.suggested_topics
        else:
            fb = AssessmentFeedback(
                assessment_id=existing_assessment.id,
                summary=feedback_output.summary,
                detailed_feedback=feedback_output.detailed_feedback,
                actionable_steps=feedback_output.actionable_steps,
                suggested_topics=feedback_output.suggested_topics,
            )
            db.add(fb)

        assessment_record = existing_assessment
    else:
        assessment_record = AssessmentResult(
            submission_id=submission_id,
            ai_score=eval_output.ai_score,
            final_score=eval_output.ai_score,
            max_score=context.total_max_marks,
            status=AssessmentStatus.COMPLETED,
            criteria_scores=criteria_data,
            concept_mastery=concept_data,
            retrieved_context=context.retrieved_chunks,
            strengths=eval_output.strengths,
            weaknesses=eval_output.weaknesses,
            model_name=model_name,
        )
        db.add(assessment_record)
        db.flush()

        feedback_record = AssessmentFeedback(
            assessment_id=assessment_record.id,
            summary=feedback_output.summary,
            detailed_feedback=feedback_output.detailed_feedback,
            actionable_steps=feedback_output.actionable_steps,
            suggested_topics=feedback_output.suggested_topics,
        )
        db.add(feedback_record)

    submission.status = SubmissionStatus.UNDER_REVIEW
    db.commit()
    db.refresh(assessment_record)
    return assessment_record


def get_assessment_by_submission(
    db: Session,
    submission_id: int,
    current_user: User,
) -> AssessmentResult:
    """
    Retrieve assessment for a submission.
    Faculty can view anytime.
    Student can view if it's their submission and status is ready (COMPLETED, APPROVED, MODIFIED).
    """
    stmt = (
        select(Submission)
        .options(
            selectinload(Submission.assignment).selectinload(Assignment.subject),
            selectinload(Submission.assessment).selectinload(AssessmentResult.feedback),
        )
        .where(Submission.id == submission_id)
    )
    submission = db.scalar(stmt)
    if not submission:
        raise ResourceNotFoundError(f"Submission with ID {submission_id} not found.")

    if not submission.assessment:
        raise ResourceNotFoundError("No assessment has been generated for this submission yet.")

    # Authorization
    if current_user.role == UserRole.FACULTY:
        if submission.assignment.subject.faculty_id != current_user.id:
            raise InsufficientPermissionsError()
    elif current_user.role == UserRole.STUDENT:
        if submission.student_id != current_user.id:
            raise InsufficientPermissionsError()
        # Student cannot view unfinished/failed states
        if submission.assessment.status in [AssessmentStatus.PENDING, AssessmentStatus.PROCESSING, AssessmentStatus.FAILED]:
            raise AppException(
                detail="Assessment is not yet available for viewing.",
                status_code=400,
            )
    else:
        raise InsufficientPermissionsError()

    return submission.assessment


def approve_assessment(
    db: Session,
    assessment_id: int,
    current_faculty: User,
    faculty_notes: str | None = None,
) -> AssessmentResult:
    """
    Approve an AI assessment as the course instructor.
    Transitions status to APPROVED and submission status to EVALUATED.
    """
    if current_faculty.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()

    stmt = (
        select(AssessmentResult)
        .options(
            selectinload(AssessmentResult.submission)
            .selectinload(Submission.assignment)
            .selectinload(Assignment.subject),
            selectinload(AssessmentResult.feedback),
        )
        .where(AssessmentResult.id == assessment_id)
    )
    assessment = db.scalar(stmt)
    if not assessment:
        raise ResourceNotFoundError(f"Assessment with ID {assessment_id} not found.")

    if assessment.submission.assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    assessment.status = AssessmentStatus.APPROVED
    if faculty_notes is not None:
        assessment.faculty_notes = faculty_notes

    assessment.submission.status = SubmissionStatus.EVALUATED
    db.commit()
    db.refresh(assessment)
    return assessment


def modify_assessment(
    db: Session,
    assessment_id: int,
    current_faculty: User,
    final_score: float,
    faculty_notes: str | None = None,
) -> AssessmentResult:
    """
    Modify or override final score of an assessment.
    Transitions status to MODIFIED and submission status to EVALUATED.
    """
    if current_faculty.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()

    stmt = (
        select(AssessmentResult)
        .options(
            selectinload(AssessmentResult.submission)
            .selectinload(Submission.assignment)
            .selectinload(Assignment.subject),
            selectinload(AssessmentResult.feedback),
        )
        .where(AssessmentResult.id == assessment_id)
    )
    assessment = db.scalar(stmt)
    if not assessment:
        raise ResourceNotFoundError(f"Assessment with ID {assessment_id} not found.")

    if assessment.submission.assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    if final_score < 0.0 or final_score > assessment.max_score:
        raise AppException(
            detail=f"Final score must be between 0.0 and {assessment.max_score}.",
            status_code=422,
        )

    assessment.final_score = round(final_score, 2)
    assessment.status = AssessmentStatus.MODIFIED
    if faculty_notes is not None:
        assessment.faculty_notes = faculty_notes

    assessment.submission.status = SubmissionStatus.EVALUATED
    db.commit()
    db.refresh(assessment)
    return assessment
