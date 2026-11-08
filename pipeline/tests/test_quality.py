"""Data quality checks pass on good data and FAIL on bad data."""

from datetime import timedelta

import pytest
from app.models import EVENT_TYPES, EventRaw
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from pipeline.quality import ALLOWED_EVENT_TYPES, CHECKS, run_all, run_check
from pipeline.run import run_pipeline


@pytest.fixture
def built(session, fx):
    conn = session.connection()
    run_pipeline(conn)
    return conn


@pytest.mark.parametrize("name", list(CHECKS))
def test_check_passes_on_clean_data(built, name):
    assert run_check(built, name) == []


def test_allowed_event_types_match_the_backend():
    assert tuple(ALLOWED_EVENT_TYPES) == tuple(EVENT_TYPES)


def test_gold_reconciles_with_silver_per_user(built, fx):
    gold, silver = built.execute(
        text(
            "SELECT (SELECT SUM(attempts_completed) FROM gold.learner_daily WHERE user_id = :u),"
            " (SELECT COUNT(*) FROM silver.attempt_facts WHERE user_id = :u"
            "  AND status = 'completed')"
        ),
        {"u": fx.user.id},
    ).one()
    assert gold == silver == 6


# --- Proof the checks can fail -------------------------------------------------------------


def test_check_catches_completed_before_started(session, fx):
    fx.a1.completed_at = fx.a1.started_at - timedelta(hours=1)  # deliberately bad data
    session.flush()
    conn = session.connection()
    run_pipeline(conn)
    bad = run_check(conn, "completed_not_before_started")
    assert [row["attempt_id"] for row in bad] == [fx.a1.id]
    assert "completed_not_before_started" in {k for k, v in run_all(conn).items() if v}


def test_reconciliation_check_catches_a_lost_gold_row(built, fx):
    built.execute(text("DELETE FROM gold.learner_daily WHERE user_id = :u"), {"u": fx.user.id})
    bad = run_check(built, "gold_daily_reconciles_with_silver")
    assert [row["user_id"] for row in bad] == [fx.user.id]


def test_check_catches_silver_missing_an_attempt(built):
    built.execute(
        text(
            "DELETE FROM silver.attempt_facts WHERE attempt_id = "
            "(SELECT MIN(attempt_id) FROM silver.attempt_facts)"
        )
    )
    assert run_check(built, "silver_count_equals_attempts") != []


def test_check_catches_duplicate_silver_rows(built):
    built.execute(text("ALTER TABLE silver.attempt_facts DROP CONSTRAINT attempt_facts_pkey"))
    built.execute(
        text("INSERT INTO silver.attempt_facts SELECT * FROM silver.attempt_facts LIMIT 1")
    )
    assert run_check(built, "one_silver_row_per_attempt") != []


def test_check_catches_out_of_range_rate(built, fx):
    built.execute(
        text("UPDATE gold.learner_daily SET independence_rate = 1.5 WHERE user_id = :u"),
        {"u": fx.user.id},
    )
    assert run_check(built, "rates_and_mastery_in_unit_range") != []


def test_check_catches_failed_extraction_leaking_into_funnel(built, fx):
    built.execute(
        text("UPDATE gold.funnel SET concepts_extracted = 3 WHERE user_id = :u"), {"u": fx.user.id}
    )
    assert run_check(built, "funnel_excludes_failed_extractions") != []


def test_database_itself_rejects_unknown_event_types(session, fx):
    # The CHECK constraint is the first line of defence; our check is the second.
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(EventRaw(user_id=fx.user.id, event_type="made_up", payload={}))
        session.flush()
