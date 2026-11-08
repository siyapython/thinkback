"""Seed SYNTHETIC demo data for the analytics dashboard.

    python -m pipeline.seed_demo            # create "Demo Learner (synthetic)"; no-op if present
    python -m pipeline.seed_demo --reset    # delete ONLY that user's data, then re-create it

!! This data is made up by a random number generator. It is NOT real usage and must never be
!! presented as evidence of real learners or real results. Every synthetic row is marked:
!! the document's content_hash starts with "synthetic-demo", models are "synthetic-demo",
!! and every event payload has "synthetic": true.

The story it tells (4 weeks, ending today): the learner needs fewer hints over time, so
independence rises, while two concepts (window functions, correlated subqueries) stay weak.
No LLM is called; rows are inserted directly. The seed is fixed, so the same end date always
produces the same data. It never reads or writes the real demo user (id DEMO_USER_ID).
"""

import argparse
import random
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from app.config import get_settings
from app.models import (
    Answer,
    Attempt,
    Concept,
    ConceptMastery,
    Document,
    EventRaw,
    HintRequest,
    Question,
    User,
)
from app.services.attempts import effective_score_for
from app.services.mastery import update_mastery
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

# Not plain "Demo Learner": the real demo user (id 1) already has that name. The synthetic user is
# found by its marker document (CONTENT_HASH), never by name.
DEMO_NAME = "Demo Learner (synthetic)"
CONTENT_HASH = "synthetic-demo-v1"
SEED = 20260101
DAYS = 28
MODEL = "synthetic-demo"

# (name, definition, is_weak)
CONCEPTS = [
    ("SELECT and WHERE", "Choosing columns and filtering rows.", False),
    ("JOINs", "Combining rows from two tables on a key.", False),
    ("GROUP BY and aggregates", "Collapsing rows into groups with COUNT, SUM, AVG.", False),
    ("HAVING", "Filtering groups after aggregation.", False),
    ("CTEs", "Naming a subquery with WITH to make queries readable.", False),
    ("Indexes", "Data structures that speed up lookups.", False),
    ("Window functions", "Calculations across related rows without collapsing them.", True),
    ("Correlated subqueries", "Subqueries that reference the outer query's row.", True),
]
WEAK_MISCONCEPTIONS = {
    "Window functions": "Thinks PARTITION BY collapses rows like GROUP BY",
    "Correlated subqueries": "Thinks the subquery runs once, not once per outer row",
}
GENERIC_MISCONCEPTIONS = [
    "Confuses WHERE with HAVING",
    "Forgets that NULL never equals NULL",
    "Mixes up INNER and LEFT JOIN results",
]
# Probability of max hint level 0..4 for concepts that get learned: week 1 vs week 4.
EARLY_LEVELS = [0.05, 0.15, 0.30, 0.30, 0.20]
LATE_LEVELS = [0.55, 0.30, 0.10, 0.04, 0.01]
WEAK_LEVELS = [0.03, 0.10, 0.25, 0.33, 0.29]


def _utc(day: date, minutes_into_day: float) -> datetime:
    return datetime.combine(day, time(0), tzinfo=UTC) + timedelta(minutes=minutes_into_day)


def _levels(weak: bool, t: float) -> list[float]:
    if weak:
        return WEAK_LEVELS
    return [e + (late - e) * t for e, late in zip(EARLY_LEVELS, LATE_LEVELS, strict=True)]


def _event(user_id, event_type, at, concept, question, attempt_id, payload) -> EventRaw:
    return EventRaw(
        user_id=user_id,
        event_type=event_type,
        document_id=concept.document_id,
        concept_id=concept.id,
        question_id=question.id if question else None,
        attempt_id=attempt_id,
        payload={**payload, "synthetic": True},
        occurred_at=at,
    )


def _misconception(rng: random.Random, concept_name: str, p: float) -> str | None:
    """With probability p, the misconception a grader would report for this concept."""
    if rng.random() >= p:
        return None
    return WEAK_MISCONCEPTIONS.get(concept_name) or rng.choice(GENERIC_MISCONCEPTIONS)


def find_demo_user(session: Session) -> User | None:
    """The synthetic user = whoever owns the marker document. Never matches the real demo user."""
    return session.scalar(
        select(User)
        .join(Document, Document.user_id == User.id)
        .where(Document.content_hash == CONTENT_HASH, User.id != get_settings().DEMO_USER_ID)
    )


def remove_demo_user(session: Session) -> bool:
    """Delete the synthetic user and everything it owns. Refuses to touch anything else."""
    user = find_demo_user(session)
    if user is None:
        return False
    hashes = list(session.scalars(select(Document.content_hash).where(Document.user_id == user.id)))
    if any(not h.startswith("synthetic-demo") for h in hashes):
        raise RuntimeError(
            f'A user named "{DEMO_NAME}" owns non-synthetic documents; not deleting.'
        )
    # (find_demo_user already excludes the real demo user, id DEMO_USER_ID.)
    # Children first. Deleting attempts cascades to their answers and hint_requests;
    # deleting the documents cascades to chunks, concepts, questions, concept_mastery.
    session.execute(delete(EventRaw).where(EventRaw.user_id == user.id))
    session.execute(delete(ConceptMastery).where(ConceptMastery.user_id == user.id))
    session.execute(delete(Attempt).where(Attempt.user_id == user.id))
    session.execute(delete(Document).where(Document.user_id == user.id))
    session.execute(delete(User).where(User.id == user.id))
    session.flush()
    return True


def seed(session: Session, *, end_date: date | None = None, reset: bool = False) -> dict | None:
    """Create the synthetic user. Returns counts, or None if it already exists (no reset)."""
    if reset:
        remove_demo_user(session)
    elif find_demo_user(session) is not None:
        return None

    rng = random.Random(SEED)
    end_date = end_date or datetime.now(UTC).date()
    first_day = end_date - timedelta(days=DAYS - 1)
    first_ts = _utc(first_day, 8 * 60)

    user = User(display_name=DEMO_NAME, created_at=first_ts)
    session.add(user)
    session.flush()
    doc = Document(
        user_id=user.id,
        title="SQL Fundamentals (synthetic demo)",
        source_type="text",
        content_hash=CONTENT_HASH,
        status="ready",
        created_at=first_ts,
    )
    session.add(doc)
    session.flush()

    concepts: list[tuple[Concept, bool, list[Question]]] = []
    for name, definition, weak in CONCEPTS:
        c = Concept(
            document_id=doc.id,
            name=name,
            definition=definition,
            model=MODEL,
            prompt_version="synthetic",
            created_at=first_ts,
        )
        session.add(c)
        session.flush()
        qs = []
        for qtype in ("explain", "apply"):
            q = Question(
                concept_id=c.id,
                question_type=qtype,
                model=MODEL,
                prompt_version="synthetic",
                prompt=f"[synthetic] {qtype.capitalize()}: {name}",
                rubric=[f"Key point 1 about {name}", f"Key point 2 about {name}"],
                misconceptions=[],
                created_at=first_ts,
            )
            session.add(q)
            qs.append(q)
        session.flush()
        concepts.append((c, weak, qs))

    events: list[EventRaw] = [
        _event(
            user.id,
            "document_uploaded",
            first_ts,
            concepts[0][0],
            None,
            None,
            {"source_type": "text"},
        ),
    ]
    # One failed extraction followed by a good one: gives the funnel's filter something to ignore.
    events.append(
        _event(
            user.id,
            "concepts_extracted",
            first_ts + timedelta(minutes=1),
            concepts[0][0],
            None,
            None,
            {"success": False, "error": "synthetic"},
        )
    )
    events.append(
        _event(
            user.id,
            "concepts_extracted",
            first_ts + timedelta(minutes=3),
            concepts[0][0],
            None,
            None,
            {"success": True, "concept_count": 8},
        )
    )

    completions: list[tuple[datetime, Attempt, str | None]] = []
    n_attempts = 0
    for day_idx in range(DAYS):
        day = first_day + timedelta(days=day_idx)
        t = day_idx / (DAYS - 1)  # 0.0 on the first day, 1.0 on the last
        if day.weekday() == 6 and rng.random() < 0.7:  # mostly rest on Sundays
            continue
        if rng.random() < 0.15:
            continue
        for _ in range(rng.choice([2, 3, 3, 4])):
            concept, weak, questions = rng.choices(
                concepts, weights=[1.4 if w else 1.0 for _, w, _ in concepts]
            )[0]
            question = rng.choice(questions)
            level = rng.choices(range(5), weights=_levels(weak, t))[0]
            start = _utc(day, rng.randint(9 * 60, 21 * 60))
            minutes = rng.uniform(8, 15) if weak else rng.uniform(5, 12) * (1 - 0.5 * t)
            end = start + timedelta(minutes=minutes)
            roll = rng.random()
            abandoned = roll < 0.06
            if weak:
                reveal = level >= 3 and rng.random() < 0.35
            else:
                reveal = level >= 3 and rng.random() < 0.10 * (1 - t) + 0.01
            misc_p = 0.6 if weak else 0.35 * (1 - t) + 0.05

            if abandoned:
                level = min(level, 1)
            attempt = Attempt(
                user_id=user.id,
                question_id=question.id,
                started_at=start,
                status="abandoned" if abandoned else "completed",
                max_hint_level=level,
            )
            session.add(attempt)
            session.flush()
            n_attempts += 1
            events.append(
                _event(
                    user.id,
                    "question_served",
                    start,
                    concept,
                    question,
                    attempt.id,
                    {"question_type": question.question_type},
                )
            )
            for lv in range(1, level + 1):
                at = start + (end - start) * (0.1 + 0.5 * lv / 4)
                session.add(
                    HintRequest(
                        attempt_id=attempt.id,
                        level=lv,
                        hint_text=f"[synthetic] hint level {lv}",
                        model=MODEL,
                        prompt_version="synthetic",
                        created_at=at,
                    )
                )
                events.append(
                    _event(
                        user.id,
                        "hint_requested",
                        at,
                        concept,
                        question,
                        attempt.id,
                        {
                            "level": lv,
                            "leak_check_passed": True,
                            "regenerated": False,
                            "used_fallback": False,
                            "model": MODEL,
                        },
                    )
                )

            # Graded answers: some misses, then (unless revealed/abandoned) a passing one.
            misses = 0 if level == 0 else rng.choice([0, 1, 1, 2])
            if reveal:
                misses = max(misses, rng.choice([0, 1, 2]))
            if abandoned:
                misses = min(misses, 1)
            passes = not reveal and not abandoned
            plan = [
                (rng.uniform(0.2, 0.7), _misconception(rng, concept.name, misc_p))
                for _ in range(misses)
            ]
            if passes:
                plan.append(
                    (
                        rng.uniform(0.8, 1.0),
                        _misconception(rng, concept.name, misc_p) if weak else None,
                    )
                )
            answers: list[Answer] = []
            for i, (score, misc) in enumerate(plan, start=1):
                at = start + (end - start) * (0.5 + 0.45 * i / max(len(plan), 1))
                a = Answer(
                    attempt_id=attempt.id,
                    answer_text=f"[synthetic] answer {i}",
                    rubric_score=Decimal(str(round(score, 2))),
                    misconception=misc,
                    grader_model=MODEL,
                    grader_prompt_version="synthetic",
                    submitted_at=at,
                    graded_at=at,
                )
                session.add(a)
                answers.append(a)
                done = passes and i == len(plan)
                events.append(
                    _event(
                        user.id,
                        "answer_submitted",
                        at,
                        concept,
                        question,
                        attempt.id,
                        {"answer_number": i, "max_hint_level": level},
                    )
                )
                events.append(
                    _event(
                        user.id,
                        "answer_graded",
                        at,
                        concept,
                        question,
                        attempt.id,
                        {
                            "rubric_score": round(score, 2),
                            "completed": done,
                            "max_hint_level": level,
                            "misconception": misc,
                        },
                    )
                )
            if abandoned:
                continue
            best = max((a.rubric_score for a in answers), default=Decimal(0))
            attempt.effective_score = effective_score_for(best, level, reveal)
            attempt.completed_at = end
            if reveal:
                attempt.revealed_at = end
                events.append(
                    _event(
                        user.id,
                        "answer_revealed",
                        end,
                        concept,
                        question,
                        attempt.id,
                        {"max_hint_level": level},
                    )
                )
            last_misc = answers[-1].misconception if answers else None
            completions.append((end, attempt, last_misc))

    session.flush()
    # Mastery is a running average, so replay completions in the order they happened.
    for _, attempt, misc in sorted(completions, key=lambda c: (c[0], c[1].id)):
        question_concept = session.get(Question, attempt.question_id).concept_id
        update_mastery(
            session,
            user_id=user.id,
            concept_id=question_concept,
            effective_score=attempt.effective_score,
            misconception=misc,
        )
    session.add_all(events)
    session.flush()
    return {
        "user_id": user.id,
        "attempts": n_attempts,
        "completed": len(completions),
        "events": len(events),
    }


def main() -> None:
    from app.db import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reset", action="store_true", help="delete the synthetic user first")
    args = parser.parse_args()
    with SessionLocal() as session:
        result = seed(session, reset=args.reset)
        session.commit()
    if result is None:
        print(f'"{DEMO_NAME}" already exists. Use --reset to rebuild it.')
    else:
        print(f"Seeded SYNTHETIC data: {result}  (not real usage; do not present it as such)")


if __name__ == "__main__":
    main()
