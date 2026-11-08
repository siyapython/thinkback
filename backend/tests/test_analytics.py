"""Analytics API. Offline: fake LLM mode, no network, data built directly in the database."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.config import get_settings
from app.models import Attempt, Concept, ConceptMastery, Document, EventRaw, Question, User


@pytest.fixture
def seeded(session, user):
    """The test user (made the 'demo user' for this test) with 3 completed attempts."""
    doc = Document(user_id=user.id, title="Doc", source_type="text", content_hash="h")
    session.add(doc)
    session.flush()
    concept = Concept(document_id=doc.id, name="Joins", definition="d")
    session.add(concept)
    session.flush()
    q = Question(
        concept_id=concept.id,
        question_type="explain",
        prompt="p",
        rubric=["a"],
        model="m",
        prompt_version="v",
    )
    session.add(q)
    session.flush()
    t0 = datetime(2026, 3, 2, 10, tzinfo=UTC)
    for i, (hint, revealed) in enumerate([(0, False), (1, False), (3, True)]):
        done = t0 + timedelta(minutes=i * 10 + 5)
        session.add(
            Attempt(
                user_id=user.id,
                question_id=q.id,
                status="completed",
                max_hint_level=hint,
                started_at=t0 + timedelta(minutes=i * 10),
                completed_at=done,
                revealed_at=done if revealed else None,
                effective_score=Decimal("0.50"),
            )
        )
    session.add(
        ConceptMastery(
            user_id=user.id, concept_id=concept.id, mastery=Decimal("0.5"), attempt_count=3
        )
    )
    for ok in (False, True):  # one failed and one good extraction
        session.add(
            EventRaw(
                user_id=user.id,
                event_type="concepts_extracted",
                document_id=doc.id,
                payload={"success": ok},
            )
        )
    session.flush()
    return doc


@pytest.fixture
def as_demo_user(user, monkeypatch):
    monkeypatch.setattr(get_settings(), "DEMO_USER_ID", user.id)


def test_overview_before_pipeline_has_run_is_an_empty_not_an_error(client, session, as_demo_user):
    session.execute(text("DROP SCHEMA IF EXISTS gold CASCADE"))
    session.execute(text("DROP SCHEMA IF EXISTS silver CASCADE"))
    r = client.get("/analytics/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline_ready"] is False
    assert body["learner_daily"] == [] and body["funnel"] == []


def test_refresh_returns_row_counts_and_overview_reads_them(client, seeded, as_demo_user):
    r = client.post("/analytics/refresh")
    assert r.status_code == 200
    tables = r.json()["tables"]
    assert set(tables) == {
        "silver.attempt_facts",
        "gold.learner_daily",
        "gold.concept_summary",
        "gold.funnel",
    }
    assert tables["silver.attempt_facts"] >= 3

    body = client.get("/analytics/overview").json()  # defaults to the demo user
    assert body["pipeline_ready"] is True
    assert body["headline"]["completed_attempts"] == 3
    assert body["headline"]["reveal_rate"] == pytest.approx(0.333)
    assert body["learner_daily"][0]["attempts_completed"] == 3
    (concept,) = body["concept_summary"]
    assert concept["concept_name"] == "Joins" and concept["is_gap"] is True  # 0.5 < 0.6, 3 attempts
    assert body["headline"]["gap_concepts"] == 1
    (funnel,) = body["funnel"]
    assert funnel["concepts_extracted"] == 1  # the failed extraction is ignored


def test_headline_independence_matches_the_existing_metrics_endpoint(client, seeded, as_demo_user):
    client.post("/analytics/refresh")
    metric = client.get("/metrics/independence").json()
    headline = client.get("/analytics/overview").json()["headline"]
    assert headline["completed_attempts"] == metric["completed_attempts"] == 3
    assert headline["independent_attempts"] == metric["independent_attempts"] == 2
    assert headline["independence_rate"] == metric["independence_rate"]


def test_users_lists_demo_user_and_synthetic_user_only(client, session, user, as_demo_user):
    other = User(display_name="Somebody else")
    session.add(other)
    session.flush()
    synthetic = User(display_name="Demo Learner (synthetic)")
    session.add(synthetic)
    session.flush()
    session.add(
        Document(
            user_id=synthetic.id, title="S", source_type="text", content_hash="synthetic-demo-v1"
        )
    )
    session.flush()
    listed = {u["id"]: u for u in client.get("/analytics/users").json()}
    assert listed[user.id]["is_synthetic"] is False
    assert listed[synthetic.id]["is_synthetic"] is True
    assert other.id not in listed
    assert client.get(f"/analytics/overview?user_id={other.id}").status_code == 404
    assert client.get(f"/analytics/overview?user_id={synthetic.id}").status_code == 200


def test_unknown_user_is_404(client):
    assert client.get("/analytics/overview?user_id=999999999").status_code == 404


def test_analytics_never_calls_the_llm(client, llm):
    assert client.post("/analytics/refresh").status_code == 200
    assert client.get("/analytics/overview").status_code in (200, 404)
    assert llm.calls == []
