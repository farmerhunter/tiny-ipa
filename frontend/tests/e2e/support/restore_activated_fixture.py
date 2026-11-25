"""Rebuild an activated synthetic learner in a separate temporary environment."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def prepare_recovery(database: Path, audio_root: Path, evidence_path: Path) -> dict:
    import prepare_core100_real_db as fixture
    from activate_sound_compare import apply as pair_apply, plan as pair_plan
    from backup_restore_dry_run import run_backup_restore_dry_run, snapshot_database
    from insert_core300_increment import (
        apply as insert_apply,
        plan as insert_plan,
        prepare_media,
    )
    from prepare_core100_audio import prepare
    import app.db as db_module

    database = database.resolve()
    root = database.parent.parent
    temp = Path(tempfile.gettempdir()).resolve()
    if (
        temp not in root.parents
        or root.exists()
        or root.is_symlink()
        or database != root / "restored/tiny-ipa.sqlite"
        or audio_root.resolve() != root / "restored/audio"
        or evidence_path.resolve() != root / "restored/evidence.json"
    ):
        raise ValueError("recovery requires a new isolated temporary environment")
    root.mkdir()
    source_root, restored = root / "source", root / "restored"
    source_root.mkdir()
    restored.mkdir()
    source_db, source_audio = source_root / "tiny-ipa.sqlite", source_root / "audio"
    source_evidence = ROOT / "content/sound_compare_pairs_candidate.json"
    overrides = {
        "CONTENT_RECOVERY_REAL": "false",
        "CONTENT_ACTIVATION_REAL": "true",
        "CORE100_REAL_DB_PATH": str(source_db),
        "TINY_IPA_DB_PATH": str(source_db),
        "CORE100_REAL_AUDIO_DIR": str(source_audio),
        "TINY_IPA_AUDIO_DIR": str(source_audio),
        "TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH": str(source_evidence),
        "TINY_IPA_ENABLE_LISTENING_PREVIEW": "false",
    }
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    db_module.DEFAULT_DB_PATH = str(source_db)
    try:
        fixture.main()
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "core100-owner", "password": "local-only-core100"},
            ).status_code
            == 200
        )
        normal = client.post("/api/practice/next-normal").json()
        assert len(normal["items"]) == 12
        first = normal["items"][0]
        assert client.post(
            "/api/attempt",
            json={
                "session_item_id": first["session_item_id"],
                "selected_answer": first["display_ipa"],
            },
        ).json()["is_correct"]
        assert (
            client.put("/api/settings", json={"daily_word_count": 8}).status_code == 200
        )
        pair = client.post("/api/practice/minimal-pairs").json()
        assert len(pair["items"]) == 8
        wrong = pair["items"][0]
        partner = next(
            i
            for i in pair["items"][1:]
            if i["word_id"]
            == {
                "back": "bag",
                "bag": "back",
                "came": "game",
                "game": "came",
                "cat": "hat",
                "hat": "cat",
                "map": "match",
                "match": "map",
            }[wrong["word_id"]]
        )
        payload = {
            "session_item_id": wrong["session_item_id"],
            "selected_answer": partner["display_ipa"],
        }
        grade = client.post("/api/attempt", json=payload).json()
        assert (
            grade["is_correct"] is False
            and grade["sound_compare"]["status"] == "available"
        )
        assert client.post("/api/attempt", json=payload).json()["replayed"]
        assert (
            client.post(
                "/api/attempt",
                json={
                    "session_item_id": wrong["session_item_id"],
                    "selected_answer": wrong["display_ipa"],
                },
            ).status_code
            == 409
        )
        pair_readback = client.post("/api/practice/minimal-pairs").json()
        progress = client.get("/api/progress").json()
        assert (
            pair_readback["group_id"] == pair["group_id"]
            and pair_readback["resume_index"] == 1
        )
        assert progress["total_attempts"] == 101
        before = snapshot_database(source_db)
        backup = run_backup_restore_dry_run(source_db, root / "backup.sqlite", database)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert audio_root.resolve() != source_audio.resolve()
    manifest100_path = ROOT / "deploy/jingyun/core100-content-audio.manifest.json"
    manifest100 = json.loads(manifest100_path.read_text())
    fixture.seed_audio_cache(
        ROOT / "frontend/tests/fixtures/core100-media.zip",
        manifest100,
        root / "cache99",
    )
    prepare(manifest100_path, ROOT, audio_root, root / "cache99")
    manifest300 = json.loads(
        (ROOT / "deploy/jingyun/core300-content-audio.manifest.json").read_text()
    )
    ids = set(manifest300["build"]["new_word_ids"])
    fixture.seed_audio_cache(
        ROOT / "frontend/tests/fixtures/core300-extra-media.zip",
        {
            "audio": {
                "assets": [
                    a for a in manifest300["audio"]["assets"] if a["word_id"] in ids
                ],
                "credits": manifest300["audio"]["credits"],
            }
        },
        root / "cache12",
    )
    prepare_media(ROOT, audio_root, root / "cache12")
    with evidence_path.open("xb") as out:
        out.write(source_evidence.read_bytes())
    with sqlite3.connect(database) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        p = pair_plan(conn, "enable", ROOT, evidence_path, audio_root)
        assert p["change_count"] == 0
        assert (
            pair_apply(
                conn, "enable", ROOT, evidence_path, audio_root, p["plan_sha256"]
            )["status"]
            == "no_change"
        )
        b = insert_plan(conn, ROOT, audio_root)
        assert b["change_count"] == 0
        assert (
            insert_apply(conn, ROOT, audio_root, b["plan_sha256"])["status"]
            == "no_change"
        )
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert conn.execute(
            "SELECT count(*),count(audio_us) FROM words"
        ).fetchone() == (112, 111)
        assert (
            conn.execute(
                "SELECT count(*) FROM words WHERE minimal_pair_group IS NOT NULL"
            ).fetchone()[0]
            == 8
        )
    assert snapshot_database(database) == before
    assert backup["verification"] == before
    report = {
        "synthetic_only": True,
        "root": str(root),
        "source_database": str(source_db),
        "restored_database": str(database),
        "source_audio": str(source_audio),
        "restored_audio": str(audio_root),
        "restored_evidence": str(evidence_path),
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "audio_count": 111,
        "source_and_restore_all_table_fingerprints_equal": True,
        "fresh_pair_plan_noop": True,
        "fresh_insert_plan_noop": True,
        "before": before,
        "backup": backup,
        "normal_group": normal,
        "pair_group": pair_readback,
        "first_answer_payload": payload,
        "first_answer_result": grade,
        "owner_attempts": progress["total_attempts"],
        "new_word_answered": first["word_id"],
        "listening_enabled": False,
    }
    with (root / "recovery-receipt.json").open("x") as out:
        json.dump(report, out, indent=2)
    return report
