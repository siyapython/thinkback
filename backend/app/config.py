from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> repo root is two levels above backend/app
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+psycopg://thinkback:thinkback@localhost:5432/thinkback"
    ANTHROPIC_API_KEY: str = ""
    LLM_MODE: Literal["fake", "real"] = "fake"
    MODEL_FAST: str = "claude-haiku-5-5"
    MODEL_STRONG: str = "claude-sonnet-5-5"

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Documents
    DEMO_USER_ID: int = 1  # until real auth exists, every request acts as the demo user
    UPLOAD_DIR: Path = BACKEND_DIR / "uploads"
    MAX_PAGES: int = 30
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    # Refuse to send more than this much text to the LLM in one extraction call (~100k tokens).
    MAX_EXTRACTION_CHARS: int = 400_000


@lru_cache
def get_settings() -> Settings:
    return Settings()
