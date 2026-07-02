from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from import_words import import_words  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Settings, User  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.services.db_store import create_user, upsert_settings  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTENT_SAMPLE = FIXTURES / "content_sample.json"
PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"


ALICE_PASSWORD = "correct horse battery staple"
BOB_PASSWORD = "another correct horse battery staple"


def _create_user(conn, user_id: str, username: str, password: str, **settings) -> None:
    create_user(
        conn,
        User(
            id=user_id,
            username=username,
            password_hash=hash_password(password),
            is_owner=False,
            is_active=True,
            created_at="2026-07-02T00:00:00+00:00",
            updated_at="2026-07-02T00:00:00+00:00",
        ),
    )
    upsert_settings(conn, Settings(user_id=user_id, **settings))


def _login(username: str, password: str) -> TestClient:
    client = TestClient(app)
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.json()
    return client


def _seed_db(tmp_path: Path, monkeypatch) -> str:
    db_path = str(tmp_path / "settings-effects.sqlite")
    import_words(source_path=CONTENT_SAMPLE, phonemes_path=PHONEMES_PATH, db_path=db_path)
    with get_connection(db_path) as conn:
        _create_user(conn, "alice", "alice", ALICE_PASSWORD, daily_word_count=1)
        _create_user(conn, "bob", "bob", BOB_PASSWORD, daily_word_count=1)

    import app.db as db_mod

    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", db_path)
    return db_path


def test_settings_persist_per_user_and_do_not_leak_between_users(tmp_path, monkeypatch):
    _seed_db(tmp_path, monkeypatch)
    alice = _login("alice", ALICE_PASSWORD)
    bob = _login("bob", BOB_PASSWORD)

    alice_resp = alice.put(
        "/api/settings",
        json={
            "ui_language": "en-US",
            "daily_word_count": 2,
            "learner_level": "mid",
            "focus_phonemes": ["/ʃ/"],
        },
    )
    assert alice_resp.status_code == 200

    bob_settings = bob.get("/api/settings").json()
    assert bob_settings["ui_language"] == "zh-CN"
    assert bob_settings["daily_word_count"] == 1
    assert bob_settings["learner_level"] == "entry"
    assert bob_settings["focus_phonemes"] == []


def test_show_translation_controls_practice_meanings(tmp_path, monkeypatch):
    _seed_db(tmp_path, monkeypatch)
    alice = _login("alice", ALICE_PASSWORD)

    alice.put("/api/settings", json={"show_translation": False, "daily_word_count": 1})
    hidden = alice.post("/api/practice/next-normal").json()
    assert hidden["items"]
    assert all(item["meaning_zh"] is None for item in hidden["items"])

    with get_connection(str(tmp_path / "settings-effects.sqlite")) as conn:
        conn.execute("DELETE FROM session_items")
        conn.execute("DELETE FROM daily_sessions")

    alice.put("/api/settings", json={"show_translation": True})
    shown = alice.post("/api/practice/next-normal").json()
    assert shown["items"]
    assert any(item["meaning_zh"] for item in shown["items"])


def test_accent_compare_setting_controls_eligible_feedback(tmp_path, monkeypatch):
    _seed_db(tmp_path, monkeypatch)
    alice = _login("alice", ALICE_PASSWORD)

    alice.put("/api/settings", json={"show_accent_compare": False, "daily_word_count": 1})
    off = alice.post("/api/practice/next-normal").json()
    assert off["items"]
    assert "accent_compare" not in off["items"][0]

    with get_connection(str(tmp_path / "settings-effects.sqlite")) as conn:
        conn.execute("DELETE FROM session_items")
        conn.execute("DELETE FROM daily_sessions")

    alice.put("/api/settings", json={"show_accent_compare": True})
    on = alice.post("/api/practice/next-normal").json()
    assert on["items"]
    assert on["items"][0]["accent_compare"]["comparison"]["accent"] == "UK"
