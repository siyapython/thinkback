from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Attempt, ConceptMastery, EventRaw
from app.services.mastery import ema, is_gap, update_mastery
from tests.practice_helpers import (
    answer,
    grade_json,
    make_question,
    rubric_of,
    setup_attempt,
    start_attempt,
    upload_and_extract,
)


def complete_with_score(client, llm, concept_id, score, misconception=None, question_id=None):
    """Run one full attempt that ends with a given rubric score (manual completion)."""
    qid = question_id or make_question(client, concept_id)["id"]
    aid = start_attempt(client, qid)["id"]
    llm._script = [grade_json(score, misconception=misconception)]
    answer(client, aid, "an answer")
    r = client.post(f"/attempts/{aid}/complete")
    assert r.status_code == 200
    llm._script = None
    return r.json()


def mastery_row(client, doc_id, concept_id):
    rows = client.get(f"/documents/{doc_id}/mastery").json()
    return next(r for r in rows if r["concept_id"] == concept_id)


# ---------------------------------------------------------------- reveal
def test_reveal_explains_from_rubric_and_scores_zero(client, session, user):
    s = setup_attempt(client)
    client.post(f"/attempts/{s['attempt_id']}/hints")
    r = client.post(f"/attempts/{s['attempt_id']}/reveal")
    assert r.status_code == 200, r.text
    body = r.json()
    for point in rubric_of(session, s["question_id"]):
        assert point in body["explanation"]
    assert body["attempt"]["status"] == "completed" and body["attempt"]["revealed"] is True
    assert body["attempt"]["effective_score"] == 0.0
    row = session.get(Attempt, s["attempt_id"])
    assert row.revealed_at is not None and row.completed_at is not None
    (event,) = session.scalars(
        select(EventRaw).where(EventRaw.event_type == "answer_revealed")
    ).all()
    assert event.user_id == user.id and event.attempt_id == s["attempt_id"]
    assert event.payload["max_hint_level"] == 1


def test_reveal_zeroes_even_a_good_earlier_score(client, llm):
    s = setup_attempt(client)
    llm._script = [grade_json(0.5)]
    answer(client, s["attempt_id"], "x")
    body = client.post(f"/attempts/{s['attempt_id']}/reveal").json()
    assert body["attempt"]["effective_score"] == 0.0


def test_reveal_twice_and_answer_after_reveal_are_rejected(client):
    s = setup_attempt(client)
    assert client.post(f"/attempts/{s['attempt_id']}/reveal").status_code == 200
    assert client.post(f"/attempts/{s['attempt_id']}/reveal").status_code == 409
    assert answer(client, s["attempt_id"], "late").status_code == 409


# ---------------------------------------------------------------- EMA math
def test_ema_function():
    assert ema(Decimal("0"), Decimal("0.8"), first=True) == Decimal("0.800")
    assert ema(Decimal("0.8"), Decimal("0.4"), first=False) == Decimal("0.680")  # .56 + .12
    assert ema(Decimal("0.68"), Decimal("1.0"), first=False) == Decimal("0.776")  # .476 + .3


def test_update_mastery_first_attempt_then_moving_average(client, session, user):
    info = upload_and_extract(client)
    cid = info["concepts"][3]["id"]
    row = update_mastery(
        session,
        user_id=user.id,
        concept_id=cid,
        effective_score=Decimal("0.80"),
        misconception=None,
    )
    assert (row.mastery, row.attempt_count, row.last_misconception) == (Decimal("0.800"), 1, None)
    row = update_mastery(
        session,
        user_id=user.id,
        concept_id=cid,
        effective_score=Decimal("0.40"),
        misconception="Thinks X",
    )
    assert (row.mastery, row.attempt_count, row.last_misconception) == (
        Decimal("0.680"),
        2,
        "Thinks X",
    )
    row = update_mastery(
        session,
        user_id=user.id,
        concept_id=cid,
        effective_score=Decimal("1.00"),
        misconception=None,
    )
    assert row.mastery == Decimal("0.776")
    assert row.last_misconception == "Thinks X"  # only overwritten when a new one is present


def test_mastery_updates_on_completion_end_to_end(client, llm, session, user):
    info = upload_and_extract(client)
    cid = info["concepts"][0]["id"]
    complete_with_score(client, llm, cid, 0.8)  # 0.8 -> completes (and mastery = .8)
    assert mastery_row(client, info["document_id"], cid)["mastery"] == 0.8
    complete_with_score(client, llm, cid, 0.4)
    row = mastery_row(client, info["document_id"], cid)
    assert row["mastery"] == 0.68 and row["attempt_count"] == 2
    db = session.get(ConceptMastery, (user.id, cid))
    assert db.mastery == Decimal("0.680")


def test_reveal_pulls_mastery_down(client, llm):
    info = upload_and_extract(client)
    cid = info["concepts"][0]["id"]
    complete_with_score(client, llm, cid, 1.0)
    qid = make_question(client, cid)["id"]
    aid = start_attempt(client, qid)["id"]
    client.post(f"/attempts/{aid}/reveal")
    assert mastery_row(client, info["document_id"], cid)["mastery"] == 0.7


def test_mastery_lists_all_active_concepts_even_untouched(client):
    info = upload_and_extract(client)
    rows = client.get(f"/documents/{info['document_id']}/mastery").json()
    assert len(rows) == 10
    assert all(r["mastery"] == 0 and r["attempt_count"] == 0 and not r["is_gap"] for r in rows)
    assert set(rows[0]) == {"concept_id", "name", "mastery", "attempt_count", "is_gap"}
    assert client.get("/documents/999999999/mastery").status_code == 404


# ---------------------------------------------------------------- gap rule
@pytest.mark.parametrize(
    ("mastery", "count", "recent", "gap"),
    [
        ("0.59", 2, [], True),
        ("0.60", 2, [], False),  # boundary: needs to be < 0.6
        ("0.10", 1, [], False),  # only one attempt: not enough evidence
        ("0.90", 3, ["Thinks X", "thinks x!"], True),  # same misconception twice (normalized)
        ("0.90", 3, ["Thinks X", "Thinks Y"], False),
        ("0.90", 3, ["Thinks X", None], False),
        ("0.90", 3, [None, None], False),
        ("0.90", 3, ["Thinks X"], False),
        ("0.90", 4, ["Thinks X", None, "Thinks X"], False),  # not in a row
    ],
)
def test_gap_rule(mastery, count, recent, gap):
    assert is_gap(Decimal(mastery), count, recent) is gap


def test_low_mastery_after_two_attempts_flags_a_gap(client, llm):
    info = upload_and_extract(client)
    cid = info["concepts"][0]["id"]
    complete_with_score(client, llm, cid, 0.5)
    assert mastery_row(client, info["document_id"], cid)["is_gap"] is False  # one attempt only
    complete_with_score(client, llm, cid, 0.2)
    row = mastery_row(client, info["document_id"], cid)
    assert row["mastery"] == 0.41 and row["attempt_count"] == 2 and row["is_gap"] is True


def test_same_misconception_twice_in_a_row_flags_a_gap_even_with_high_mastery(client, llm):
    info = upload_and_extract(client)
    cid = info["concepts"][0]["id"]
    complete_with_score(client, llm, cid, 0.9, misconception="Thinks every entry appears")
    assert mastery_row(client, info["document_id"], cid)["is_gap"] is False
    complete_with_score(client, llm, cid, 0.9, misconception="Thinks every entry appears")
    row = mastery_row(client, info["document_id"], cid)
    assert row["mastery"] == 0.9 and row["is_gap"] is True


def test_a_clean_attempt_in_between_breaks_the_streak(client, llm):
    info = upload_and_extract(client)
    cid = info["concepts"][0]["id"]
    complete_with_score(client, llm, cid, 0.9, misconception="Thinks X")
    complete_with_score(client, llm, cid, 0.9, misconception=None)
    complete_with_score(client, llm, cid, 0.9, misconception="Thinks X")
    assert mastery_row(client, info["document_id"], cid)["is_gap"] is False


# ---------------------------------------------------------------- independence metric
def test_independence_metric(client, llm):
    empty = client.get("/metrics/independence").json()
    assert empty == {"completed_attempts": 0, "independent_attempts": 0, "independence_rate": None}

    info = upload_and_extract(client)
    cid = info["concepts"][0]["id"]
    qid = make_question(client, cid)["id"]

    def attempt():
        return start_attempt(client, qid)["id"]

    a = attempt()  # completed, no hints -> independent
    client.post(f"/attempts/{a}/complete")
    b = attempt()  # one hint -> still independent
    client.post(f"/attempts/{b}/hints")
    client.post(f"/attempts/{b}/complete")
    c = attempt()  # two hints -> not independent
    client.post(f"/attempts/{c}/hints")
    client.post(f"/attempts/{c}/hints")
    client.post(f"/attempts/{c}/complete")
    d = attempt()  # revealed with no hints -> not independent
    client.post(f"/attempts/{d}/reveal")
    attempt()  # still in progress: not counted

    assert client.get("/metrics/independence").json() == {
        "completed_attempts": 4,
        "independent_attempts": 2,
        "independence_rate": 0.5,
    }
