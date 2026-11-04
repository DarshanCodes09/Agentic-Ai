"""
LLM providers: Mock, OpenAI, and Gemini implementations.
"""

import json
import logging
import re
from typing import Any, TypeVar
import httpx
from pydantic import BaseModel
from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncGroq,
    AuthenticationError,
    BadRequestError,
    GroqError,
    RateLimitError,
)

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

    def __init__(self, enable_vision: bool = False) -> None:
        self.enable_vision = enable_vision

    @property
    def has_vision_capability(self) -> bool:
        return self.enable_vision

    async def analyze_image(
        self,
        image_path: str,
        prompt: str = "Analyze this academic plot, chart, or diagram and describe its axes, metrics, trends, and results.",
        **kwargs: Any,
    ) -> str | None:
        if not self.enable_vision:
            return None
        from pathlib import Path
        name = Path(image_path).name
        return (
            f"Vision inspection of '{name}': Visual analysis indicates experimental results plot. "
            f"Training and validation metrics show steady convergence over epochs, confirming model optimization."
        )

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
        if "[SIMULATE_413]" in prompt or "[SIMULATE_GROQ_413]" in prompt:
            raise AppException(
                detail="AI provider rejected request: Payload too large for model mock (HTTP 413: Request too large on tokens per minute (TPM)). Please reduce submission file size.",
                status_code=413,
            )
        if "[SIMULATE_CONTEXT_LENGTH]" in prompt:
            raise AppException(
                detail="AI model context-length exceeded for model mock (HTTP 413: context_length_exceeded: maximum context length is 8192 tokens). Please reduce submission file size.",
                status_code=413,
            )
        if response_model == AssessmentStructuredOutput:
            return self._generate_mock_assessment(prompt)  # type: ignore[return-value]
        elif response_model == FeedbackStructuredOutput:
            return self._generate_mock_feedback(prompt)  # type: ignore[return-value]
        elif response_model.__name__ == "ExtractedRubricResponse":
            return self._generate_mock_extracted_rubric(prompt)  # type: ignore[return-value]
        else:
            # Fallback for arbitrary Pydantic schema
            try:
                return response_model.model_validate({})
            except Exception:
                raise AppException(
                    detail=f"MockLLMProvider does not support schema {response_model.__name__}",
                    status_code=500,
                )

    def _generate_mock_extracted_rubric(self, prompt: str) -> Any:
        """Heuristically analyze document text in prompt to extract rubric criteria or detect lack of rubric."""
        from app.schemas.rubric import ExtractedRubricItem, ExtractedRubricResponse

        if "[SIMULATE_NO_RUBRIC]" in prompt:
            return ExtractedRubricResponse(
                has_rubric=False,
                rubric_name=None,
                total_marks=None,
                items=[],
                message="No explicit grading rubric was found in the document.",
            )

        lower = prompt.lower()
        rubric_keywords = ["rubric", "grading scheme", "marking scheme", "evaluation criteria", "marks:", "points:"]
        has_keywords = any(kw in lower for kw in rubric_keywords)

        if not has_keywords:
            return ExtractedRubricResponse(
                has_rubric=False,
                rubric_name=None,
                total_marks=None,
                items=[],
                message="No explicit grading rubric was found in the document. You can define rubric criteria manually.",
            )

        if "[SIMULATE_MISMATCH]" in prompt:
            return ExtractedRubricResponse(
                has_rubric=True,
                rubric_name="Extracted Marking Scheme",
                total_marks=120.0,
                items=[
                    ExtractedRubricItem(criterion="Part A: Design", description="System architecture", max_marks=70.0),
                    ExtractedRubricItem(criterion="Part B: Implementation", description="Core algorithms", max_marks=50.0),
                ],
                message="Extracted rubric contains 120.0 marks.",
            )

        pattern = re.compile(
            r"(?:[-*•]|\d+\.|\bCriterion:?)\s*([A-Za-z0-9\s&,/-]+?)\s*[-:]?\s*\(?(\d+(?:\.\d+)?)\s*(?:marks?|pts?|points?)\)?",
            re.IGNORECASE,
        )
        matches = pattern.findall(prompt)

        items: list[ExtractedRubricItem] = []
        seen = set()
        for name, marks_str in matches:
            clean_name = name.strip()
            if len(clean_name) < 3 or clean_name.lower() in seen:
                continue
            seen.add(clean_name.lower())
            items.append(
                ExtractedRubricItem(
                    criterion=clean_name,
                    description=f"Assessment of {clean_name} deliverables and implementation",
                    max_marks=float(marks_str),
                )
            )

        if not items:
            items = [
                ExtractedRubricItem(
                    criterion="Technical Implementation & Functionality",
                    description="Correctness of algorithms and problem requirements",
                    max_marks=60.0,
                ),
                ExtractedRubricItem(
                    criterion="Experimental Evaluation & Discussion",
                    description="Methodology, results analysis, and documentation",
                    max_marks=40.0,
                ),
            ]

        total = sum(item.max_marks for item in items)
        return ExtractedRubricResponse(
            has_rubric=True,
            rubric_name="Extracted Assignment Rubric",
            total_marks=total,
            items=items,
            assignment_summary="Extracted from assignment instruction document.",
            message=f"Successfully extracted {len(items)} criteria totaling {total} marks.",
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
        is_unexecuted_notebook = "Execution Audit: UNEXECUTED" in prompt
        is_errored_notebook = "Execution Audit: ERRORED" in prompt

        # Extract criteria if mentioned in prompt
        # Rubric format in prompt: Criterion: <name> (Max Marks: <N>)
        criteria_matches = re.findall(
            r"Criterion:\s*([^\n\r]+?)\s*\(Max Marks:\s*([0-9]+(?:\.[0-9]+)?)\)",
            prompt,
        )

        # Detect files and mappings from prompt
        discovered_files = re.findall(r"\[(?:Source File|CSV Data/Results|Notebook|Document Report|Visual Inspection):\s*([^\]\n]+)\]", prompt)
        clean_files = [f.split("(")[0].strip() for f in discovered_files if f.strip()]
        
        criterion_mapping_matches = re.findall(r"\*\s*Criterion '([^']+)':\s*Substantive Evidence in \[([^\]]+)\]", prompt)
        criterion_to_files = {c.strip().lower(): [f.strip() for f in fl.split(",")] for c, fl in criterion_mapping_matches}

        review_crit_matches = re.findall(r"\*\s*Criterion '([^']+)':\s*(.+)", prompt)
        review_crits = {c.strip().lower(): r.strip() for c, r in review_crit_matches}

        criteria_evaluations: list[CriterionEvaluation] = []
        if criteria_matches:
            for criterion_name, max_m_str in criteria_matches:
                crit_max = float(max_m_str)
                crit_lower = criterion_name.strip().lower()
                matched_files = criterion_to_files.get(crit_lower, [])
                ref_file = matched_files[0] if matched_files and not matched_files[0].startswith("(") else (clean_files[0] if clean_files else "submitted project files")

                # Check if criterion requires review due to unreadable / omitted files
                if crit_lower in review_crits and any(kw in review_crits[crit_lower].lower() for kw in ("unreadable", "omitted", "could not be parsed", "unsupported")):
                    score = round(crit_max * 0.55, 2)
                    reasoning = f"Work for '{criterion_name}' in {ref_file} cannot be fully verified due to file format or context limits ({review_crits[crit_lower]}); provisional partial credit awarded, flagged for faculty review."
                elif is_sparse or (matched_files and "(no directly matched files" in matched_files[0].lower() and not clean_files):
                    score = 0.0
                    reasoning = f"Work absent after adequate inspection across project files for '{criterion_name}'."
                elif is_unexecuted_notebook:
                    score = round(crit_max * 0.55, 2)
                    reasoning = f"Code implementation is present in {ref_file} for '{criterion_name}', but notebook cells lack saved execution outputs and execution counts."
                elif is_errored_notebook:
                    score = round(crit_max * 0.50, 2)
                    reasoning = f"Code implementation was attempted in {ref_file} for '{criterion_name}', but execution halted with runtime errors."
                else:
                    score = round(crit_max * 0.88, 2)
                    reasoning = f"Verified implementation and experimental outcomes in {ref_file}; methodology and deliverables adhere to '{criterion_name}' standards."

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
            if is_sparse:
                calculated_score = 0.0
            elif is_unexecuted_notebook:
                calculated_score = round(total_max_marks * 0.55, 2)
            elif is_errored_notebook:
                calculated_score = round(total_max_marks * 0.50, 2)
            else:
                calculated_score = round(total_max_marks * 0.82, 2)

            criteria_evaluations.append(
                CriterionEvaluation(
                    rubric_item_id=None,
                    criterion="Overall Academic Rigor & Accuracy",
                    score=calculated_score,
                    max_marks=total_max_marks,
                    reasoning="Evaluation based on comprehensive conceptual correctness, code implementation, and structure.",
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


class GroqLLMProvider(BaseLLMProvider):
    """
    Official Groq Python SDK provider for high-performance open-source LLM inference.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        timeout: float = 30.0,
        client: AsyncGroq | None = None,
    ) -> None:
        if not api_key:
            raise AppException(
                detail="GROQ_API_KEY is not configured. Please provide a valid Groq API key.",
                status_code=500,
            )
        self.api_key = api_key
        self.model = model or "llama-3.3-70b-versatile"
        self.timeout = timeout
        self.client = client or AsyncGroq(api_key=api_key, timeout=timeout)

    @property
    def has_vision_capability(self) -> bool:
        """Determines whether current Groq model supports visual/image understanding."""
        return "vision" in self.model.lower()

    async def analyze_image(
        self,
        image_path: str,
        prompt: str = "Analyze this academic plot, chart, or diagram and describe its axes, metrics, trends, and results.",
        **kwargs: Any,
    ) -> str | None:
        if not self.has_vision_capability:
            return None
        import base64
        from pathlib import Path
        img_p = Path(image_path)
        if not img_p.exists():
            return None
        ext = img_p.suffix.lower()
        mime = "image/png"
        if ext in [".jpg", ".jpeg"]:
            mime = "image/jpeg"
        elif ext == ".webp":
            mime = "image/webp"

        try:
            b64_data = base64.b64encode(img_p.read_bytes()).decode("utf-8")
            data_url = f"data:{mime};base64,{b64_data}"
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                temperature=0.2,
                max_tokens=400,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Groq vision analysis failed for %s: %s", image_path, exc)
            return None

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

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", 0.0),
            )
            return response.choices[0].message.content or ""
        except AuthenticationError as e:
            logger.error("Groq authentication failure: invalid or expired API key.")
            raise AppException(
                detail="Groq authentication failed: Invalid or expired API key.",
                status_code=502,
            ) from e
        except RateLimitError as e:
            logger.warning("Groq rate limit exceeded.")
            raise AppException(
                detail="Groq rate limit exceeded. Please try again later.",
                status_code=429,
            ) from e
        except APITimeoutError as e:
            logger.error("Groq API request timed out.")
            raise AppException(
                detail="Groq request timed out. Please try again.",
                status_code=504,
            ) from e
        except APIConnectionError as e:
            logger.error("Groq network connection error.")
            raise AppException(
                detail="Groq network connection error. Could not reach Groq API.",
                status_code=502,
            ) from e
        except BadRequestError as e:
            err_msg = str(getattr(e, "message", e)).lower()
            provider_msg = getattr(e, "message", str(e))
            if any(term in err_msg for term in ("413", "context_length_exceeded", "too large", "tokens", "maximum context")):
                logger.error("Failure Stage: Model Context-Length Exceeded (BadRequestError). Provider message: %s", provider_msg)
                raise AppException(
                    detail=f"AI model context-length exceeded for {self.model} (HTTP 413: {provider_msg}). Please reduce submission file size.",
                    status_code=413,
                ) from e
            logger.error("Groq bad request error: %s", provider_msg)
            raise AppException(
                detail="Groq API bad request error.",
                status_code=502,
            ) from e
        except APIStatusError as e:
            status_code = getattr(e, "status_code", 502)
            provider_msg = getattr(e, "message", str(e))
            if status_code == 413:
                logger.error("Failure Stage: Groq Provider HTTP 413. Provider message: %s", provider_msg)
                raise AppException(
                    detail=f"AI provider rejected request: Payload too large for model {self.model} (HTTP 413: {provider_msg}). Please reduce submission file size.",
                    status_code=413,
                ) from e
            logger.error("Groq API status error: status_code=%s, message=%s", status_code, provider_msg)
            raise AppException(
                detail=f"Groq API error ({status_code}).",
                status_code=502,
            ) from e
        except GroqError as e:
            logger.error("Groq SDK general error.")
            raise AppException(
                detail="Groq API request failed.",
                status_code=502,
            ) from e

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

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", 0.0),
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or "{}"
        except AuthenticationError as e:
            logger.error("Groq authentication failure: invalid or expired API key.")
            raise AppException(
                detail="Groq authentication failed: Invalid or expired API key.",
                status_code=502,
            ) from e
        except RateLimitError as e:
            logger.warning("Groq rate limit exceeded.")
            raise AppException(
                detail="Groq rate limit exceeded. Please try again later.",
                status_code=429,
            ) from e
        except APITimeoutError as e:
            logger.error("Groq API request timed out.")
            raise AppException(
                detail="Groq request timed out. Please try again.",
                status_code=504,
            ) from e
        except APIConnectionError as e:
            logger.error("Groq network connection error.")
            raise AppException(
                detail="Groq network connection error. Could not reach Groq API.",
                status_code=502,
            ) from e
        except BadRequestError as e:
            err_msg = str(getattr(e, "message", e)).lower()
            provider_msg = getattr(e, "message", str(e))
            if any(term in err_msg for term in ("413", "context_length_exceeded", "too large", "tokens", "maximum context")):
                logger.error("Failure Stage: Model Context-Length Exceeded (BadRequestError). Provider message: %s", provider_msg)
                raise AppException(
                    detail=f"AI model context-length exceeded for {self.model} (HTTP 413: {provider_msg}). Please reduce submission file size.",
                    status_code=413,
                ) from e
            logger.error("Groq bad request error: %s", provider_msg)
            raise AppException(
                detail="Groq API bad request error.",
                status_code=502,
            ) from e
        except APIStatusError as e:
            status_code = getattr(e, "status_code", 502)
            provider_msg = getattr(e, "message", str(e))
            if status_code == 413:
                logger.error("Failure Stage: Groq Provider HTTP 413. Provider message: %s", provider_msg)
                raise AppException(
                    detail=f"AI provider rejected request: Payload too large for model {self.model} (HTTP 413: {provider_msg}). Please reduce submission file size.",
                    status_code=413,
                ) from e
            logger.error("Groq API status error: status_code=%s, message=%s", status_code, provider_msg)
            raise AppException(
                detail=f"Groq API error ({status_code}).",
                status_code=502,
            ) from e
        except Exception as e:
            if isinstance(e, AppException):
                raise
            logger.error("Groq SDK general error: %s", type(e).__name__)
            raise AppException(
                detail="Groq API request failed.",
                status_code=502,
            ) from e

        # Clean markdown JSON fencing if returned by model
        content = raw_content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)

        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Groq returned malformed non-JSON content.")
            raise AppException(
                detail="Groq model returned malformed non-JSON output.",
                status_code=502,
            ) from e

        try:
            return response_model.model_validate(parsed)
        except Exception as e:
            logger.error("Groq output failed schema validation: %s", e)
            raise AppException(
                detail="Groq model output failed structured schema validation.",
                status_code=502,
            ) from e

