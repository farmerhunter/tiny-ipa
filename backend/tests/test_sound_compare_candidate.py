from __future__ import annotations

import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))

from correct_core100_tags import derive, load_corrections  # noqa: E402
from correct_expanded_tags import load_pack  # noqa: E402
from import_words import import_words  # noqa: E402
from prepare_sound_compare import candidate, load_pairs  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.services.sessions import build_minimal_pair_group_response  # noqa: E402


@pytest.mark.parametrize("size", [100, 300])
def test_candidate_changes_only_four_pair_fields_after_tag_correction(size):
    content, tags = load_corrections() if size == 100 else load_pack(size)
    before = derive(content, tags)
    after = candidate(size)
    changed = []
    for old, new in zip(before["words"], after["words"]):
        if old != new:
            changed.append(old["word_id"])
            assert {k: v for k, v in old.items() if k != "minimal_pair_group"} == {
                k: v for k, v in new.items() if k != "minimal_pair_group"
            }
    assert sorted(changed) == ["back", "bag", "came", "game"]
    assert len(load_pairs()["pairs"]) == 2


@pytest.mark.parametrize(
    "damage",
    ["source", "audio_manifest", "order", "position", "duplicate", "ipa", "audio_member", "status"],
)
def test_bad_pair_or_recording_binding_is_rejected(tmp_path, damage):
    manifest = load_pairs()
    for name in [*manifest["sources"], manifest["audio_manifest"]]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    member = manifest["pairs"][0]["members"][0]
    if damage == "source":
        (tmp_path / "content/core_100_words.json").write_text("{}")
    elif damage == "audio_manifest":
        manifest["audio_manifest_sha256"] = "0" * 64
    elif damage == "order":
        member["ordered_phones_us"].reverse()
    elif damage == "position":
        manifest["pairs"][0]["contrast_index"] = 2
    elif damage == "duplicate":
        manifest["pairs"][1]["members"][0] = member.copy()
    elif damage == "ipa":
        member["ipa_us"] = "/ˈkɪm/"
    elif damage == "audio_member":
        member["audio_sha256"] = "0" * 64
    else:
        manifest["status"] = "production"
    (tmp_path / "content/sound_compare_pairs_candidate.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_pairs(tmp_path)


def test_candidate_import_is_explicit_and_uses_existing_specialty_route(tmp_path):
    db = str(tmp_path / "comparison.sqlite")
    phonemes = ROOT / "content/phonemes.json"
    assert not import_words(ROOT / "content/core_300_words.json", phonemes, db)["errors"]
    with get_connection(db) as conn:
        assert build_minimal_pair_group_response(conn)["status"] == "empty"
    source = tmp_path / "explicit-candidate.json"
    source.write_text(json.dumps(candidate(300)))
    assert not import_words(source, phonemes, db)["errors"]
    with get_connection(db) as conn:
        response = build_minimal_pair_group_response(conn)
        assert response["group_type"] == "minimal_pair"
        assert sorted(w["word_id"] for w in response["items"]) == ["back", "bag", "came", "game"]
        assert all(w["question"]["type"] == "choose_ipa" for w in response["items"])
        assert conn.execute("SELECT count(*) FROM attempts").fetchone()[0] == 0


def test_limited_batch_still_includes_ipa_of_partner_outside_the_batch(tmp_path):
    database = str(tmp_path / "limited.sqlite")
    source = tmp_path / "candidate.json"
    source.write_text(json.dumps(candidate(300)))
    assert not import_words(source, ROOT / "content/phonemes.json", database)["errors"]
    with get_connection(database) as conn:
        conn.execute("UPDATE settings SET daily_word_count=3")
        conn.commit()
        response = build_minimal_pair_group_response(conn)
        assert len(response["items"]) == 3
        members = {w["word_id"]: w for w in candidate(300)["words"]}
        ids = {item["word_id"] for item in response["items"]}
        outside = []
        for item in response["items"]:
            current = members[item["word_id"]]
            partner = next(
                w
                for w in members.values()
                if w["word_id"] != current["word_id"]
                and w["minimal_pair_group"] == current["minimal_pair_group"]
            )
            assert partner["ipa_us"] in item["question"]["choices"]
            if partner["word_id"] not in ids:
                outside.append(partner["word_id"])
        assert len(outside) == 1


def test_pair_selection_creation_and_question_validation_share_a_write_lock(tmp_path, monkeypatch):
    from app.db import get_db
    from app.services import sessions

    database = str(tmp_path / "atomic.sqlite")
    source = tmp_path / "candidate.json"
    source.write_text(json.dumps(candidate(300)))
    assert not import_words(source, ROOT / "content/phonemes.json", database)["errors"]
    original = sessions._select_minimal_pair_words
    observed = []

    def concurrent_edit():
        with sqlite3.connect(database, timeout=0) as other:
            try:
                other.execute("UPDATE words SET content_status='disabled' WHERE id='game'")
                other.commit()
                return "changed"
            except sqlite3.OperationalError as error:
                assert "locked" in str(error)
                return "locked"

    with ThreadPoolExecutor(max_workers=1) as executor:

        def select_and_probe(*args, **kwargs):
            words = original(*args, **kwargs)
            observed.append(executor.submit(concurrent_edit).result(timeout=5))
            return words

        monkeypatch.setattr(sessions, "_select_minimal_pair_words", select_and_probe)
        with get_db(database) as conn:
            response = sessions.build_minimal_pair_group_response(conn)
        assert observed == ["locked"]
    assert "error" not in response
    assert len(response["items"]) == 4
    with get_connection(database) as conn:
        assert conn.execute("SELECT count(*) FROM daily_sessions").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM session_items").fetchone()[0] == 4
        assert (
            conn.execute("SELECT content_status FROM words WHERE id='game'").fetchone()[0]
            != "disabled"
        )


@pytest.mark.parametrize("accent", ["US", "UK"])
@pytest.mark.parametrize("padded_left", [False, True])
@pytest.mark.parametrize("active", [False, True])
def test_trim_equal_pairs_are_rejected_for_both_accents_and_directions(
    tmp_path, accent, padded_left, active
):
    database = str(tmp_path / "equivalent.sqlite")
    source = tmp_path / "candidate.json"
    source.write_text(json.dumps(candidate(300)))
    assert not import_words(source, ROOT / "content/phonemes.json", database)["errors"]
    with get_connection(database) as conn:
        conn.execute("UPDATE words SET minimal_pair_group=NULL WHERE id IN ('back','bag')")
        conn.commit()
        if active:
            group = build_minimal_pair_group_response(conn, accent=accent)
            assert len(group["items"]) == 2
            conn.commit()
        left, right = (" /keɪm/ ", "/keɪm/") if padded_left else ("/keɪm/", " /keɪm/ ")
        column = "ipa_us" if accent == "US" else "ipa_uk"
        conn.execute(f"UPDATE words SET {column}=? WHERE id='came'", (left,))
        conn.execute(f"UPDATE words SET {column}=? WHERE id='game'", (right,))
        conn.commit()
        tables = ("daily_sessions", "session_items", "attempts", "phoneme_stats")
        before = {
            name: [tuple(row) for row in conn.execute(f"SELECT * FROM {name} ORDER BY rowid")]
            for name in tables
        }
        response = build_minimal_pair_group_response(conn, accent=accent)
        if active:
            assert response["error"] == "CONTENT_NOT_READY"
        else:
            assert response["status"] == "empty"
            assert response["items"] == []
        after = {
            name: [tuple(row) for row in conn.execute(f"SELECT * FROM {name} ORDER BY rowid")]
            for name in tables
        }
        assert after == before
