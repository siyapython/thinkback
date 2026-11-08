"""Analytics: run the pipeline and read its silver/gold tables.

The SQL itself lives in the repo-root `pipeline/` folder (so it can run without the API too).
This module only wires it into the backend. All reads are parameterised raw SQL against the
tables the pipeline builds; nothing here computes a metric a second time.
"""

import sys

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import REPO_ROOT, get_settings
from app.models import Document, User

SYNTHETIC_HASH_PREFIX = "synthetic-demo"


def refresh(session: Session) -> dict[str, int]:
    """Full-refresh silver and gold in one transaction. Returns {table: row_count}."""
    if str(REPO_ROOT) not in sys.path:  # `pipeline/` sits next to `backend/`, not inside it
        sys.path.insert(0, str(REPO_ROOT))
    from pipeline.run import run_pipeline

    try:
        counts = run_pipeline(session.connection())
        session.commit()
    except Exception:
        session.rollback()
        raise
    return counts


def pipeline_ready(session: Session) -> bool:
    return bool(
        session.scalar(
            text(
                "SELECT to_regclass('silver.attempt_facts') IS NOT NULL"
                " AND to_regclass('gold.learner_daily') IS NOT NULL"
                " AND to_regclass('gold.concept_summary') IS NOT NULL"
                " AND to_regclass('gold.funnel') IS NOT NULL"
            )
        )
    )


def is_synthetic(session: Session, user_id: int) -> bool:
    hashes = session.scalars(select(Document.content_hash).where(Document.user_id == user_id))
    return any(h.startswith(SYNTHETIC_HASH_PREFIX) for h in hashes)


def selectable_users(session: Session) -> list[dict]:
    """The real demo user, plus any synthetic user (found by its marker document)."""
    demo_id = get_settings().DEMO_USER_ID
    out = []
    for user in session.scalars(select(User).order_by(User.id)):
        synthetic = is_synthetic(session, user.id)
        if user.id == demo_id or synthetic:
            out.append(
                {"id": user.id, "display_name": user.display_name, "is_synthetic": synthetic}
            )
    return out


def _rows(session: Session, sql: str, user_id: int) -> list[dict]:
    return [dict(r) for r in session.execute(text(sql), {"u": user_id}).mappings()]


def overview(session: Session, user: User) -> dict:
    synthetic = is_synthetic(session, user.id)
    base = {"user_id": user.id, "display_name": user.display_name, "is_synthetic": synthetic}
    empty_headline = {
        "completed_attempts": 0,
        "independent_attempts": 0,
        "independence_rate": None,
        "avg_hint_level": None,
        "reveal_rate": None,
        "avg_effective_score": None,
        "gap_concepts": 0,
    }
    if not pipeline_ready(session):
        return {
            **base,
            "pipeline_ready": False,
            "headline": empty_headline,
            "learner_daily": [],
            "concept_summary": [],
            "funnel": [],
        }

    # Headline numbers come from silver (not from averaging daily rates, which would weight
    # a 1-attempt day the same as a 10-attempt day).
    headline = _rows(
        session,
        """
        SELECT COUNT(*) AS completed_attempts,
               COUNT(*) FILTER (WHERE is_independent) AS independent_attempts,
               ROUND(AVG(is_independent::int), 3) AS independence_rate,
               ROUND(AVG(max_hint_level), 3) AS avg_hint_level,
               ROUND(AVG(revealed::int), 3) AS reveal_rate,
               ROUND(AVG(effective_score), 3) AS avg_effective_score
        FROM silver.attempt_facts WHERE user_id = :u AND status = 'completed'""",
        user.id,
    )[0]
    concepts = _rows(
        session,
        """SELECT concept_id, concept_name, document_id, attempts, avg_effective_score,
                  avg_max_hint_level, reveal_count, mastery, is_gap
           FROM gold.concept_summary WHERE user_id = :u ORDER BY concept_name""",
        user.id,
    )
    return {
        **base,
        "pipeline_ready": True,
        "headline": {**headline, "gap_concepts": sum(1 for c in concepts if c["is_gap"])},
        "learner_daily": _rows(
            session,
            """SELECT day, attempts_completed, independence_rate, avg_hint_level, reveal_rate,
                      avg_effective_score
               FROM gold.learner_daily WHERE user_id = :u ORDER BY day""",
            user.id,
        ),
        "concept_summary": concepts,
        "funnel": _rows(
            session,
            """SELECT document_id, document_title, concepts_extracted, question_served,
                      answer_submitted, completed, revealed
               FROM gold.funnel WHERE user_id = :u ORDER BY document_id""",
            user.id,
        ),
    }
