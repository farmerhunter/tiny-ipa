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

from app.db import get_connection  # noqa: E402
from app.main import app  # noqa: E402
from app.services.db_schema import init_db  # noqa: E402
from app.services.db_store import get_settings  # noqa: E402
from tests.auth_helpers import authenticated_client, bootstrap_owner_user  # noqa: E402

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
    bootstrap_owner_user(db_path)
    yield db_path
    db_mod.DEFAULT_DB_PATH = orig


@pytest.fixture(name="client")
def client_fixture(seeded_db: str) -> TestClient:
    return authenticated_client(TestClient(app))


class TestSettingsApi:
    """Integration tests for GET/PUT /api/settings."""

    def test_get_returns_defaults(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["primary_accent"] == "US"
        assert data["daily_word_count"] == 10
        assert data["show_translation"] is True
        assert data["learner_level"] == "entry"
        assert data["ui_language"] == "zh-CN"
        assert data["focus_phonemes"] == []

    def test_put_updates_and_persists(self, client, seeded_db):
        resp = client.put("/api/settings", json={
            "daily_word_count": 5,
            "show_translation": False,
            "learner_level": "mid",
            "ui_language": "en-US",
            "focus_phonemes": ["/ʃ/", " /ɪ/ "],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["daily_word_count"] == 5
        assert data["show_translation"] is False
        assert data["learner_level"] == "mid"
        assert data["ui_language"] == "en-US"
        assert data["focus_phonemes"] == ["/ʃ/", "/ɪ/"]
        # Other fields unchanged
        assert data["primary_accent"] == "US"

        # Verify persistence
        conn = get_connection(seeded_db)
        s = get_settings(conn, "default")
        conn.close()
        assert s is not None
        assert s.daily_word_count == 5
        assert s.show_translation is False
        assert s.learner_level == "mid"
        assert s.ui_language == "en-US"
        assert s.focus_phonemes == ["/ʃ/", "/ɪ/"]

    @pytest.mark.parametrize("ui_language", ["zh-CN", "en-US"])
    def test_put_accepts_supported_ui_languages(self, client, ui_language):
        resp = client.put("/api/settings", json={"ui_language": ui_language})
        assert resp.status_code == 200
        assert resp.json()["ui_language"] == ui_language

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

    def test_put_accepts_choose_word_practice_mode(self, client):
        resp = client.put("/api/settings", json={"practice_mode": "choose_word"})
        assert resp.status_code == 200
        assert resp.json()["practice_mode"] == "choose_word"

    def test_put_invalid_learner_level(self, client):
        resp = client.put("/api/settings", json={"learner_level": "advanced"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "SETTINGS_INVALID"

    def test_put_invalid_ui_language(self, client):
        resp = client.put("/api/settings", json={"ui_language": "fr-FR"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "SETTINGS_INVALID"

    @pytest.mark.parametrize(
        "payload",
        [
            {"focus_phonemes": "/ʃ/"},
            {"focus_phonemes": ["/ʃ/", ""]},
            {"focus_phonemes": ["/ʃ/", 123]},
            {"focus_phonemes": None},
        ],
    )
    def test_put_invalid_focus_phonemes(self, client, payload):
        resp = client.put("/api/settings", json=payload)
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
            bootstrap_owner_user(db_path)
            authenticated_client(c)
            resp = c.get("/api/settings")
            assert resp.status_code == 200
            assert resp.json()["daily_word_count"] == 10
            assert resp.json()["learner_level"] == "entry"
            assert resp.json()["ui_language"] == "zh-CN"
            assert resp.json()["focus_phonemes"] == []
        finally:
            db_mod.DEFAULT_DB_PATH = orig
