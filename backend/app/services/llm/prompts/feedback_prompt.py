"""
Prompt builder for the FeedbackAgent.
"""

from typing import Any

from app.schemas.assessment import AssessmentStructuredOutput

SYSTEM_FEEDBACK_PROMPT = """You are an encouraging, insightful, and pedagogical University Academic Tutor and Mentor.
Your goal is to turn assessment scores into actionable, personalized learning guidance for the student.

Directives:
1. Growth Mindset: Frame feedback constructively. Celebrate demonstrated competence while clearly explaining how to fix errors and gaps.
2. Specificity: Directly reference the student's concept mastery gaps and rubric deficiencies. Avoid vague platitudes like "study harder".
3. Actionable Next Steps: Provide concrete exercises, readings, or problem-solving approaches the student can immediately implement.
4. Curated Revision Topics: Suggest specific academic topics or chapters that need reinforcement.
5. JSON Strictness: Output valid JSON strictly conforming to FeedbackStructuredOutput.
"""


def build_feedback_prompts(
    assignment_title: str,
    assessment: AssessmentStructuredOutput,
    total_max_marks: float,
    retrieved_chunks: list[dict[str, Any]],
) -> tuple[str, str]:
    """
    Constructs (system_prompt, user_prompt) for the FeedbackAgent.
    """
    user_parts: list[str] = [
        f"### Assignment: {assignment_title}",
        f"Overall Score: {assessment.ai_score} / {total_max_marks}",
        f"General Remarks: {assessment.general_remarks}",
        "\n### Strengths Identified:",
    ]
    for s in assessment.strengths:
        user_parts.append(f"- {s}")

    user_parts.append("\n### Weaknesses & Areas for Growth:")
    for w in assessment.weaknesses:
        user_parts.append(f"- {w}")

    user_parts.append("\n### Rubric Criteria Performance:")
    for c in assessment.criteria_scores:
        user_parts.append(f"- {c.criterion}: {c.score} / {c.max_marks} (Reasoning: {c.reasoning})")

    user_parts.append("\n### Concept Mastery Breakdown:")
    for cm in assessment.concept_mastery:
        user_parts.append(
            f"- {cm.concept}: {cm.mastery_level.value} (Evidence: {cm.evidence})"
        )

    if retrieved_chunks:
        user_parts.append("\n### Referenced Course Material Sources:")
        sources = {
            chunk.get("metadata", {}).get("source_filename")
            for chunk in retrieved_chunks
            if chunk.get("metadata", {}).get("source_filename")
        }
        for src in sources:
            user_parts.append(f"- Document: {src}")

    user_parts.append(
        "\nGenerate comprehensive, encouraging, and actionable personalized feedback now matching FeedbackStructuredOutput."
    )

    return SYSTEM_FEEDBACK_PROMPT, "\n".join(user_parts)
