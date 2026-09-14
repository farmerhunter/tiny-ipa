"""Tests for the health-check endpoint."""

from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "content_version" in data
    assert "db_ready" in data


def test_version_returns_only_non_secret_release_identity(monkeypatch):
    monkeypatch.setattr(config, "RELEASE_ID", "release-abc")
    monkeypatch.setattr(config, "RELEASE_COMMIT", "abc123")
    monkeypatch.setattr(config, "RELEASE_TAG", "m14-candidate")

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert set(data) == {"status", "release_id", "commit", "tag"}
    assert data["status"] == "ok"
    assert data["release_id"] == "release-abc"
    assert data["commit"] == "abc123"
    assert data["tag"] == "m14-candidate"


def test_version_uses_local_defaults_and_omits_empty_tag(monkeypatch):
    monkeypatch.setattr(config, "RELEASE_ID", "development")
    monkeypatch.setattr(config, "RELEASE_COMMIT", "development")
    monkeypatch.setattr(config, "RELEASE_TAG", "")

    response = client.get("/api/version")

    assert response.status_code == 200
    data = response.json()
    assert data["release_id"] == "development"
    assert data["commit"] == "development"
    assert data["tag"] is None
