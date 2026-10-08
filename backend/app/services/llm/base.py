"""
Base interface for LLM providers.
"""

from abc import ABC, abstractmethod
from typing import Any, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers (Mock, OpenAI, Gemini, etc.)."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate raw text response from the model.

        Args:
            prompt: User prompt.
            system_prompt: Optional instructions for the model.
            kwargs: Provider-specific overrides (temperature, etc.).

        Returns:
            Generated text string.
        """
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> T:
        """
        Generate a strictly validated structured output conforming to a Pydantic model.

        Args:
            prompt: User prompt.
            response_model: Pydantic schema class to parse into.
            system_prompt: Optional system prompt.
            kwargs: Additional parameters.

        Returns:
            Instance of response_model.
        """
        pass
