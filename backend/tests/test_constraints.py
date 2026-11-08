import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Answer,
    Attempt,
    Concept,
    Document,
    EventRaw,
    HintRequest,
    Question,
    User,
)


@pytest.fixture
def attempt(session):
    user = User(display_name="Test")
    session.add(user)
    session.flush()
    doc = Document(user_id=user.id, title="t", source_type="text", content_hash="h")
    session.add(doc)
    session.flush()
    concept = Concept(document_id=doc.id, name="JOIN", definition="d")
    session.add(concept)
    session.flush()
    question = Question(
        concept_id=concept.id,
        question_type="explain",
        prompt="p",
        rubric={"points": []},
        model="fake",
        prompt_version="v0",
    )
    session.add(question)
    session.flush()
    attempt = Attempt(user_id=user.id, question_id=question.id)
    session.add(attempt)
    session.flush()
    return attempt


def assert_rejected(session, obj):
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(obj)
        session.flush()


def test_defaults_apply(session, attempt):
    session.refresh(attempt)
    assert attempt.status == "in_progress"
    assert attempt.max_hint_level == 0


def test_hint_level_5_rejected(session, attempt):
    assert_rejected(
        session,
        HintRequest(attempt_id=attempt.id, level=5, hint_text="x", model="m", prompt_version="v"),
    )


def test_hint_level_0_rejected(session, attempt):
    assert_rejected(
        session,
        HintRequest(attempt_id=attempt.id, level=0, hint_text="x", model="m", prompt_version="v"),
    )


def test_valid_hint_level_accepted(session, attempt):
    session.add(
        HintRequest(attempt_id=attempt.id, level=4, hint_text="x", model="m", prompt_version="v")
    )
    session.flush()


def test_attempt_max_hint_level_5_rejected(session, attempt):
    with pytest.raises(IntegrityError), session.begin_nested():
        attempt.max_hint_level = 5
        session.flush()


def test_rubric_score_1_5_rejected(session, attempt):
    assert_rejected(session, Answer(attempt_id=attempt.id, answer_text="a", rubric_score=1.5))


def test_rubric_score_in_range_accepted(session, attempt):
    session.add(Answer(attempt_id=attempt.id, answer_text="a", rubric_score=0.75))
    session.flush()


def test_bad_enum_like_values_rejected(session, attempt):
    assert_rejected(
        session,
        Document(user_id=attempt.user_id, title="t", source_type="docx", content_hash="x"),
    )
    assert_rejected(session, EventRaw(user_id=attempt.user_id, event_type="not_an_event"))


def test_events_raw_accepts_dangling_ids(session, attempt):
    """No foreign keys on events_raw: ids that point at nothing are allowed."""
    session.add(
        EventRaw(user_id=attempt.user_id, event_type="question_served", attempt_id=999_999_999)
    )
    session.flush()
