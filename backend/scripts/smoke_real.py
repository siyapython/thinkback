"""End-to-end smoke test against the REAL Anthropic API.

Run from backend/ (uses your .env for the key; nothing secret is ever printed):

    LLM_MODE=real python scripts/smoke_real.py

It creates a tiny throwaway document for the demo user, extracts concepts, generates one
question, grades one answer and requests one hint, prints short summaries, then deletes
everything it created (even if a step fails). Costs a few cents.
Use --allow-fake to exercise the script itself against the offline fake client.
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Attempt, Concept, Document, EventRaw, Question  # noqa: E402
from app.services.attempts import start_attempt, submit_answer  # noqa: E402
from app.services.extraction import extract_concepts  # noqa: E402
from app.services.hints import request_hint  # noqa: E402
from app.services.ingest import ingest_text  # noqa: E402
from app.services.llm import get_llm_client  # noqa: E402
from app.services.questions import generate_question  # noqa: E402

NOTES = """\
A primary key is a column (or set of columns) whose values uniquely identify each row in a table.
A primary key can never be NULL and can never repeat within the table.

A foreign key is a column in one table that refers to the primary key of another table. It lets
the database enforce that a row cannot point at something that does not exist.

An index is a separate data structure that lets the database find rows by a column's value
without scanning the whole table. Indexes make reads faster but make writes slightly slower,
because the index must be updated too.

A transaction groups several statements so that they either all take effect or none do. This
property is called atomicity. If any statement fails, the database rolls the whole group back.
"""


def say(message: str) -> None:
    print(message, flush=True)


def cleanup(document_id: int) -> None:
    with SessionLocal() as session:
        question_ids = select(Question.id).join(Concept).where(Concept.document_id == document_id)
        session.execute(delete(Attempt).where(Attempt.question_id.in_(question_ids)))
        session.execute(delete(EventRaw).where(EventRaw.document_id == document_id))
        session.execute(delete(Document).where(Document.id == document_id))  # cascades the rest
        session.commit()


def main() -> int:
    settings = get_settings()
    if settings.LLM_MODE != "real" and "--allow-fake" not in sys.argv:
        say("Refusing to run: LLM_MODE is not 'real'.")
        say("Run:  LLM_MODE=real python scripts/smoke_real.py")
        return 2
    say(f"mode={settings.LLM_MODE} strong={settings.MODEL_STRONG} fast={settings.MODEL_FAST}")
    llm = get_llm_client()
    user_id = settings.DEMO_USER_ID
    document_id: int | None = None
    try:
        with SessionLocal() as session:
            doc = ingest_text(
                session,
                user_id=user_id,
                title=f"smoke test {uuid.uuid4().hex[:8]}",
                text=NOTES + f"\n(run {uuid.uuid4().hex})",
            )
            document_id = doc.id
            say(f"1. uploaded document: status={doc.status}")

            result = extract_concepts(session, doc, llm, user_id)
            concepts = list(session.scalars(select(Concept).where(Concept.document_id == doc.id)))
            say(f"2. extracted {len(concepts)} concepts (model={result.model})")
            say("   e.g. " + ", ".join(c.name for c in concepts[:4]))

            question = generate_question(session, concepts[0], llm, None)
            say(
                f"3. question ({question.question_type}, model={question.model}, "
                f"{len(question.rubric)} rubric points): {question.prompt[:120]}"
            )

            attempt = start_attempt(session, question, user_id)
            _, grade, rubric_size, replaced = submit_answer(
                session, attempt, "I'm not sure, maybe it has something to do with tables?", llm
            )
            say(
                f"4. graded a weak answer: score={grade.rubric_score} of 1.0, "
                f"{len(grade.points_covered)}/{rubric_size} points covered, "
                f"feedback_replaced={replaced}"
            )
            say(f"   feedback: {grade.feedback[:140]}")

            hint = request_hint(session, attempt, llm)
            say(
                f"5. hint level {hint.level} (leak_check_passed={hint.leak_check_passed}, "
                f"regenerated={hint.regenerated}, model={hint.model}): {hint.hint_text[:160]}"
            )
        say("OK: all steps worked")
        return 0
    except HTTPException as exc:
        say(f"FAILED: HTTP {exc.status_code}: {exc.detail}")
        return 1
    except Exception as exc:  # noqa: BLE001 - report the type and message only
        say(f"FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if document_id is not None:
            cleanup(document_id)
            say("cleanup: deleted the test document and everything created from it")


if __name__ == "__main__":
    raise SystemExit(main())
