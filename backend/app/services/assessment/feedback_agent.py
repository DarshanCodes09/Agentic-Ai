"""
FeedbackAgent: Generates personalized academic feedback and actionable improvement steps.
"""

import logging
from app.schemas.assessment import AssessmentStructuredOutput, FeedbackStructuredOutput
from app.services.assessment.preparation_service import AssessmentContext
from app.services.llm.client import LLMService, get_llm_service
from app.services.llm.prompts.feedback_prompt import build_feedback_prompts

logger = logging.getLogger(__name__)


class FeedbackAgent:
    """Agent responsible for crafting pedagogically sound, actionable student feedback."""

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or get_llm_service()

    async def generate_feedback(
        self, context: AssessmentContext, assessment: AssessmentStructuredOutput
    ) -> FeedbackStructuredOutput:
        """Execute LLM generation of personalized feedback based on assessment results."""
        system_prompt, user_prompt = build_feedback_prompts(
            assignment_title=context.assignment_title,
            assessment=assessment,
            total_max_marks=context.total_max_marks,
            retrieved_chunks=context.retrieved_chunks,
        )

        feedback_result: FeedbackStructuredOutput = await self.llm_service.generate_structured(
            prompt=user_prompt,
            response_model=FeedbackStructuredOutput,
            system_prompt=system_prompt,
        )

        return feedback_result


_feedback_agent_instance: FeedbackAgent | None = None


def get_feedback_agent() -> FeedbackAgent:
    global _feedback_agent_instance
    if _feedback_agent_instance is None:
        _feedback_agent_instance = FeedbackAgent()
    return _feedback_agent_instance
