"""The transforms produce the numbers we expect from the hand-built fixture."""

from decimal import Decimal

from sqlalchemy import text

from pipeline.run import TABLES, run_pipeline


def build(session):
    return run_pipeline(session.connection())


def rows(session, sql, **params):
    return session.connection().execute(text(sql), params).mappings().all()


def test_runner_returns_row_counts_for_every_table(session, fx):
    counts = build(session)
    assert set(counts) == set(TABLES)
    assert counts["gold.learner_daily"] >= 2  # fixture user has two days


def test_full_refresh_is_repeatable(session, fx):
    assert build(session) == build(session)


def test_silver_one_row_per_attempt_with_expected_fields(session, fx):
    build(session)
    r = {
        row["attempt_id"]: row
        for row in rows(
            session, "SELECT * FROM silver.attempt_facts WHERE user_id = :u", u=fx.user.id
        )
    }
    assert len(r) == 8
    assert r[fx.a1.id]["is_independent"] is True
    assert r[fx.a1.id]["seconds_to_complete"] == 300
    assert r[fx.a3.id]["is_independent"] is False  # hint level 3
    assert r[fx.a3.id]["answer_count"] == 2
    assert r[fx.a3.id]["hint_count"] == 3
    assert r[fx.a3.id]["rubric_score"] == Decimal("0.85")  # last graded answer
    assert r[fx.a4.id]["revealed"] is True and r[fx.a4.id]["is_independent"] is False
    # Abandoned / in-progress rows are kept but have no completed-only metrics.
    for a in (fx.a5, fx.a6):
        assert r[a.id]["is_independent"] is None
        assert r[a.id]["seconds_to_complete"] is None


def test_learner_daily(session, fx):
    build(session)
    day1, day2 = rows(
        session,
        "SELECT * FROM gold.learner_daily WHERE user_id = :u ORDER BY day",
        u=fx.user.id,
    )
    assert (day1["attempts_completed"], day1["independence_rate"]) == (2, Decimal("1.000"))
    assert day1["avg_hint_level"] == Decimal("0.500")
    assert day1["reveal_rate"] == 0
    assert day1["avg_effective_score"] == Decimal("0.835")
    assert (day2["attempts_completed"], day2["independence_rate"]) == (4, Decimal("0.500"))
    assert day2["reveal_rate"] == Decimal("0.250")


def test_concept_summary_and_gap_rules(session, fx):
    build(session)
    r = {
        row["concept_id"]: row
        for row in rows(
            session, "SELECT * FROM gold.concept_summary WHERE user_id = :u", u=fx.user.id
        )
    }
    c1, c2, c3 = (r[fx.concepts[k].id] for k in ("C1", "C2", "C3"))
    assert c1["attempts"] == 2 and c1["is_gap"] is False  # abandoned/in-progress not counted
    assert c2["attempts"] == 2 and c2["reveal_count"] == 1
    assert c2["is_gap"] is True  # low mastery after 2 attempts
    assert c2["top_misconception"] in ("M", "m!")
    assert c3["mastery"] == Decimal("0.900") and c3["is_gap"] is True  # same misconception twice


def test_funnel_counts_attempts_not_events_and_ignores_failed_extraction(session, fx):
    build(session)
    (f,) = rows(session, "SELECT * FROM gold.funnel WHERE user_id = :u", u=fx.user.id)
    assert f["concepts_extracted"] == 1  # 3 events, 2 of them failed
    assert f["question_served"] == 8
    assert f["answer_submitted"] == 3  # a1, a3 (twice), a4
    assert f["completed"] == 6  # graded-completed a1 a2 a3 a7 a8 + revealed a4
    assert f["revealed"] == 1
