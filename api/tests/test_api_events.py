from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSERVER_DB_PATH", str(tmp_path / "observer.db"))
    with TestClient(app) as test_client:
        yield test_client


def _payload() -> dict:
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "pytest",
        "user_id": "demo.user@company.com",
        "user_name": "Demo User",
        "team": "data-platform",
        "department": "engineering",
        "app": "sample-app",
        "workflow": "demo-call",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "input_tokens": 1234,
        "output_tokens": 220,
        "cached_tokens": 100,
        "latency_ms": 1840,
        "status": "success",
        "retry_count": 0,
        "request_id": "abc123",
        "raw": {"test": True},
    }


def test_post_events_returns_enriched_event(client: TestClient) -> None:
    response = client.post("/api/events", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["id"]
    assert body["total_tokens"] == 1454
    assert body["cache_hit"] is True
    assert body["cost_input"] > 0
    assert body["cost_cached"] > 0
    assert body["total_cost"] > 0
    assert body["model_tier"] == "standard"


def test_get_summary(client: TestClient) -> None:
    client.post("/api/events", json=_payload())

    response = client.get("/api/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_events"] == 1
    assert body["total_tokens"] == 1454
    assert body["active_users"] == 1
    assert 0 <= body["hygiene_score"] <= 100

