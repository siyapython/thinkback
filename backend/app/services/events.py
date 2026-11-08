from typing import Any

from sqlalchemy.orm import Session

from app.models import EventRaw


def log_event(
    session: Session,
    *,
    user_id: int,
    event_type: str,
    document_id: int | None = None,
    concept_id: int | None = None,
    question_id: int | None = None,
    attempt_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Add an events_raw row to the current transaction (the caller commits)."""
    session.add(
        EventRaw(
            user_id=user_id,
            event_type=event_type,
            document_id=document_id,
            concept_id=concept_id,
            question_id=question_id,
            attempt_id=attempt_id,
            payload=payload or {},
        )
    )
