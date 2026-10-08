"""
LLM providers: Mock, OpenAI, and Gemini implementations.
"""

import json
import logging
import re
from typing import Any, TypeVar
import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.schemas.assessment import (
    AssessmentStructuredOutput,
    ConceptMasteryItem,
    ConceptMasteryLevel,
    CriterionEvaluation,
    FeedbackStructuredOutput,
)
from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock provider for automated testing and local execution.
    Does not require external network requests or API keys.
    """

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        return (
            "Assessment Evaluation Report:\n"
            "The submission demonstrates satisfactory understanding of the core topics. "
            "Evidence of conceptual understanding is present, though technical rigor could be deepened."
        )

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> T:
        if response_model == AssessmentStructuredOutput:
            return self._generate_mock_assessment(prompt)  # type: ignore[return-value]
        elif response_model == FeedbackStructuredOutput:
            return self._generate_mock_feedback(prompt)  # type: ignore[return-value]
        else:
            # Fallback for arbitrary Pydantic schema
            try:
                return response_model.model_validate({})
            except Exception:
                raise AppException(
                    detail=f"MockLLMProvider does not support schema {response_model.__name__}",
                    status_code=500,
                )

    def _generate_mock_assessment(self, prompt: str) -> AssessmentStructuredOutput:
        """Heuristically analyze prompt to provide realistic academic evaluation."""
        # Detect maximum marks from prompt if present
        max_marks_match = re.search(r"Total Assignment Max Marks:\s*([0-9]+(?:\.[0-9]+)?)", prompt)
        total_max_marks = float(max_marks_match.group(1)) if max_marks_match else 100.0

        # Detect whether the student's submission is very brief, missing, or trivial
        is_sparse = (
            "I do not know" in prompt
            or "IDK" in prompt
            or "[EMPTY SUBMISSION]" in prompt
        )


        # Extract criteria if mentioned in prompt
        # Rubric format in prompt: Criterion: <name> (Max Marks: <N>)
        criteria_matches = re.findall(
            r"Criterion:\s*([^\n\r]+?)\s*\(Max Marks:\s*([0-9]+(?:\.[0-9]+)?)\)",
            prompt,
        )

        criteria_evaluations: list[CriterionEvaluation] = []
        if criteria_matches:
            for criterion_name, max_m_str in criteria_matches:
                crit_max = float(max_m_str)
                score = 0.0 if is_sparse else round(crit_max * 0.85, 2)
                reasoning = (
                    f"Limited or absent explanation provided for '{criterion_name}'."
                    if is_sparse
                    else f"Clear and accurate articulation adhering to '{criterion_name}' standards."
                )
                criteria_evaluations.append(
                    CriterionEvaluation(
                        rubric_item_id=None,
                        criterion=criterion_name.strip(),
                        score=score,
                        max_marks=crit_max,
                        reasoning=reasoning,
                    )
                )
            calculated_score = sum(c.score for c in criteria_evaluations)
        else:
            calculated_score = 0.0 if is_sparse else round(total_max_marks * 0.82, 2)
            criteria_evaluations.append(
                CriterionEvaluation(
                    rubric_item_id=None,
                    criterion="Overall Academic Rigor & Accuracy",
                    score=calculated_score,
                    max_marks=total_max_marks,
                    reasoning="Evaluation based on comprehensive conceptual correctness and structure.",
                )
            )

        # Extract expected concepts if mentioned
        # Expected Concepts: [c1, c2] or bullet points
        concepts_match = re.findall(r"-\s*Concept:\s*([^\n\r]+)", prompt)
        if not concepts_match:
            concepts_match = ["Core Concepts", "Domain Methodology"]

        concept_masteries: list[ConceptMasteryItem] = []
        for c_name in concepts_match:
            c_name_clean = c_name.strip()
            level = (
                ConceptMasteryLevel.NEEDS_IMPROVEMENT
                if is_sparse
                else ConceptMasteryLevel.MASTERED
            )
            evidence = (
                f"Minimal mention or conceptual absence of '{c_name_clean}'."
                if is_sparse
                else f"Student correctly integrated and explained principles of '{c_name_clean}'."
            )
            concept_masteries.append(
                ConceptMasteryItem(
                    concept=c_name_clean,
                    mastery_level=level,
                    evidence=evidence,
                )
            )

        if is_sparse:
            strengths = ["Submission was delivered on time."]
            weaknesses = [
                "Lack of detailed academic explanations.",
                "Failed to address the core requirements outlined in the rubric.",
            ]
            remarks = "The submission lacks adequate detail to demonstrate mastery of the required concepts."
        else:
            strengths = [
                "Accurate theoretical definitions provided.",
                "Well-structured explanation aligned with rubric guidelines.",
                "Strong conceptual foundation evident throughout the response.",
            ]
            weaknesses = [
                "Could provide more comprehensive empirical examples.",
                "Depth of critical comparative analysis can be expanded.",
            ]
            remarks = "Commendable submission showcasing solid mastery of fundamental principles with minor gaps in edge-case analysis."

        return AssessmentStructuredOutput(
            ai_score=round(min(calculated_score, total_max_marks), 2),
            criteria_scores=criteria_evaluations,
            concept_mastery=concept_masteries,
            strengths=strengths,
            weaknesses=weaknesses,
            general_remarks=remarks,
        )

    def _generate_mock_feedback(self, prompt: str) -> FeedbackStructuredOutput:
        """Generate structured academic feedback matching student assessment."""
        is_sparse = "NEEDS_IMPROVEMENT" in prompt or "0.0" in prompt or "sparse" in prompt.lower()

        if is_sparse:
            summary = (
                "Your submission needs substantial improvement. Key topics were not adequately addressed, "
                "and several foundational concepts require immediate review."
            )
            detailed_feedback = (
                "Review the reference materials thoroughly. In your response, outline each question "
                "systematically and ensure you cover all criteria specified in the assignment rubric."
            )
            actionable_steps = [
                "Review the lecture notes and course textbook chapters for this module.",
                "Consult with faculty during office hours to clarify difficult concepts.",
                "Practice answering previous tutorial problems with step-by-step reasoning.",
            ]
            suggested_topics = [
                "Foundational Principles",
                "Application Methodologies",
            ]
        else:
            summary = (
                "Great job on this assignment! You demonstrated a strong grasp of the primary concepts "
                "and adhered closely to the grading rubric."
            )
            detailed_feedback = (
                "Your explanations were clear, logical, and supported by accurate terminology. "
                "To attain top marks on advanced exams, consider exploring practical tradeoffs "
                "and real-world edge cases in greater depth."
            )
            actionable_steps = [
                "Explore advanced case studies and real-world system applications.",
                "Refine technical citations and quantitative comparisons where applicable.",
            ]
            suggested_topics = [
                "Advanced System Architecture",
                "Optimization & Boundary Analysis",
            ]

        return FeedbackStructuredOutput(
            summary=summary,
            detailed_feedback=detailed_feedback,
            actionable_steps=actionable_steps,
            suggested_topics=suggested_topics,
        )


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI API Provider (via httpx)."""

    def __init__(self, api_key: str, model: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.api_url = "https://api.openai.com/v1/chat/completions"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.2),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.api_url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error("OpenAI API error: %s - %s", resp.status_code, resp.text)
                raise AppException(
                    detail=f"OpenAI API call failed: {resp.text}",
                    status_code=502,
                )
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> T:
        schema_json = json.dumps(response_model.model_json_schema())
        system_directive = (
            f"{system_prompt or ''}\n\n"
            f"You MUST return ONLY valid JSON matching this schema:\n{schema_json}"
        )
        messages = [
            {"role": "system", "content": system_directive},
            {"role": "user", "content": prompt},
        ]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.1),
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.api_url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error("OpenAI API error: %s - %s", resp.status_code, resp.text)
                raise AppException(
                    detail=f"OpenAI API call failed: {resp.text}",
                    status_code=502,
                )
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return response_model.model_validate(parsed)


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini API Provider (via httpx)."""

    def __init__(self, api_key: str, model: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.2),
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error("Gemini API error: %s - %s", resp.status_code, resp.text)
                raise AppException(
                    detail=f"Gemini API call failed: {resp.text}",
                    status_code=502,
                )
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> T:
        schema_json = json.dumps(response_model.model_json_schema())
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        instruction = (
            f"{system_prompt or ''}\n\n"
            f"You MUST return ONLY valid JSON matching this schema:\n{schema_json}"
        )
        contents = [
            {"role": "user", "parts": [{"text": instruction}]},
            {"role": "model", "parts": [{"text": "I will return only JSON matching the schema."}]},
            {"role": "user", "parts": [{"text": prompt}]},
        ]

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.1),
                "response_mime_type": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error("Gemini API error: %s - %s", resp.status_code, resp.text)
                raise AppException(
                    detail=f"Gemini API call failed: {resp.text}",
                    status_code=502,
                )
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            return response_model.model_validate(parsed)
