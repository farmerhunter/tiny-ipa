"""Tests for GET/PUT /api/settings."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from import_words import import_words  # noqa: E402
from app.main import app  # noqa: E402
from app.db import get_connection  # noqa: E402
from app.services.db_schema import init_db  # noqa: E402
from app.services.db_store import get_settings  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTENT_SAMPLE = FIXTURES / "content_sample.json"
PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"


@pytest.fixture(name="seeded_db")
def seeded_db_fixture(tmp_path: Path) -> str:
    """Database with imported content and default settings."""
    db_path = str(tmp_path / "test.sqlite")
    import_words(source_path=CONTENT_SAMPLE, phonemes_path=PHONEMES_PATH, db_path=db_path)
    import app.db as db_mod
    orig = db_mod.DEFAULT_DB_PATH
    db_mod.DEFAULT_DB_PATH = db_path
    yield db_path
    db_mod.DEFAULT_DB_PATH = orig


@pytest.fixture(name="client")
def client_fixture(seeded_db: str) -> TestClient:
    return TestClient(app)


class TestSettingsApi:
    """Integration tests for GET/PUT /api/settings."""

    def test_get_returns_defaults(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["primary_accent"] == "US"
        assert data["daily_word_count"] == 10
        assert data["show_translation"] is True

    def test_put_updates_and_persists(self, client, seeded_db):
        resp = client.put("/api/settings", json={
            "daily_word_count": 5,
            "show_translation": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["daily_word_count"] == 5
        assert data["show_translation"] is False
        # Other fields unchanged
        assert data["primary_accent"] == "US"

        # Verify persistence
        conn = get_connection(seeded_db)
        s = get_settings(conn, "default")
        conn.close()
        assert s is not None
        assert s.daily_word_count == 5
        assert s.show_translation is False

    def test_put_invalid_daily_word_count(self, client):
        resp = client.put("/api/settings", json={"daily_word_count": 100})
        assert resp.status_code == 400
        data = resp.json()
        assert data["detail"]["error"] == "SETTINGS_INVALID"

    def test_put_invalid_accent(self, client):
        resp = client.put("/api/settings", json={"primary_accent": "JP"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "SETTINGS_INVALID"

    def test_put_invalid_practice_mode(self, client):
        resp = client.put("/api/settings", json={"practice_mode": "random"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "SETTINGS_INVALID"

    def test_put_empty_body_noop(self, client):
        """Empty body is accepted — no fields changed."""
        resp = client.put("/api/settings", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["daily_word_count"] == 10

    def test_get_empty_db(self, tmp_path, monkeypatch):
        """Settings GET returns defaults even without import."""
        db_path = str(tmp_path / "empty.sqlite")
        conn = get_connection(db_path)
        init_db(conn)
        conn.close()
        import app.db as db_mod
        orig = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            c = TestClient(app)
            resp = c.get("/api/settings")
            assert resp.status_code == 200
            assert resp.json()["daily_word_count"] == 10
        finally:
            db_mod.DEFAULT_DB_PATH = orig
