"""Tests for the health-check endpoint."""

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app import config
from app import db as db_mod
from app.main import app, create_app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "content_version" in data
    assert "db_ready" in data


def test_enabled_wal_anchor_starts_without_http_traffic_and_closes_with_app(
    tmp_path: Path, monkeypatch,
):
    database = tmp_path / "tiny-ipa.sqlite"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    shm = Path(f"{database}-shm")
    assert not shm.exists()

    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", str(database))
    monkeypatch.setenv("TINY_IPA_KEEP_WAL_ANCHOR", "true")
    anchored_app = create_app()

    with TestClient(anchored_app):
        assert shm.is_file()
        reader = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            assert reader.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 0
        finally:
            reader.close()
        assert shm.is_file()

    assert not shm.exists()


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
