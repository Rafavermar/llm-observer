import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSERVER_DB_PATH", str(tmp_path / "observer.db"))
    with TestClient(app) as test_client:
        yield test_client


def test_sync_users_upserts_directory_records(client: TestClient) -> None:
    response = client.post(
        "/api/users/sync",
        json={
            "source": "pytest",
            "users": [
                {
                    "user_id": "ana@company.com",
                    "user_name": "Ana Example",
                    "role": "developer",
                    "team": "platform",
                    "department": "engineering",
                    "active": True,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["synced"] == 1
    assert body["users"][0]["source"] == "pytest"

    users = client.get("/api/users", params={"query": "ana"}).json()
    assert len(users) == 1
    assert users[0]["team"] == "platform"


def test_issue_virtual_key_returns_key_once_and_list_masks_secret(client: TestClient) -> None:
    client.post("/api/users/sync/demo")

    issued = client.post(
        "/api/virtual-keys",
        json={
            "user_id": "demo.user@company.com",
            "app": "sample-app",
            "workflow": "demo-call",
            "models": ["gpt-4o-mini"],
            "max_budget_usd": 5,
        },
    )

    assert issued.status_code == 200
    issued_body = issued.json()
    assert issued_body["key"].startswith("sk-obsv-")
    assert issued_body["source"] == "observer_local"
    assert issued_body["key_prefix"]
    assert issued_body["litellm_generate_payload"]["user_id"] == "demo.user@company.com"

    listed = client.get("/api/virtual-keys").json()
    assert len(listed) == 1
    assert "key" not in listed[0]
    assert listed[0]["key_prefix"] == issued_body["key_prefix"]


def test_issue_virtual_key_requires_synced_user(client: TestClient) -> None:
    response = client.post(
        "/api/virtual-keys",
        json={"user_id": "missing@company.com"},
    )

    assert response.status_code == 404
