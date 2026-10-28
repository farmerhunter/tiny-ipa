import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))
from import_words import import_words  # noqa: E402
from prepare_sound_compare import candidate  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Settings, User  # noqa: E402
from app.services.db_store import create_user, upsert_settings  # noqa: E402
from tests.auth_helpers import authenticated_client, bootstrap_owner_user  # noqa: E402


@pytest.fixture
def comparison(tmp_path, monkeypatch):
    source = tmp_path / "candidate.json"
    source.write_text(json.dumps(candidate(100)))
    database = str(tmp_path / "test.sqlite")
    assert import_words(source, ROOT / "content/phonemes.json", database)["committed"]
    monkeypatch.setattr("app.db.DEFAULT_DB_PATH", database)
    bootstrap_owner_user(database)
    with get_connection(database) as conn:
        conn.execute("UPDATE settings SET daily_word_count=4 WHERE user_id='default'")
        conn.commit()
    evidence = tmp_path / "evidence.json"
    evidence.write_bytes((ROOT / "content/sound_compare_pairs_candidate.json").read_bytes())
    monkeypatch.setenv("TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH", str(evidence))
    client = authenticated_client(TestClient(app))
    group = client.post("/api/practice/minimal-pairs").json()
    assert len(group["items"]) == 4
    assert all("sound_compare" not in item for item in group["items"])
    return client, group, database, evidence


def submit(client, item, answer=None):
    return client.post(
        "/api/attempt",
        json={
            "session_item_id": item["session_item_id"],
            "selected_answer": answer or item["display_ipa"],
        },
    )


def test_both_directions_positions_first_grade_and_replay(comparison):
    client, group, database, _ = comparison
    for index, item in enumerate(group["items"]):
        answer = "/wrong/" if index == 0 else item["display_ipa"]
        first = submit(client, item, answer).json()
        assert first["is_correct"] is (index != 0)
        feedback = first["sound_compare"]
        assert feedback["status"] == "available"
        assert feedback["current"] == {
            "word_id": item["word_id"],
            "word": item["word"],
            "ipa": item["display_ipa"],
        }
        expected_partner = {"came": "game", "game": "came", "back": "bag", "bag": "back"}[
            item["word_id"]
        ]
        assert feedback["counterpart"]["word_id"] == expected_partner
        assert feedback["contrast"]["position"] == (
            "initial" if item["word_id"] in {"came", "game"} else "final"
        )
        assert {
            feedback["contrast"]["current_phoneme"],
            feedback["contrast"]["counterpart_phoneme"],
        } == {"/k/", "/g/"}
        replay = submit(client, item, answer).json()
        assert replay["sound_compare"] == feedback and replay["replayed"]
        assert submit(client, item, "/other/").status_code == 409
    with get_connection(database) as conn:
        assert conn.execute("SELECT count(*) FROM attempts").fetchone()[0] == 4


@pytest.mark.parametrize(
    "damage",
    [
        "unset",
        "missing",
        "json",
        "shape",
        "index",
        "order",
        "label",
        "ipa",
        "disabled",
        "ambiguous",
        "uk",
    ],
)
def test_missing_stale_or_malformed_evidence_does_not_undo_valid_grade(
    comparison, monkeypatch, damage
):
    client, group, database, evidence = comparison
    item = next(i for i in group["items"] if i["word_id"] == "came")
    if damage == "unset":
        monkeypatch.delenv("TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH")
    elif damage == "missing":
        monkeypatch.setenv("TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH", str(evidence.parent / "missing"))
    elif damage == "json":
        evidence.write_text("{")
    elif damage == "shape":
        evidence.write_text(
            json.dumps(
                {
                    "schema": "tiny-ipa-sound-compare-candidate/v1",
                    "status": "development-only",
                    "pairs": [{"members": None}],
                }
            )
        )
    elif damage in {"index", "order"}:
        data = json.loads(evidence.read_text())
        if damage == "index":
            data["pairs"][0]["contrast_index"] = 1
        else:
            data["pairs"][0]["members"][0]["ordered_phones_us"].reverse()
        evidence.write_text(json.dumps(data))
    else:
        with get_connection(database) as conn:
            if damage == "label":
                conn.execute("UPDATE words SET word='renamed' WHERE id='game'")
            elif damage == "ipa":
                conn.execute("UPDATE words SET ipa_us='/changed/' WHERE id='game'")
            elif damage == "disabled":
                conn.execute("UPDATE words SET content_status='disabled' WHERE id='game'")
            elif damage == "ambiguous":
                conn.execute("UPDATE words SET minimal_pair_group='kg_initial' WHERE id='bag'")
            else:
                conn.execute(
                    "UPDATE daily_sessions SET primary_accent='UK' WHERE id=?", (group["group_id"],)
                )
            conn.commit()
    result = submit(client, item)
    assert result.status_code == 200, result.json()
    assert result.json()["sound_compare"] == {"status": "unavailable"}
    assert submit(client, item).json()["sound_compare"] == {"status": "unavailable"}
    with get_connection(database) as conn:
        assert conn.execute("SELECT count(*) FROM attempts").fetchone()[0] == 1


def test_replay_does_not_contradict_stored_grade(comparison):
    client, group, database, _ = comparison
    item = group["items"][0]
    assert submit(client, item).json()["sound_compare"]["status"] == "available"
    with get_connection(database) as conn:
        conn.execute("UPDATE words SET ipa_us='/changed/' WHERE id=?", (item["word_id"],))
        conn.commit()
    replay = submit(client, item).json()
    assert replay["correct_answer"] == item["display_ipa"]
    assert replay["sound_compare"] == {"status": "unavailable"}


def test_foreign_owner_gets_no_feedback_and_normal_feedback_unchanged(comparison):
    client, group, database, _ = comparison
    from app.services.auth import hash_password

    with get_connection(database) as conn:
        create_user(
            conn,
            User("other", "other", hash_password("local-only-other"), False, True, "now", "now"),
        )
        upsert_settings(conn, Settings(user_id="other"))
        conn.commit()
    other = TestClient(app)
    assert (
        other.post(
            "/api/auth/login", json={"username": "other", "password": "local-only-other"}
        ).status_code
        == 200
    )
    denial = submit(other, group["items"][0])
    assert denial.status_code == 404 and "sound_compare" not in denial.json()
    normal = client.post("/api/practice/next-normal").json()
    assert submit(client, normal["items"][0]).json()["sound_compare"] is None
