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
from app.models import Settings, User  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.services.db_store import create_user, get_settings, upsert_settings  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTENT_SAMPLE = FIXTURES / "content_sample.json"
PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"

ALICE_PASSWORD = "correct horse battery staple"
BOB_PASSWORD = "another correct horse battery staple"


@pytest.fixture(name="isolated_db")
def isolated_db_fixture(tmp_path: Path) -> str:
    db_path = str(tmp_path / "isolation.sqlite")
    import_words(source_path=CONTENT_SAMPLE, phonemes_path=PHONEMES_PATH, db_path=db_path)
    conn = get_connection(db_path)
    _create_user(conn, "alice", "alice", ALICE_PASSWORD)
    _create_user(conn, "bob", "bob", BOB_PASSWORD)
    conn.commit()
    conn.close()

    import app.db as db_mod

    orig = db_mod.DEFAULT_DB_PATH
    db_mod.DEFAULT_DB_PATH = db_path
    yield db_path
    db_mod.DEFAULT_DB_PATH = orig


def _create_user(conn, user_id: str, username: str, password: str) -> None:
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
    upsert_settings(conn, Settings(user_id=user_id, daily_word_count=1))


def _login(username: str, password: str) -> TestClient:
    client = TestClient(app)
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.json()
    return client


def test_settings_are_scoped_to_current_user(isolated_db: str):
    alice = _login("alice", ALICE_PASSWORD)
    bob = _login("bob", BOB_PASSWORD)

    alice.put("/api/settings", json={"daily_word_count": 2, "learner_level": "mid"})
    bob_settings = bob.get("/api/settings").json()

    assert bob_settings["daily_word_count"] == 1
    assert bob_settings["learner_level"] == "entry"

    conn = get_connection(isolated_db)
    try:
        assert get_settings(conn, "alice").daily_word_count == 2
        assert get_settings(conn, "bob").daily_word_count == 1
    finally:
        conn.close()


def test_today_and_progress_are_scoped_to_current_user(isolated_db: str):
    alice = _login("alice", ALICE_PASSWORD)
    bob = _login("bob", BOB_PASSWORD)

    alice_group = alice.post("/api/practice/next-normal").json()
    bob_progress = bob.get("/api/progress").json()
    bob_today = bob.get("/api/today").json()

    assert alice_group["status"] == "in_progress"
    assert bob_progress["total_sessions"] == 0
    assert bob_progress["resumable_normal_groups"] == 0
    assert bob_today["status"] == "idle"


def test_attempt_rejects_other_users_session_item(isolated_db: str):
    alice = _login("alice", ALICE_PASSWORD)
    bob = _login("bob", BOB_PASSWORD)

    alice_group = alice.post("/api/practice/next-normal").json()
    item = alice_group["items"][0]
    resp = bob.post(
        "/api/attempt",
        json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        },
    )

    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "ITEM_NOT_FOUND"


def test_current_group_review_rejects_other_users_source_group(isolated_db: str):
    alice = _login("alice", ALICE_PASSWORD)
    bob = _login("bob", BOB_PASSWORD)

    alice_group = alice.post("/api/practice/next-normal").json()
    resp = bob.post(
        "/api/review/current-group",
        json={"group_id": alice_group["group_id"]},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "GROUP_NOT_FOUND"
