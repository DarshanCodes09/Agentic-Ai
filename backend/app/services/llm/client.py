"""
LLM Service client wrapper and factory.
"""

import logging
from typing import Any, TypeVar
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.services.llm.base import BaseLLMProvider
from app.services.llm.provider import (
    GeminiLLMProvider,
    GroqLLMProvider,
    MockLLMProvider,
    OpenAILLMProvider,
)

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMService:
    """Centralized LLM service used by AssessmentAgent and FeedbackAgent."""

    def __init__(self, provider: BaseLLMProvider | None = None) -> None:
        if provider is not None:
            self._provider = provider
            if isinstance(provider, MockLLMProvider):
                self.provider_name = "mock"
            elif isinstance(provider, GroqLLMProvider):
                self.provider_name = "groq"
            else:
                self.provider_name = provider.__class__.__name__.lower().replace("llmprovider", "")
        else:
            settings = get_settings()
            provider_type = (settings.llm_provider or "mock").lower()
            self.provider_name = provider_type

            if provider_type == "groq":
                api_key = settings.groq_api_key or settings.llm_api_key
                model = settings.groq_model or settings.llm_model or "llama-3.3-70b-versatile"
                if not api_key:
                    raise AppException(
                        detail="GROQ_API_KEY is not configured. Please set GROQ_API_KEY to use the Groq provider.",
                        status_code=500,
                    )
                self._provider = GroqLLMProvider(
                    api_key=api_key,
                    model=model,
                    timeout=settings.llm_timeout,
                )
                self.provider_name = "groq"
            elif provider_type == "openai":
                if not settings.llm_api_key:
                    logger.warning("LLM_API_KEY is not set for OpenAI; falling back to MockLLMProvider.")
                    self._provider = MockLLMProvider()
                    self.provider_name = "mock"
                else:
                    self._provider = OpenAILLMProvider(
                        api_key=settings.llm_api_key,
                        model=settings.llm_model,
                        timeout=settings.llm_timeout,
                    )
            elif provider_type == "gemini":
                if not settings.llm_api_key:
                    logger.warning("LLM_API_KEY is not set for Gemini; falling back to MockLLMProvider.")
                    self._provider = MockLLMProvider()
                    self.provider_name = "mock"
                else:
                    self._provider = GeminiLLMProvider(
                        api_key=settings.llm_api_key,
                        model=settings.llm_model,
                        timeout=settings.llm_timeout,
                    )
            else:
                self._provider = MockLLMProvider()
                self.provider_name = "mock"


    @property
    def provider(self) -> BaseLLMProvider:
        return self._provider

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Forward raw generation call to active provider."""
        return await self._provider.generate(prompt, system_prompt=system_prompt, **kwargs)

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> T:
        """Forward structured output generation call to active provider."""
        return await self._provider.generate_structured(
            prompt,
            response_model=response_model,
            system_prompt=system_prompt,
            **kwargs,
        )


_llm_service_instance: LLMService | None = None


def get_llm_service() -> LLMService:
    """Dependency / singleton accessor for LLMService."""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance


def reset_llm_service() -> None:
    """Reset the singleton instance (useful for testing override)."""
    global _llm_service_instance
    _llm_service_instance = None
