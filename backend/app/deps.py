from fastapi import HTTPException

from app.config import get_settings
from app.services.llm import LLMClient, LLMError, get_llm_client


def current_user_id() -> int:
    """Until real auth exists, every request acts as the demo user."""
    return get_settings().DEMO_USER_ID


def llm_client() -> LLMClient:
    try:
        return get_llm_client()
    except LLMError as exc:
        raise HTTPException(503, str(exc)) from exc
