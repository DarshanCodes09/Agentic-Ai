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

    model_config = SettingsConfigDict(
        # pydantic-settings tries each file left-to-right; first match wins per key.
        env_file=(".env", ".env.test"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Use as a FastAPI dependency."""
    return Settings()
