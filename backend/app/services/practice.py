"""Shared helpers for the practice loop: ownership checks and small lookups."""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt, Chunk, Concept, Document, Question
from app.schemas import AttemptOut


def get_owned_concept(session: Session, concept_id: int, user_id: int) -> Concept:
    concept = session.scalar(
        select(Concept)
        .join(Document, Document.id == Concept.document_id)
        .where(Concept.id == concept_id, Document.user_id == user_id)
    )
    if concept is None:
        raise HTTPException(404, "Concept not found.")
    return concept


def get_owned_question(session: Session, question_id: int, user_id: int) -> Question:
    question = session.scalar(
        select(Question)
        .join(Concept, Concept.id == Question.concept_id)
        .join(Document, Document.id == Concept.document_id)
        .where(Question.id == question_id, Document.user_id == user_id)
    )
    if question is None:
        raise HTTPException(404, "Question not found.")
    return question


def get_owned_attempt(session: Session, attempt_id: int, user_id: int) -> Attempt:
    attempt = session.get(Attempt, attempt_id)
    if attempt is None or attempt.user_id != user_id:
        raise HTTPException(404, "Attempt not found.")
    return attempt


def require_in_progress(attempt: Attempt) -> None:
    if attempt.status != "in_progress":
        raise HTTPException(409, f"This attempt is already {attempt.status}.")


def chunks_by_ids(session: Session, ids: list[int]) -> list[Chunk]:
    if not ids:
        return []
    return list(
        session.scalars(
            select(Chunk).where(Chunk.id.in_(ids)).order_by(Chunk.document_id, Chunk.chunk_index)
        )
    )


def attempt_out(attempt: Attempt) -> AttemptOut:
    score = attempt.effective_score
    return AttemptOut(
        id=attempt.id,
        question_id=attempt.question_id,
        status=attempt.status,
        max_hint_level=attempt.max_hint_level,
        revealed=attempt.revealed_at is not None,
        effective_score=float(score) if isinstance(score, Decimal) else score,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
    )
