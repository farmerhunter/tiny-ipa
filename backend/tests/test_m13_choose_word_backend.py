"""Backend foundation tests for M13 choose_word practice mode."""

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
from tests.auth_helpers import authenticated_client, bootstrap_owner_user  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTENT_SAMPLE = FIXTURES / "content_sample.json"
PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"


def _seed_db(tmp_path: Path, monkeypatch) -> str:
    db_path = str(tmp_path / "m13-choose-word.sqlite")
    import_words(source_path=CONTENT_SAMPLE, phonemes_path=PHONEMES_PATH, db_path=db_path)
    import app.db as db_mod

    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", db_path)
    bootstrap_owner_user(db_path)
    return db_path


def _client() -> TestClient:
    return authenticated_client(TestClient(app))


def test_default_normal_group_remains_choose_ipa(tmp_path, monkeypatch):
    _seed_db(tmp_path, monkeypatch)
    client = _client()

    data = client.post("/api/practice/next-normal").json()

    assert data["items"]
    assert {item["question"]["type"] for item in data["items"]} == {"choose_ipa"}
    first = data["items"][0]
    assert first["display_ipa"] in first["question"]["choices"]


def test_choose_word_setting_creates_word_choice_normal_group(tmp_path, monkeypatch):
    db_path = _seed_db(tmp_path, monkeypatch)
    client = _client()
    settings = client.put("/api/settings", json={"practice_mode": "choose_word"})
    assert settings.status_code == 200
    assert settings.json()["practice_mode"] == "choose_word"

    data = client.post("/api/practice/next-normal").json()

    assert data["items"]
    item = data["items"][0]
    assert item["question"]["type"] == "choose_word"
    assert item["question"]["display_ipa"] == item["display_ipa"]
    assert item["word"] in item["question"]["choices"]
    assert item["display_ipa"] not in item["question"]["choices"]
    assert set(item["question"]["choices"]) == {"ship", "sheep", "cat"}
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT question_type FROM session_items WHERE id = ?",
        (item["session_item_id"],),
    ).fetchone()
    conn.close()
    assert row["question_type"] == "choose_word"


def test_choose_word_attempt_uses_server_word_answer_and_updates_stats(
    tmp_path,
    monkeypatch,
):
    db_path = _seed_db(tmp_path, monkeypatch)
    client = _client()
    client.put("/api/settings", json={"practice_mode": "choose_word"})
    item = client.post("/api/practice/next-normal").json()["items"][0]

    response = client.post(
        "/api/attempt",
        json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["word"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_correct"] is True
    assert data["correct_answer"] == item["word"]
    assert data["updated_phonemes"]
    conn = get_connection(db_path)
    row = conn.execute(
        """
        SELECT question_type, selected_answer, correct_answer, is_correct
        FROM attempts
        WHERE session_item_id = ?
        """,
        (item["session_item_id"],),
    ).fetchone()
    conn.close()
    assert dict(row) == {
        "question_type": "choose_word",
        "selected_answer": item["word"],
        "correct_answer": item["word"],
        "is_correct": 1,
    }


def test_choose_word_attempt_rejects_visible_ipa_as_word_answer(tmp_path, monkeypatch):
    db_path = _seed_db(tmp_path, monkeypatch)
    client = _client()
    client.put("/api/settings", json={"practice_mode": "choose_word"})
    item = client.post("/api/practice/next-normal").json()["items"][0]

    response = client.post(
        "/api/attempt",
        json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_correct"] is False
    assert data["correct_answer"] == item["word"]
    assert data["updated_phonemes"]
    conn = get_connection(db_path)
    row = conn.execute(
        """
        SELECT question_type, selected_answer, correct_answer, is_correct
        FROM attempts
        WHERE session_item_id = ?
        """,
        (item["session_item_id"],),
    ).fetchone()
    conn.close()
    assert dict(row) == {
        "question_type": "choose_word",
        "selected_answer": item["display_ipa"],
        "correct_answer": item["word"],
        "is_correct": 0,
    }


def test_unsupported_question_type_fails_closed(tmp_path, monkeypatch):
    db_path = _seed_db(tmp_path, monkeypatch)
    client = _client()
    item = client.post("/api/practice/next-normal").json()["items"][0]
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE session_items SET question_type = 'type_word' WHERE id = ?",
        (item["session_item_id"],),
    )
    conn.commit()
    conn.close()

    response = client.post(
        "/api/attempt",
        json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["word"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_ATTEMPT"
    conn = get_connection(db_path)
    attempt_count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM attempts WHERE session_item_id = ?",
        (item["session_item_id"],),
    ).fetchone()["cnt"]
    stat_count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM phoneme_stats WHERE user_id = 'default'",
    ).fetchone()["cnt"]
    conn.close()
    assert attempt_count == 0
    assert stat_count == 0
