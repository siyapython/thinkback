"""Mastery tracking: an exponential moving average per (user, concept), plus the gap rule."""

import re
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Answer, Attempt, Concept, ConceptMastery, Question

OLD_WEIGHT = Decimal("0.7")
NEW_WEIGHT = Decimal("0.3")
GAP_MASTERY = Decimal("0.6")
GAP_MIN_ATTEMPTS = 2


def ema(old: Decimal, new: Decimal, *, first: bool) -> Decimal:
    """new = 0.7 * old + 0.3 * score; the very first attempt just takes the score."""
    value = new if first else OLD_WEIGHT * old + NEW_WEIGHT * new
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def update_mastery(
    session: Session,
    *,
    user_id: int,
    concept_id: int,
    effective_score: Decimal,
    misconception: str | None,
) -> ConceptMastery:
    row = session.get(ConceptMastery, (user_id, concept_id))
    if row is None:
        row = ConceptMastery(
            user_id=user_id, concept_id=concept_id, mastery=Decimal(0), attempt_count=0
        )
        session.add(row)
    row.mastery = ema(Decimal(row.mastery), Decimal(effective_score), first=row.attempt_count == 0)
    row.attempt_count += 1
    if misconception:
        row.last_misconception = misconception
    session.flush()
    return row


def _norm(text: str | None) -> str | None:
    if not text:
        return None
    return re.sub(r"[\W_]+", " ", text.casefold()).strip() or None


def is_gap(mastery: Decimal, attempt_count: int, recent_misconceptions: list[str | None]) -> bool:
    """A concept is a gap if mastery < 0.6 after at least 2 attempts, OR the same
    misconception showed up in the two most recent completed attempts (newest first)."""
    if attempt_count >= GAP_MIN_ATTEMPTS and Decimal(mastery) < GAP_MASTERY:
        return True
    last_two = [_norm(m) for m in recent_misconceptions[:2]]
    return len(last_two) == 2 and last_two[0] is not None and last_two[0] == last_two[1]


def recent_misconceptions(
    session: Session, user_id: int, concept_ids: list[int]
) -> dict[int, list[str | None]]:
    """For each concept: the misconception of each completed attempt, newest first.
    An attempt's misconception is the one on its last graded answer (None if there was none)."""
    if not concept_ids:
        return {}
    attempts = session.execute(
        select(Attempt.id, Question.concept_id)
        .join(Question, Question.id == Attempt.question_id)
        .where(
            Attempt.user_id == user_id,
            Attempt.status == "completed",
            Question.concept_id.in_(concept_ids),
        )
        .order_by(Attempt.completed_at.desc(), Attempt.id.desc())
    ).all()
    attempt_ids = [a for a, _ in attempts]
    last_misconception: dict[int, str | None] = {}
    if attempt_ids:
        answers = session.execute(
            select(Answer.attempt_id, Answer.misconception)
            .where(Answer.attempt_id.in_(attempt_ids), Answer.graded_at.is_not(None))
            .order_by(Answer.id)
        )
        for attempt_id, misconception in answers:  # later answers overwrite earlier ones
            last_misconception[attempt_id] = misconception
    result: dict[int, list[str | None]] = {}
    for attempt_id, concept_id in attempts:
        result.setdefault(concept_id, []).append(last_misconception.get(attempt_id))
    return result


def document_mastery(session: Session, user_id: int, document_id: int) -> list[dict]:
    concepts = list(
        session.scalars(
            select(Concept)
            .where(Concept.document_id == document_id, Concept.is_active.is_(True))
            .order_by(Concept.id)
        )
    )
    ids = [c.id for c in concepts]
    rows = {
        r.concept_id: r
        for r in session.scalars(
            select(ConceptMastery).where(
                ConceptMastery.user_id == user_id, ConceptMastery.concept_id.in_(ids)
            )
        )
    }
    recent = recent_misconceptions(session, user_id, ids)
    out = []
    for c in concepts:
        row = rows.get(c.id)
        mastery = Decimal(row.mastery) if row else Decimal(0)
        count = row.attempt_count if row else 0
        out.append(
            {
                "concept_id": c.id,
                "name": c.name,
                "mastery": float(mastery),
                "attempt_count": count,
                "is_gap": is_gap(mastery, count, recent.get(c.id, [])),
            }
        )
    return out
