from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.deps import current_user_id, llm_client
from app.models import Attempt, Document
from app.schemas import (
    AnswerIn,
    AnswerOut,
    AttemptOut,
    ConceptMasteryOut,
    HintOut,
    IndependenceOut,
    QuestionCreateIn,
    QuestionOut,
    RevealOut,
)
from app.services import attempts as attempt_service
from app.services import hints as hint_service
from app.services import questions as question_service
from app.services.llm import LLMClient
from app.services.mastery import document_mastery
from app.services.practice import (
    attempt_out,
    get_owned_attempt,
    get_owned_concept,
    get_owned_question,
)

router = APIRouter(tags=["practice"])


def _question_out(q) -> QuestionOut:
    # Built field by field on purpose: the rubric and misconceptions can never slip in.
    return QuestionOut(
        id=q.id, concept_id=q.concept_id, question_type=q.question_type, prompt=q.prompt
    )


@router.post("/concepts/{concept_id}/questions", response_model=QuestionOut, status_code=201)
def create_question(
    concept_id: int,
    body: QuestionCreateIn | None = None,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
    llm: LLMClient = Depends(llm_client),
) -> QuestionOut:
    concept = get_owned_concept(session, concept_id, user_id)
    qtype = body.question_type if body else None
    return _question_out(question_service.generate_question(session, concept, llm, qtype))


@router.get("/questions/{question_id}", response_model=QuestionOut)
def get_question(
    question_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
) -> QuestionOut:
    return _question_out(get_owned_question(session, question_id, user_id))


@router.post("/questions/{question_id}/attempts", response_model=AttemptOut, status_code=201)
def start_attempt(
    question_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
) -> AttemptOut:
    question = get_owned_question(session, question_id, user_id)
    return attempt_out(attempt_service.start_attempt(session, question, user_id))


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(
    attempt_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
) -> AttemptOut:
    return attempt_out(get_owned_attempt(session, attempt_id, user_id))


@router.post("/attempts/{attempt_id}/answers", response_model=AnswerOut, status_code=201)
def submit_answer(
    attempt_id: int,
    body: AnswerIn,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
    llm: LLMClient = Depends(llm_client),
) -> AnswerOut:
    attempt = get_owned_attempt(session, attempt_id, user_id)
    answer, grade, rubric_size, _ = attempt_service.submit_answer(
        session, attempt, body.answer_text, llm
    )
    return AnswerOut(
        answer_id=answer.id,
        rubric_score=float(answer.rubric_score),
        feedback=grade.feedback,
        points_covered_count=len(grade.points_covered),
        points_total=rubric_size,
        attempt=attempt_out(attempt),
    )


@router.post("/attempts/{attempt_id}/hints", response_model=HintOut, status_code=201)
def request_hint(
    attempt_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
    llm: LLMClient = Depends(llm_client),
) -> HintOut:
    attempt = get_owned_attempt(session, attempt_id, user_id)
    hint = hint_service.request_hint(session, attempt, llm)
    return HintOut(
        level=hint.level,
        hint_text=hint.hint_text,
        cited_chunk_ids=hint.cited_chunk_ids or [],
        hints_remaining=hint_service.MAX_LEVEL - attempt.max_hint_level,
        attempt=attempt_out(attempt),
    )


@router.post("/attempts/{attempt_id}/reveal", response_model=RevealOut)
def reveal(
    attempt_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
) -> RevealOut:
    attempt = get_owned_attempt(session, attempt_id, user_id)
    explanation = attempt_service.reveal_attempt(session, attempt)
    return RevealOut(explanation=explanation, attempt=attempt_out(attempt))


@router.post("/attempts/{attempt_id}/complete", response_model=AttemptOut)
def complete(
    attempt_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
) -> AttemptOut:
    attempt = get_owned_attempt(session, attempt_id, user_id)
    return attempt_out(attempt_service.complete_attempt(session, attempt))


@router.get("/documents/{document_id}/mastery", response_model=list[ConceptMasteryOut])
def get_mastery(
    document_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(current_user_id),
) -> list[ConceptMasteryOut]:
    doc = session.get(Document, document_id)
    if doc is None or doc.user_id != user_id:
        raise HTTPException(404, "Document not found.")
    return [ConceptMasteryOut(**row) for row in document_mastery(session, user_id, doc.id)]


@router.get("/metrics/independence", response_model=IndependenceOut)
def independence(
    session: Session = Depends(get_session), user_id: int = Depends(current_user_id)
) -> IndependenceOut:
    """Share of completed attempts finished with at most hint level 1 and no reveal."""
    completed = Attempt.user_id == user_id, Attempt.status == "completed"
    total = session.scalar(select(func.count()).select_from(Attempt).where(*completed)) or 0
    independent = (
        session.scalar(
            select(func.count())
            .select_from(Attempt)
            .where(*completed, Attempt.max_hint_level <= 1, Attempt.revealed_at.is_(None))
        )
        or 0
    )
    rate = float(round(Decimal(independent) / Decimal(total), 3)) if total else None
    return IndependenceOut(
        completed_attempts=total, independent_attempts=independent, independence_rate=rate
    )
