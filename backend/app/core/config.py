"""
Application configuration using pydantic-settings.
All settings are loaded from environment variables (or backend/.env file).

Priority (highest to lowest):
  1. Actual environment variables
  2. .env file in the working directory
  3. .env.test file (used during pytest runs)
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "AI Academic Assessment System"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Document Processing & RAG (Phase 3)
    chroma_persist_dir: str = "./chroma_db"
    embedding_provider: str = "default"  # "default", "mock", "openai", etc.
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_api_key: str | None = None
    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_top_k: int = 4

    # LLM & AI Assessment (Phase 4 & Phase 7)
    llm_provider: str = "mock"  # "mock", "groq", "openai", "gemini"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    llm_timeout: int = 30

    # Groq API Integration (Phase 7)
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    # Multi-Format Submissions, Code & Notebooks (Phase 10)
    max_upload_size_mb: int = 25
    max_zip_extracted_size_mb: int = 60
    max_zip_file_count: int = 250
    max_code_file_size_kb: int = 500
    max_notebook_cell_output_chars: int = 600

    # Assessment Prompt & Evidence Budgets (Groq 413 & TPM Safeguards)
    max_assessment_prompt_tokens: int = 4200
    max_assessment_prompt_chars: int = 16000
    max_submission_evidence_chars: int = 8000
    max_code_file_chars: int = 2500
    max_project_source_files: int = 5
    max_rag_context_chars: int = 1200
    max_assignment_instructions_chars: int = 1500
    max_notebook_cells: int = 25

    model_config = SettingsConfigDict(
        # .env.test provides test fallbacks; runtime .env takes precedence when present.
        env_file=(".env.test", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )



@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Use as a FastAPI dependency."""
    return Settings()
