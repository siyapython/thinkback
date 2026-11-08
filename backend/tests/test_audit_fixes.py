"""Regression tests for the leaks the audit found (see docs/AUDIT.md, item (a))."""

from app.config import get_settings
from app.models import Question
from tests.practice_helpers import answer, good_answer, grade_json, setup_attempt


def test_a_feedback_quoting_a_hidden_misconception_is_replaced(client, session, llm):
    """The grader sees the misconception list. If it echoes one back in the feedback shown to
    the student, that must be caught just like a leaked rubric point."""
    s = setup_attempt(client)
    misconception = session.get(Question, s["question_id"]).misconceptions[0]
    llm._script = [
        grade_json(0.2, misconception=misconception, feedback=f"Careful: {misconception}.")
    ]
    r = answer(client, s["attempt_id"], "no idea")
    assert r.status_code == 201
    assert misconception.lower() not in r.text.lower()


def test_a_analytics_overview_does_not_return_misconception_text(
    client, session, user, monkeypatch
):
    monkeypatch.setattr(get_settings(), "DEMO_USER_ID", user.id)
    s = setup_attempt(client)
    misconception = session.get(Question, s["question_id"]).misconceptions[0]
    # a wrong-but-honest answer: the fake grader records the hidden misconception on it,
    # then the student gives up (reveal completes the attempt)
    answer(client, s["attempt_id"], "no idea")
    client.post(f"/attempts/{s['attempt_id']}/reveal")
    client.post("/analytics/refresh")
    r = client.get("/analytics/overview")
    assert r.status_code == 200 and r.json()["concept_summary"]
    assert misconception.lower() not in r.text.lower()


def test_a_revealed_question_cannot_be_retried_with_the_revealed_rubric(client, session):
    """Reveal shows the rubric. Starting a fresh attempt on the same question and pasting that
    rubric back would earn full marks, so a revealed question is closed for new attempts."""
    s = setup_attempt(client)
    revealed = client.post(f"/attempts/{s['attempt_id']}/reveal")
    assert revealed.status_code == 200
    retry = client.post(f"/questions/{s['question_id']}/attempts")
    assert retry.status_code == 409
    assert "new question" in retry.json()["detail"].lower()
    assert good_answer(session, s["question_id"]) not in retry.text
    # a brand-new question on the same concept is fine
    fresh = client.post(f"/concepts/{s['concept_id']}/questions").json()
    assert client.post(f"/questions/{fresh['id']}/attempts").status_code == 201
