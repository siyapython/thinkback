from app.config import get_settings


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "llm_mode": "fake"}


def test_health_reports_real_llm_mode(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "LLM_MODE", "real")
    assert client.get("/health").json() == {"status": "ok", "llm_mode": "real"}


def test_health_never_exposes_the_api_key(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "ANTHROPIC_API_KEY", "sk-secret-value")
    assert "sk-secret-value" not in client.get("/health").text


def test_cors_allows_vite_dev_origin(client):
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
