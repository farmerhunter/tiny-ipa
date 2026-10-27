from __future__ import annotations

import json
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))
from import_words import import_words  # noqa: E402

from app import db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import listening  # noqa: E402
from tests.auth_helpers import authenticated_client, bootstrap_owner_user  # noqa: E402


@pytest.fixture
def preview(tmp_path, monkeypatch):
    database = str(tmp_path / "preview.sqlite")
    import_words(
        ROOT / "content/core_100_words.json", ROOT / "content/phonemes.json", db_path=database
    )
    bootstrap_owner_user(database)
    audio = tmp_path / "audio"
    (audio / "us").mkdir(parents=True)
    with zipfile.ZipFile(ROOT / "frontend/tests/fixtures/core100-media.zip") as z:
        for word in ["came", "game", "back", "bag"]:
            (audio / "us" / f"{word}.mp3").write_bytes(z.read(f"us/{word}.mp3"))
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", database)
    monkeypatch.setenv("TINY_IPA_ENABLE_LISTENING_PREVIEW", "true")
    monkeypatch.setenv("TINY_IPA_ENV", "development")
    monkeypatch.setenv("TINY_IPA_AUDIO_DIR", str(audio))
    with TestClient(create_app()) as client:
        authenticated_client(client)
        yield client, database


def action(client, lesson, name, **extra):
    return client.post(
        f"/api/listening/lessons/{lesson['id']}/actions",
        json={
            "action": name,
            "index": lesson["cursor"],
            **extra,
        },
    )


def first_question(client):
    lesson = client.post("/api/listening/lessons").json()
    return action(client, lesson, "begin").json()


def correct(lesson):
    return Path(lesson["item"]["audio_url"]).stem


def snapshot(database):
    with db.get_connection(database) as conn:
        return {
            t: [tuple(r) for r in conn.execute("SELECT * FROM " + t)]
            for t in [
                "attempts",
                "daily_sessions",
                "session_items",
                "phoneme_stats",
                "settings",
            ]
        }


def test_eight_item_route_retry_resume_review_and_normal_stats_unchanged(preview):
    client, database = preview
    before = snapshot(database)
    lesson = first_question(client)
    lesson_id = lesson["id"]
    expected_ipa = {
        w["word_id"]: w["ipa_us"]
        for w in json.loads((ROOT / "content/core_100_words.json").read_text())["words"]
    }
    assert lesson["item"]["feedback"] is None
    assert action(client, lesson, "answer", selected_answer=correct(lesson)).status_code == 409
    assert action(client, lesson, "next").status_code == 409
    for i in range(8):
        assert lesson["cursor"] == i
        assert action(client, lesson, "played").status_code == 200
        answer = (
            correct(lesson)
            if i
            else next(w for w in lesson["item"]["choices"] if w != correct(lesson))
        )
        lesson = action(client, lesson, "answer", selected_answer=answer).json()
        assert lesson["item"]["feedback"]["ipa"] == expected_ipa[correct(lesson)]
        replay = action(client, lesson, "answer", selected_answer=answer)
        assert replay.status_code == 200 and replay.json()["replayed"]
        assert replay.json()["summary"]["total"] == i + 1
        other = next(w for w in lesson["item"]["choices"] if w != answer)
        assert action(client, lesson, "answer", selected_answer=other).status_code == 409
        assert client.get("/api/listening/current").json()["lesson"]["id"] == lesson_id
        lesson = action(client, lesson, "next").json()
    assert lesson["phase"] == "completed"
    assert lesson["summary"] == {
        "correct": 7,
        "total": 8,
        "practice_correct": 3,
        "new_words_correct": 4,
    }
    assert snapshot(database) == before
    next_lesson = client.post("/api/listening/lessons").json()
    assert next_lesson["id"] != lesson_id and next_lesson["phase"] == "demo"
    assert client.post("/api/listening/lessons").json()["id"] == next_lesson["id"]


def test_preview_is_owner_scoped_and_unknown_action_rejected(preview):
    client, database = preview
    lesson = first_question(client)
    assert action(client, lesson, "erase").status_code == 400
    with db.get_connection(database) as conn:
        conn.execute(
            "INSERT INTO users SELECT 'other','other',password_hash,0,1,created_at,updated_at "
            "FROM users WHERE id='default'"
        )
        conn.execute("UPDATE listening_previews SET user_id='other' WHERE id=?", (lesson["id"],))
    assert action(client, lesson, "played").status_code == 404
    assert client.get("/api/listening/current").json()["lesson"] is None


def test_same_answer_concurrency_scores_once(preview):
    client, database = preview
    lesson = first_question(client)
    action(client, lesson, "played")
    cookies = dict(client.cookies)
    barrier = Barrier(2)
    app = create_app()

    def submit(_):
        with TestClient(app, cookies=cookies) as other:
            barrier.wait(timeout=10)
            return action(other, lesson, "answer", selected_answer=correct(lesson))

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(submit, range(2)))
    assert [r.status_code for r in result] == [200, 200]
    assert sorted(r.json().get("replayed", False) for r in result) == [False, True]
    assert client.get("/api/listening/current").json()["lesson"]["summary"]["total"] == 1
    assert snapshot(database)["attempts"] == []


def test_disabled_preview_cannot_be_enabled_in_production(preview, monkeypatch):
    client, _ = preview
    monkeypatch.setenv("TINY_IPA_ENV", "production")
    assert listening.enabled() is False
    monkeypatch.setenv("TINY_IPA_ENV", "development")
    monkeypatch.setenv("TINY_IPA_ENABLE_LISTENING_PREVIEW", "false")
    assert client.get("/api/listening/current").json() == {"enabled": False, "lesson": None}
    assert client.post("/api/listening/lessons").status_code == 404


def test_missing_audio_prevents_group_creation(preview, monkeypatch, tmp_path):
    client, database = preview
    monkeypatch.setenv("TINY_IPA_AUDIO_DIR", str(tmp_path / "absent"))
    assert client.post("/api/listening/lessons").status_code == 409
    with db.get_connection(database) as conn:
        assert conn.execute("SELECT count(*) FROM listening_previews").fetchone()[0] == 0
