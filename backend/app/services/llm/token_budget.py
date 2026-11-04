"""
Token estimation and model context limit definitions for safe LLM requests.
Prevents HTTP 413 payload rejections on providers like Groq by enforcing conservative
token budgets with response headroom before requests are dispatched.
"""

import logging
from typing import Any
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Known safe input token budgets by model.
# On Groq Free Tier, llama-3.3-70b-versatile has a 6,000 TPM limit.
# Reserving ~1,800 tokens for JSON output generation leaves a maximum safe
# request input limit of ~4,200 tokens.
MODEL_SAFE_REQUEST_TOKEN_LIMITS: dict[str, int] = {
    "llama-3.3-70b-versatile": 4200,
    "llama-3.1-70b-versatile": 4200,
    "llama-3.1-8b-instant": 6500,
    "llama3-70b-8192": 4200,
    "llama3-8b-8192": 6000,
    "mixtral-8x7b-32768": 6000,
    "gpt-4o-mini": 12000,
    "gpt-4o": 16000,
    "gemini-1.5-flash": 16000,
}

DEFAULT_SAFE_TOKEN_BUDGET: int = 4200


def estimate_tokens(text: str) -> int:
    """
    Conservative token estimator for source code, markdown, and structured JSON.
    Uses character and word heuristics with safety margins so requests do not
    underestimate real tokenizer counts on punctuation-heavy code payloads.
    """
    if not text:
        return 0
    # Code, punctuation, and JSON delimiters average ~3.2 characters per token
    char_estimate = int(len(text) / 3.2) + 1
    word_estimate = int(len(text.split()) * 1.3) + 1
    return max(char_estimate, word_estimate)


def get_model_safe_token_limit(model_name: str | None = None) -> int:
    """
    Determine the safe maximum input tokens for the configured model.
    Falls back to settings.max_assessment_prompt_tokens or DEFAULT_SAFE_TOKEN_BUDGET.
    """
    settings = get_settings()
    configured_setting = getattr(settings, "max_assessment_prompt_tokens", DEFAULT_SAFE_TOKEN_BUDGET)
    if model_name:
        cleaned_model = model_name.lower().strip()
        model_cap = MODEL_SAFE_REQUEST_TOKEN_LIMITS.get(cleaned_model, DEFAULT_SAFE_TOKEN_BUDGET)
        return min(configured_setting, model_cap)
    return configured_setting
