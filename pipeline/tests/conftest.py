"""Pipeline test fixtures. Like the backend tests, everything runs inside a transaction that
is rolled back, so the dev database is never changed. (DDL such as DROP SCHEMA is transactional
in Postgres, so even the pipeline's rebuild of silver/gold is undone.) Needs
`alembic upgrade head` first."""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

os.environ["LLM_MODE"] = "fake"  # the pipeline never calls an LLM, but be safe

import pytest  # noqa: E402
from app.db import engine  # noqa: E402
from app.models import (  # noqa: E402
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
from sqlalchemy.orm import Session  # noqa: E402

import pipeline  # noqa: E402,F401  (puts backend/ on sys.path)

DAY1 = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
DAY2 = DAY1 + timedelta(days=1)


@pytest.fixture
def session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def fx(session) -> SimpleNamespace:
    """A small dataset with known answers (see the comments for the expected numbers).

    user, 1 document, 3 concepts, one question each, 8 attempts:
      A1 C1 completed hint0            independent, day1
      A2 C1 completed hint1            independent, day1
      A3 C2 completed hint3, 2 answers NOT independent, day2, misconception "M"
      A4 C2 revealed  hint4            NOT independent, day2, misconception "m!" (same as "M")
      A5 C1 abandoned hint1            not counted anywhere
      A6 C1 in progress                not counted anywhere
      A7 C3 completed hint0            independent, day2, misconception "X"
      A8 C3 completed hint0            independent, day2, misconception "X"  (repeat -> gap)
    => completed 6, independent 4 (0.667); day1: 2 completed; day2: 4 completed.
    """
    user = User(display_name="Pipeline Test Learner")
    session.add(user)
    session.flush()
    doc = Document(user_id=user.id, title="Fixture doc", source_type="text", content_hash="fx")
    session.add(doc)
    session.flush()
    concepts, questions = {}, {}
    for key in ("C1", "C2", "C3"):
        c = Concept(document_id=doc.id, name=f"Concept {key}", definition="d")
        session.add(c)
        session.flush()
        q = Question(
            concept_id=c.id,
            question_type="explain",
            prompt="p",
            rubric=["a"],
            model="m",
            prompt_version="v",
        )
        session.add(q)
        session.flush()
        concepts[key], questions[key] = c, q

    def attempt(key, status, hint, start, minutes=5, revealed=False, effective=None, answers=()):
        a = Attempt(
            user_id=user.id,
            question_id=questions[key].id,
            status=status,
            max_hint_level=hint,
            started_at=start,
            completed_at=start + timedelta(minutes=minutes) if status == "completed" else None,
            revealed_at=start + timedelta(minutes=minutes) if revealed else None,
            effective_score=effective,
        )
        session.add(a)
        session.flush()
        for lvl in range(1, hint + 1):
            session.add(
                HintRequest(
                    attempt_id=a.id, level=lvl, hint_text="h", model="m", prompt_version="v"
                )
            )
        for i, (score, misc) in enumerate(answers):
            session.add(
                Answer(
                    attempt_id=a.id,
                    answer_text="t",
                    rubric_score=Decimal(str(score)),
                    misconception=misc,
                    graded_at=start + timedelta(minutes=i + 1),
                )
            )
        session.flush()
        return a

    at = SimpleNamespace(
        a1=attempt("C1", "completed", 0, DAY1, effective=Decimal("0.90"), answers=[(0.9, None)]),
        a2=attempt(
            "C1",
            "completed",
            1,
            DAY1 + timedelta(hours=1),
            effective=Decimal("0.77"),
            answers=[(0.9, None)],
        ),
        a3=attempt(
            "C2",
            "completed",
            3,
            DAY2,
            minutes=10,
            effective=Decimal("0.34"),
            answers=[(0.4, "M"), (0.85, "M")],
        ),
        a4=attempt(
            "C2",
            "completed",
            4,
            DAY2 + timedelta(hours=1),
            revealed=True,
            effective=Decimal("0.00"),
            answers=[(0.3, "m!")],
        ),
        a5=attempt("C1", "abandoned", 1, DAY2 + timedelta(hours=2)),
        a6=attempt("C1", "in_progress", 0, DAY2 + timedelta(hours=3)),
        a7=attempt(
            "C3",
            "completed",
            0,
            DAY2 + timedelta(hours=4),
            effective=Decimal("0.90"),
            answers=[(0.9, "X")],
        ),
        a8=attempt(
            "C3",
            "completed",
            0,
            DAY2 + timedelta(hours=5),
            effective=Decimal("0.90"),
            answers=[(0.9, "X")],
        ),
    )
    for key, mastery in (("C1", "0.900"), ("C2", "0.160"), ("C3", "0.900")):
        session.add(
            ConceptMastery(
                user_id=user.id,
                concept_id=concepts[key].id,
                mastery=Decimal(mastery),
                attempt_count=2,
            )
        )

    def event(event_type, attempt_obj=None, **payload):
        session.add(
            EventRaw(
                user_id=user.id,
                event_type=event_type,
                document_id=doc.id,
                attempt_id=attempt_obj.id if attempt_obj else None,
                payload=payload,
            )
        )

    event("concepts_extracted", success=True)
    event("concepts_extracted", success=False, error="boom")  # failed: must be ignored
    event("concepts_extracted", success=False, error="boom")
    all_attempts = [at.a1, at.a2, at.a3, at.a4, at.a5, at.a6, at.a7, at.a8]
    for a in all_attempts:
        event("question_served", a)
    event("answer_submitted", at.a1)
    event("answer_submitted", at.a3)
    event("answer_submitted", at.a3)  # same attempt twice: counts once
    event("answer_submitted", at.a4)
    event("answer_graded", at.a3, completed=False)
    for a in (at.a1, at.a2, at.a3, at.a7, at.a8):
        event("answer_graded", a, completed=True)
    event("answer_revealed", at.a4)
    session.flush()
    return SimpleNamespace(user=user, doc=doc, concepts=concepts, **vars(at))
