"""Audit item (a), misconceptions: the hidden misconception list must not reach the student
through grader feedback or the analytics dashboard endpoint."""

from app.models import Question
from tests.practice_helpers import answer, grade_json, setup_attempt


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
