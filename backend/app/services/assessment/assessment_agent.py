"""
AssessmentAgent: Evaluates student submission against rubric criteria, questions, and RAG context.
"""

import logging
from app.schemas.assessment import AssessmentStructuredOutput
from app.services.assessment.preparation_service import AssessmentContext
from app.services.llm.client import LLMService, get_llm_service
from app.services.llm.prompts.assessment_prompt import build_assessment_prompts

logger = logging.getLogger(__name__)


class AssessmentAgent:
    """Agent responsible for rigorous rubric-based grading and concept mastery evaluation."""

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or get_llm_service()

    async def evaluate(self, context: AssessmentContext) -> AssessmentStructuredOutput:
        """
        Execute LLM evaluation for the provided assessment context.
        Validates, clamps, and aligns scores within legal rubric bounds.
        """
        system_prompt, user_prompt = build_assessment_prompts(
            assignment_title=context.assignment_title,
            assignment_description=context.assignment_description,
            total_max_marks=context.total_max_marks,
            questions=context.questions,
            rubric_items=context.rubric_items,
            retrieved_chunks=context.retrieved_chunks,
            submission_text=context.submission_text,
        )

        result: AssessmentStructuredOutput = await self.llm_service.generate_structured(
            prompt=user_prompt,
            response_model=AssessmentStructuredOutput,
            system_prompt=system_prompt,
        )

        # Post-validation and score bounding safeguards
        validated_result = self._validate_and_bound_scores(result, context)
        return validated_result

    def _validate_and_bound_scores(
        self, result: AssessmentStructuredOutput, context: AssessmentContext
    ) -> AssessmentStructuredOutput:
        """Ensure scores do not exceed maximum bounds and match rubric item IDs."""
        rubric_map = {item["criterion"].lower(): item for item in context.rubric_items}

        bounded_criteria = []
        for crit in result.criteria_scores:
            matched_item = rubric_map.get(crit.criterion.lower())
            item_id = matched_item["id"] if matched_item else crit.rubric_item_id
            crit_max = matched_item["max_marks"] if matched_item else crit.max_marks

            # Clamp criterion score between 0.0 and crit_max
            clamped_score = max(0.0, min(float(crit.score), float(crit_max)))
            crit.rubric_item_id = item_id
            crit.score = round(clamped_score, 2)
            crit.max_marks = float(crit_max)
            bounded_criteria.append(crit)

        # Total score validation
        if bounded_criteria:
            summed_score = sum(c.score for c in bounded_criteria)
            final_ai_score = min(summed_score, context.total_max_marks)
        else:
            final_ai_score = max(0.0, min(result.ai_score, context.total_max_marks))

        result.ai_score = round(final_ai_score, 2)
        result.criteria_scores = bounded_criteria
        return result


_assessment_agent_instance: AssessmentAgent | None = None


def get_assessment_agent() -> AssessmentAgent:
    global _assessment_agent_instance
    if _assessment_agent_instance is None:
        _assessment_agent_instance = AssessmentAgent()
    return _assessment_agent_instance
