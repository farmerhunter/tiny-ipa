import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend/scripts"), str(ROOT / "frontend/tests/e2e/support")]
from backup_restore_dry_run import snapshot_database  # noqa: E402
from candidate_content_fixture import fixture_only, insert_next_audio, set_next_pairs  # noqa: E402
from prepare_core100_audio import check_media  # noqa: E402
from prepare_core100_real_db import seed_audio_cache  # noqa: E402
from prepare_next_audio import candidate, prepare  # noqa: E402
from screen_next_pairs import NEW_IDS, combined_evidence, load_next, screen  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    root = tmp_path_factory.mktemp("offline-next-template").resolve()
    db, audio = root / "base.sqlite", root / "audio"
    env = {
        **os.environ,
        "CORE100_REAL_DB_PATH": str(db),
        "TINY_IPA_DB_PATH": str(db),
        "CORE100_REAL_AUDIO_DIR": str(audio),
        "TINY_IPA_AUDIO_DIR": str(audio),
        "TINY_IPA_ENV": "development",
        "TINY_IPA_SESSION_SECRET": "synthetic-next-only",
        "TINY_IPA_ENABLE_LISTENING_PREVIEW": "false",
        "TINY_IPA_REQUIRE_PACKAGED_AUDIO": "true",
        "TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH": str(
            ROOT / "content/sound_compare_pairs_candidate.json"
        ),
        "CONTENT_ACTIVATION_REAL": "true",
        "CORE100_REAL_PAIR_CANDIDATE": "false",
        "CORE300_REAL_CANDIDATE": "false",
        "CORE100_REAL_LEVEL_ACCOUNTS": "false",
        "CONTENT_RECOVERY_REAL": "false",
        "NEXT_AUDIO_REAL": "false",
        "NEXT_PAIRS_REAL": "false",
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "frontend/tests/e2e/support/prepare_core100_real_db.py")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    _, manifest = candidate(ROOT)
    cache = root / "next-cache"
    seed_audio_cache(
        ROOT / "frontend/tests/fixtures/core300-next-media.zip",
        {"audio": {"assets": manifest["selected_new_words"], "credits": manifest["credits"]}},
        cache,
    )
    prepare(ROOT, audio, cache)
    return db, audio, cache


@pytest.fixture
def fixture(template, tmp_path, monkeypatch):
    original, audio, cache = template
    target = tmp_path / "copy.sqlite"
    with sqlite3.connect(original) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    monkeypatch.setattr("app.db.DEFAULT_DB_PATH", str(target))
    monkeypatch.setenv("TINY_IPA_ENV", "development")
    monkeypatch.setenv("TINY_IPA_ENABLE_LISTENING_PREVIEW", "false")
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(combined_evidence(ROOT)))
    monkeypatch.setenv("TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH", str(evidence))
    conn = sqlite3.connect(target)
    conn.execute("PRAGMA foreign_keys=ON")
    yield conn, target, audio, cache, evidence
    conn.close()


def test_next_audio_research_selection_and_strict_decode(template):
    _, audio, _ = template
    words, m = candidate(ROOT)
    assert {w["word_id"] for w in words} == {"family", "how", "better"}
    assert not m["existing_word_attachments"]
    assert {d["word_id"] for d in m["deferrals"]} == {"wood", "angry", "candy"}
    assert sum(a["bytes"] for a in m["selected_new_words"]) == 37842
    for a in m["selected_new_words"]:
        data = (audio / a["path"]).read_bytes()
        assert len(data) == a["bytes"] and hashlib.sha256(data).hexdigest() == a["sha256"]
        assert check_media(audio / a["path"])["decoded"]
    assert next(d for d in m["deferrals"] if d["word_id"] == "wood")["checks"]


def test_isolated_insert_preserves_activated112_and_history_no_wood_attachment(fixture):
    conn, db, audio, _, _ = fixture
    before = snapshot_database(db)
    old = {r[0]: tuple(r) for r in conn.execute("SELECT * FROM words")}
    assert before["tables"]["attempts"]["count"] == 100
    assert insert_next_audio(conn, audio)["updated"] == 3
    rows = {r[0]: tuple(r) for r in conn.execute("SELECT * FROM words")}
    assert all(rows[wid] == row for wid, row in old.items())
    assert conn.execute("SELECT count(*),count(audio_us) FROM words").fetchone() == (115, 114)
    assert conn.execute("SELECT audio_us FROM words WHERE id='wood'").fetchone()[0] is None
    after = snapshot_database(db)
    assert {k: v for k, v in before["tables"].items() if k != "words"} == {
        k: v for k, v in after["tables"].items() if k != "words"
    }
    assert insert_next_audio(conn, audio) == {"status": "no_change", "updated": 0}


def test_next_audio_insert_fault_keeps_all_original_data(fixture):
    conn, db, audio, _, _ = fixture
    conn.execute(
        "CREATE TRIGGER injected BEFORE INSERT ON words WHEN NEW.id='how' "
        "BEGIN SELECT RAISE(ABORT,'injected'); END"
    )
    conn.commit()
    before = snapshot_database(db)
    with pytest.raises(sqlite3.IntegrityError):
        insert_next_audio(conn, audio)
    assert snapshot_database(db) == before


def test_next_audio_rejects_partial_or_conflicting_rows(fixture):
    conn, db, audio, _, _ = fixture
    insert_next_audio(conn, audio)
    conn.execute("UPDATE words SET audio_us='unreviewed' WHERE id='family'")
    conn.commit()
    before = snapshot_database(db)
    with pytest.raises(ValueError):
        insert_next_audio(conn, audio)
    assert snapshot_database(db) == before


def test_next_audio_wrong_cache_and_collision_fail_without_replacing_bytes(fixture, tmp_path):
    _, _, audio, cache, _ = fixture
    target = tmp_path.resolve() / "audio"
    (target / "us").mkdir(parents=True)
    (target / "us/family.mp3").write_bytes(b"collision")
    with pytest.raises(ValueError):
        prepare(ROOT, target, cache)
    assert (target / "us/family.mp3").read_bytes() == b"collision"
    with pytest.raises((ValueError, OSError)):
        prepare(ROOT, tmp_path.resolve() / "missing", tmp_path.resolve())


def test_deterministic_screen_uses111_and_disjoint_literal_source_contrasts(template):
    _, audio, _ = template
    first = screen(ROOT, audio)
    second = screen(ROOT, audio)
    assert first == second and first["recording_count"] == 111
    assert first["media_check"] == "all111-bytes-verified"
    existing = {frozenset(c) for c in first["excluded_existing_contrasts"]}
    assert existing == {
        frozenset(("/k/", "/g/")),
        frozenset(("/k/", "/h/")),
        frozenset(("/p/", "/tʃ/")),
    }
    assert all(frozenset(c["contrast"]) not in existing for c in first["candidates"])
    selected = load_next(ROOT)
    assert {m["word_id"] for p in selected["pairs"] for m in p["members"]} == NEW_IDS
    assert not NEW_IDS & set(first["excluded_existing_members"])
    for p in selected["pairs"]:
        for m in p["members"]:
            assert "/ə/" in m["ordered_phones_us"] and "/ʌ/" in m["source_tags_us"]
    merged = combined_evidence(ROOT)
    assert len(merged["pairs"]) == 6
    assert (
        merged["pairs"][:4]
        == json.loads((ROOT / "content/sound_compare_pairs_candidate.json").read_text())["pairs"]
    )


def test_candidate_pair_pending_old_date_disable_and_original_feedback_survive(fixture):
    conn, db, audio, _, evidence = fixture
    before = {r[0]: r[1] for r in conn.execute("SELECT id,minimal_pair_group FROM words")}
    assert set_next_pairs(conn, audio, True)["updated"] == 4
    client = TestClient(app)
    assert (
        client.post(
            "/api/auth/login", json={"username": "core100-owner", "password": "local-only-core100"}
        ).status_code
        == 200
    )
    assert client.put("/api/settings", json={"daily_word_count": 12}).status_code == 200
    group = client.post("/api/practice/minimal-pairs").json()
    assert len(group["items"]) == 12
    conn.execute(
        "UPDATE daily_sessions SET session_date='2000-01-01' WHERE id=?", (group["group_id"],)
    )
    conn.commit()
    assert set_next_pairs(conn, audio, False) == {
        "status": "blocked_unfinished_sessions",
        "updated": 0,
        "blocked_sessions": 1,
    }
    for item in group["items"]:
        answer = client.post(
            "/api/attempt",
            json={
                "session_item_id": item["session_item_id"],
                "selected_answer": item["display_ipa"],
            },
        ).json()
        assert answer["sound_compare"]["status"] == "available" and answer["is_correct"]
    attempts = conn.execute("SELECT count(*) FROM attempts").fetchone()[0]
    assert set_next_pairs(conn, audio, False)["updated"] == 4
    evidence.write_bytes((ROOT / "content/sound_compare_pairs_candidate.json").read_bytes())
    assert {r[0]: r[1] for r in conn.execute("SELECT id,minimal_pair_group FROM words")} == before
    for item in group["items"]:
        response = client.post(
            "/api/attempt",
            json={
                "session_item_id": item["session_item_id"],
                "selected_answer": item["display_ipa"],
            },
        ).json()
        assert response["replayed"]
        assert response["sound_compare"]["status"] == (
            "unavailable" if item["word_id"] in NEW_IDS else "available"
        )
    assert conn.execute("SELECT count(*) FROM attempts").fetchone()[0] == attempts


def test_restore_refuses_existing_or_non_temporary_environment(tmp_path):
    from restore_activated_fixture import prepare_recovery

    existing = tmp_path.resolve() / "existing"
    existing.mkdir()
    (existing / "sentinel").write_text("keep")
    with pytest.raises(ValueError):
        prepare_recovery(
            existing / "restored/tiny-ipa.sqlite",
            existing / "restored/audio",
            existing / "restored/evidence.json",
        )
    assert (existing / "sentinel").read_text() == "keep"
    with pytest.raises(ValueError):
        prepare_recovery(
            ROOT / "restored/tiny-ipa.sqlite",
            ROOT / "restored/audio",
            ROOT / "restored/evidence.json",
        )


@pytest.mark.parametrize("damage", ["attachment", "bindings", "accent", "license"])
def test_next_audio_manifest_rejects_unreviewed_attachments_or_provenance(tmp_path, damage):
    _, original = candidate(ROOT)
    copy = json.loads(json.dumps(original))
    if damage == "attachment":
        copy["existing_word_attachments"] = [{"word_id": "wood"}]
    elif damage == "bindings":
        copy["source_bindings"] = {}
    elif damage == "accent":
        copy["selected_new_words"][0]["accent_evidence"] = "English only"
    else:
        copy["selected_new_words"][0]["license"] = "unverified"
    target = tmp_path.resolve()
    for name in [
        "content/core300_next_audio_candidate.json",
        *original["source_bindings"],
        original["credits"]["source"],
    ]:
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    (target / "content/core300_next_audio_candidate.json").write_text(json.dumps(copy))
    with pytest.raises(ValueError):
        candidate(target)


@pytest.mark.parametrize("damage", ["tags_as_order", "old_member", "provenance"])
def test_new_pair_evidence_refuses_inferred_tokens_overlap_and_stale_sources(tmp_path, damage):
    original = load_next(ROOT)
    copy = json.loads(json.dumps(original))
    if damage == "tags_as_order":
        copy["pairs"][0]["members"][0]["ordered_phones_us"] = copy["pairs"][0]["members"][0][
            "source_tags_us"
        ]
    elif damage == "old_member":
        copy["pairs"][0]["members"][0]["word_id"] = "cat"
    else:
        copy["base_evidence_sha256"] = "0" * 64
    target = tmp_path.resolve()
    from insert_core300_increment import source

    names = [*source(ROOT)[4], "content/sound_compare_next_pairs_candidate.json"]
    for name in names:
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    (target / "content/sound_compare_next_pairs_candidate.json").write_text(json.dumps(copy))
    with pytest.raises(ValueError):
        load_next(target)


def test_candidate_group_midtransaction_fault_and_temporary_boundary(fixture):
    conn, db, audio, _, _ = fixture
    conn.execute(
        "CREATE TRIGGER injected_pair BEFORE UPDATE OF minimal_pair_group ON words "
        "WHEN NEW.id='fun' BEGIN SELECT RAISE(ABORT,'injected'); END"
    )
    conn.commit()
    before = snapshot_database(db)
    with pytest.raises(sqlite3.IntegrityError):
        set_next_pairs(conn, audio, True)
    assert snapshot_database(db) == before
    with sqlite3.connect(":memory:") as outside:
        with pytest.raises(ValueError):
            insert_next_audio(outside, audio)


def test_memory_fixture_is_rejected_from_temporary_cwd(monkeypatch):
    cwd = Path(tempfile.mkdtemp(prefix="tiny-ipa-memory-guard-", dir="/tmp"))
    monkeypatch.chdir(cwd)
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE users (username TEXT)")
        conn.executemany(
            "INSERT INTO users VALUES (?)", [("core100-owner",), ("workflow-owner",)]
        )
        assert conn.execute("PRAGMA database_list").fetchone()[2] == ""
        with pytest.raises(ValueError, match="file-backed temporary fixture"):
            fixture_only(conn)
