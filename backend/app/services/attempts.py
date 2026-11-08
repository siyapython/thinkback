"""Attempts: start, answer + grade, complete (with effective score + mastery), reveal."""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Answer, Attempt, Concept, Question
from app.prompts.grade_answer import PROMPT_VERSION as GRADE_PROMPT_VERSION
from app.prompts.grade_answer import SYSTEM_PROMPT as GRADE_SYSTEM
from app.prompts.grade_answer import build_user_prompt as build_grade_prompt
from app.schemas import GradeResult
from app.services.events import log_event
from app.services.leak import check_leak
from app.services.llm import LLMClient, LLMError, complete_json
from app.services.mastery import update_mastery
from app.services.practice import require_in_progress

PASS_THRESHOLD = Decimal("0.8")
# Using hints lowers the effective score: the more help, the less independent the success.
HINT_FACTOR = {
    0: Decimal("1.0"),
    1: Decimal("0.85"),
    2: Decimal("0.65"),
    3: Decimal("0.4"),
    4: Decimal("0.4"),
}
GENERIC_FEEDBACK = (
    "Not quite there yet. Re-read the question and your notes: which part of your answer "
    "are you least sure about, and why?"
)


def _now() -> datetime:
    return datetime.now(UTC)


def start_attempt(session: Session, question: Question, user_id: int) -> Attempt:
    attempt = Attempt(user_id=user_id, question_id=question.id)
    session.add(attempt)
    session.flush()
    concept = session.get(Concept, question.concept_id)
    log_event(
        session,
        user_id=user_id,
        event_type="question_served",
        document_id=concept.document_id,
        concept_id=concept.id,
        question_id=question.id,
        attempt_id=attempt.id,
        payload={
            "question_type": question.question_type,
            "prompt_version": question.prompt_version,
        },
    )
    session.commit()
    return attempt


def effective_score_for(best_rubric_score: Decimal, max_hint_level: int, revealed: bool) -> Decimal:
    """effective_score = rubric_score * hint_factor (0 if the answer was revealed)."""
    factor = Decimal(0) if revealed else HINT_FACTOR[max_hint_level]
    return (Decimal(best_rubric_score) * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def finish_attempt(session: Session, attempt: Attempt, *, revealed: bool = False) -> None:
    """Mark the attempt completed, store effective_score, and update concept mastery.
    Uses the best rubric score among the attempt's graded answers (0 if there are none)."""
    best = session.scalar(
        select(func.max(Answer.rubric_score)).where(
            Answer.attempt_id == attempt.id, Answer.graded_at.is_not(None)
        )
    )
    attempt.effective_score = effective_score_for(
        Decimal(best if best is not None else 0), attempt.max_hint_level, revealed
    )
    attempt.status = "completed"
    attempt.completed_at = _now()
    if revealed:
        attempt.revealed_at = attempt.completed_at

    last_misconception = session.scalar(
        select(Answer.misconception)
        .where(Answer.attempt_id == attempt.id, Answer.graded_at.is_not(None))
        .order_by(Answer.id.desc())
        .limit(1)
    )
    question = session.get(Question, attempt.question_id)
    update_mastery(
        session,
        user_id=attempt.user_id,
        concept_id=question.concept_id,
        effective_score=attempt.effective_score,
        misconception=last_misconception,
    )


def complete_attempt(session: Session, attempt: Attempt) -> Attempt:
    """Student-requested completion. Calling it again on a finished attempt changes nothing."""
    if attempt.status == "completed":
        return attempt
    require_in_progress(attempt)
    finish_attempt(session, attempt)
    session.commit()
    return attempt


def submit_answer(
    session: Session, attempt: Attempt, answer_text: str, llm: LLMClient
) -> tuple[Answer, GradeResult, int, bool]:
    """Store the answer, grade it, maybe complete the attempt.
    Returns (answer, grade, rubric_size, feedback_was_replaced)."""
    require_in_progress(attempt)
    question = session.get(Question, attempt.question_id)
    concept = session.get(Concept, question.concept_id)
    rubric: list[str] = list(question.rubric)

    answer = Answer(attempt_id=attempt.id, answer_text=answer_text)
    session.add(answer)
    session.flush()
    n_answers = session.scalar(
        select(func.count()).select_from(Answer).where(Answer.attempt_id == attempt.id)
    )
    log_event(
        session,
        user_id=attempt.user_id,
        event_type="answer_submitted",
        document_id=concept.document_id,
        concept_id=concept.id,
        question_id=question.id,
        attempt_id=attempt.id,
        payload={
            "answer_number": n_answers,
            "answer_length": len(answer_text),
            "max_hint_level": attempt.max_hint_level,
        },
    )
    session.commit()  # the answer is kept even if grading fails below

    try:
        grade, result = complete_json(
            llm,
            system=GRADE_SYSTEM,
            user=build_grade_prompt(
                question=question.prompt,
                rubric=rubric,
                misconceptions=list(question.misconceptions or []),
                answer_text=answer_text,
            ),
            schema=GradeResult,
            tier="fast",
        )
    except LLMError as exc:
        raise HTTPException(
            502, f"Grading failed: {exc}. Your answer was saved; try again."
        ) from exc

    # The student must not see missed key points: check the feedback and replace it if it leaks.
    covered_norm = {p.strip().casefold() for p in grade.points_covered}
    uncovered = [p for p in rubric if p.strip().casefold() not in covered_norm]
    check_against = list(grade.points_missed) + uncovered
    replaced = check_leak(grade.feedback, check_against, exclude=question.prompt).leaked
    feedback = GENERIC_FEEDBACK if replaced else grade.feedback

    score = Decimal(str(round(grade.rubric_score, 2)))
    answer.rubric_score = score
    answer.points_covered = grade.points_covered
    answer.points_missed = grade.points_missed
    answer.misconception = grade.misconception
    answer.feedback = feedback
    answer.grader_model = result.model
    answer.grader_prompt_version = GRADE_PROMPT_VERSION
    answer.graded_at = _now()

    completed = score >= PASS_THRESHOLD
    if completed:
        session.flush()
        finish_attempt(session, attempt)

    log_event(
        session,
        user_id=attempt.user_id,
        event_type="answer_graded",
        document_id=concept.document_id,
        concept_id=concept.id,
        question_id=question.id,
        attempt_id=attempt.id,
        payload={
            "rubric_score": float(score),
            "points_covered_count": len(grade.points_covered),
            "points_total": len(rubric),
            "misconception": grade.misconception,
            "feedback_replaced": replaced,
            "completed": completed,
            "effective_score": float(attempt.effective_score) if completed else None,
            "max_hint_level": attempt.max_hint_level,
            "grader_model": result.model,
            "prompt_version": GRADE_PROMPT_VERSION,
        },
    )
    session.commit()
    return answer, grade.model_copy(update={"feedback": feedback}), len(rubric), replaced


def reveal_attempt(session: Session, attempt: Attempt) -> str:
    """Show an explanation built from the rubric. The attempt completes with effective_score 0."""
    require_in_progress(attempt)
    question = session.get(Question, attempt.question_id)
    concept = session.get(Concept, question.concept_id)
    best = session.scalar(
        select(func.max(Answer.rubric_score)).where(
            Answer.attempt_id == attempt.id, Answer.graded_at.is_not(None)
        )
    )
    finish_attempt(session, attempt, revealed=True)
    log_event(
        session,
        user_id=attempt.user_id,
        event_type="answer_revealed",
        document_id=concept.document_id,
        concept_id=concept.id,
        question_id=question.id,
        attempt_id=attempt.id,
        payload={
            "max_hint_level": attempt.max_hint_level,
            "best_rubric_score": float(best) if best is not None else None,
        },
    )
    session.commit()
    points = "\n".join(f"- {p}" for p in question.rubric)
    return f"A strong answer to this question covers:\n{points}"
