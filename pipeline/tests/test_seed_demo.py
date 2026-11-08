"""The synthetic demo data: deterministic, idempotent, tells its story, and is isolated."""

from datetime import date

from app.config import get_settings
from app.models import Attempt, EventRaw, User
from sqlalchemy import func, select, text

from pipeline.quality import run_all
from pipeline.run import run_pipeline
from pipeline.seed_demo import DEMO_NAME, find_demo_user, remove_demo_user, seed

END = date(2026, 3, 29)


def count(session, model, **where):
    return session.scalar(select(func.count()).select_from(model).filter_by(**where))


def test_seed_is_idempotent_without_reset(session):
    first = seed(session, end_date=END)
    assert first and first["attempts"] > 60
    assert seed(session, end_date=END) is None
    assert count(session, User, display_name=DEMO_NAME) == 1
    assert find_demo_user(session).id == first["user_id"]


def test_seed_is_deterministic(session):
    a = seed(session, end_date=END, reset=True)
    b = seed(session, end_date=END, reset=True)
    assert {k: v for k, v in a.items() if k != "user_id"} == {
        k: v for k, v in b.items() if k != "user_id"
    }


def test_reset_removes_only_the_demo_learner(session, fx):
    before = (
        count(session, Attempt, user_id=fx.user.id),
        count(session, EventRaw, user_id=fx.user.id),
    )
    result = seed(session, end_date=END)
    assert count(session, Attempt, user_id=result["user_id"]) > 0
    assert remove_demo_user(session) is True
    assert find_demo_user(session) is None
    assert count(session, Attempt, user_id=result["user_id"]) == 0
    assert count(session, EventRaw, user_id=result["user_id"]) == 0
    after = (
        count(session, Attempt, user_id=fx.user.id),
        count(session, EventRaw, user_id=fx.user.id),
    )
    assert before == after


def test_never_deletes_the_real_demo_user(session, monkeypatch):
    # Pretend the seeded user is the real demo user: it must be invisible to find/remove.
    result = seed(session, end_date=END)
    monkeypatch.setattr(get_settings(), "DEMO_USER_ID", result["user_id"])
    assert find_demo_user(session) is None
    assert remove_demo_user(session) is False
    assert count(session, Attempt, user_id=result["user_id"]) > 0


def test_a_real_user_with_the_same_name_is_not_touched(session, fx):
    fx.user.display_name = DEMO_NAME  # same name, but no synthetic marker document
    session.flush()
    assert find_demo_user(session) is None
    assert remove_demo_user(session) is False
    assert count(session, Attempt, user_id=fx.user.id) == 8


def test_seeded_data_tells_the_story_and_passes_quality_checks(session):
    seed(session, end_date=END)
    conn = session.connection()
    run_pipeline(conn)
    uid = find_demo_user(session).id

    def window(first, last):
        return conn.execute(
            text(
                "SELECT AVG(max_hint_level)::float, AVG(is_independent::int)::float "
                "FROM silver.attempt_facts "
                "WHERE user_id = :u AND status = 'completed' "
                "AND (completed_at AT TIME ZONE 'UTC')::date BETWEEN :a AND :b"
            ),
            {"u": uid, "a": first, "b": last},
        ).one()

    hints_w1, indep_w1 = window(date(2026, 3, 2), date(2026, 3, 8))
    hints_w4, indep_w4 = window(date(2026, 3, 23), date(2026, 3, 29))
    assert hints_w4 < hints_w1 - 0.5  # hint usage trends down
    assert indep_w4 > indep_w1 + 0.3  # independence rises

    gaps = {
        r.concept_name
        for r in conn.execute(
            text("SELECT concept_name, is_gap FROM gold.concept_summary WHERE user_id = :u"),
            {"u": uid},
        )
        if r.is_gap
    }
    assert gaps == {"Window functions", "Correlated subqueries"}  # two concepts stay weak

    assert all(v == [] for v in run_all(conn).values())


def test_every_synthetic_row_is_labelled(session):
    result = seed(session, end_date=END)
    unlabelled = session.scalar(
        select(func.count())
        .select_from(EventRaw)
        .where(
            EventRaw.user_id == result["user_id"], EventRaw.payload["synthetic"].astext != "true"
        )
    )
    assert unlabelled == 0
