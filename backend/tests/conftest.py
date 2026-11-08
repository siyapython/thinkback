import os

# Tests must never reach the network, whatever the developer's .env says.
os.environ["LLM_MODE"] = "fake"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import engine, get_session  # noqa: E402
from app.deps import current_user_id, llm_client  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.services.llm import FakeLLMClient  # noqa: E402


@pytest.fixture
def session():
    """A session inside an outer transaction that is always rolled back,
    so tests never leave data in the dev database. Needs `alembic upgrade head` first."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def user(session) -> User:
    user = User(display_name="Test Learner")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def client(session, user, llm, tmp_path, monkeypatch) -> TestClient:
    """API client wired to the rolled-back session, a throwaway user, the fake LLM and a
    temporary upload folder."""
    monkeypatch.setattr(get_settings(), "UPLOAD_DIR", tmp_path / "uploads")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[current_user_id] = lambda: user.id
    app.dependency_overrides[llm_client] = lambda: llm
    yield TestClient(app)
    app.dependency_overrides.clear()
