"""Mutations exclusively for marked temporary candidate-learning fixtures."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

from prepare_core100_real_db import ROOT, seed_audio_cache
from content_activation import media
from insert_core300_increment import COLUMNS, source, stored
from prepare_next_audio import candidate, prepare
from screen_next_pairs import NEW_IDS, combined_evidence, load_next, screen


def fixture_only(conn):
    filename = next(
        r[2] for r in conn.execute("PRAGMA database_list") if r[1] == "main"
    )
    path = Path(filename).resolve(strict=True)
    if not any(
        p in path.parents
        for p in (Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve())
    ):
        raise ValueError("candidate mutation requires a temporary fixture")
    users = {r[0] for r in conn.execute("SELECT username FROM users")}
    if users != {"core100-owner", "workflow-owner"}:
        raise ValueError("candidate mutation requires the synthetic workflow fixture")


def row_map(conn):
    return {
        r[0]: dict(zip(COLUMNS, r))
        for r in conn.execute("SELECT " + ",".join(COLUMNS) + " FROM words")
    }


def baseline_rows(conn, allow_new_pairs=False):
    old12, _, original, old_pairs, _, _ = source(ROOT)
    expected = {w["word_id"]: stored(w) for w in [*original, *old12]}
    rows = row_map(conn)
    for pair in old_pairs["pairs"]:
        for member in pair["members"]:
            expected[member["word_id"]]["minimal_pair_group"] = pair["group"]
    if allow_new_pairs:
        for wid in NEW_IDS:
            expected[wid]["minimal_pair_group"] = rows[wid]["minimal_pair_group"]
    if any(rows.get(wid) != row for wid, row in expected.items()):
        raise ValueError("activated112 fixture content drift")
    return rows, expected


def insert_next_audio(conn, audio_root):
    fixture_only(conn)
    words, manifest = candidate(ROOT)
    media(audio_root, manifest["selected_new_words"])
    credits = manifest["credits"]
    if (
        hashlib.sha256((audio_root / credits["path"]).read_bytes()).hexdigest()
        != credits["sha256"]
    ):
        raise ValueError("next fixture attribution differs")
    target = {w["word_id"]: stored(w) for w in words}
    rows, expected = baseline_rows(conn)
    if set(rows) not in (set(expected), set(expected) | set(target)):
        raise ValueError("partial or unrelated next-candidate catalog")
    if set(target) <= set(rows):
        if any(rows[wid] != row for wid, row in target.items()):
            raise ValueError("conflicting existing next-candidate word")
        return {"status": "no_change", "updated": 0}
    if conn.in_transaction:
        raise ValueError("existing fixture transaction")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for row in target.values():
            conn.execute(
                "INSERT INTO words ("
                + ",".join(COLUMNS)
                + ") VALUES ("
                + ",".join("?" for _ in COLUMNS)
                + ")",
                [row[c] for c in COLUMNS],
            )
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("candidate insertion foreign keys")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"status": "fixture_inserted", "updated": 3}


def prepare_next_audio(database, audio_root):
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
    old12 = client.post("/api/practice/next-normal").json()
    assert len(old12["items"]) == 12
    for item in old12["items"]:
        assert client.post(
            "/api/attempt",
            json={
                "session_item_id": item["session_item_id"],
                "selected_answer": item["display_ipa"],
            },
        ).json()["is_correct"]
    assert client.put("/api/settings", json={"daily_word_count": 3}).status_code == 200
    _, manifest = candidate(ROOT)
    cache = (
        Path(tempfile.mkdtemp(prefix="tiny-ipa-next-audio-cache-")).resolve() / "cache"
    )
    seed_audio_cache(
        ROOT / "frontend/tests/fixtures/core300-next-media.zip",
        {
            "audio": {
                "assets": manifest["selected_new_words"],
                "credits": manifest["credits"],
            }
        },
        cache,
    )
    prepare(ROOT, audio_root, cache)
    with sqlite3.connect(database) as conn:
        before = row_map(conn)
        assert insert_next_audio(conn, audio_root)["updated"] == 3
        assert all(row_map(conn)[wid] == row for wid, row in before.items())
        assert conn.execute(
            "SELECT count(*),count(audio_us) FROM words"
        ).fetchone() == (115, 114)
        assert (
            conn.execute("SELECT audio_us FROM words WHERE id='wood'").fetchone()[0]
            is None
        )


def set_next_pairs(conn, audio_root, enabled):
    fixture_only(conn)
    manifest = load_next(ROOT)
    groups = {m["word_id"]: p["group"] for p in manifest["pairs"] for m in p["members"]}
    rows, expected = baseline_rows(conn, allow_new_pairs=True)
    if set(rows) != set(expected):
        raise ValueError("next pairs require only activated112 catalog")
    current = {wid: rows[wid]["minimal_pair_group"] for wid in NEW_IDS}
    if current not in ({wid: None for wid in NEW_IDS}, groups):
        raise ValueError("mixed/conflicting next group fields")
    if enabled:
        screen(ROOT, audio_root)
    if conn.in_transaction:
        raise ValueError("existing fixture transaction")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not enabled:
            pending = conn.execute(
                "SELECT count(DISTINCT ds.id) FROM daily_sessions ds "
                "JOIN session_items si ON si.session_id=ds.id "
                "WHERE ds.group_type='minimal_pair' AND ds.status='in_progress' "
                "AND si.word_id IN (?,?,?,?)",
                sorted(NEW_IDS),
            ).fetchone()[0]
            if pending:
                conn.rollback()
                return {
                    "status": "blocked_unfinished_sessions",
                    "updated": 0,
                    "blocked_sessions": pending,
                }
        updated = 0
        for wid in sorted(NEW_IDS):
            value = groups[wid] if enabled else None
            if value != current[wid]:
                cursor = conn.execute(
                    "UPDATE words SET minimal_pair_group=? WHERE id=? "
                    "AND minimal_pair_group IS ?",
                    (value, wid, current[wid]),
                )
                if cursor.rowcount != 1:
                    raise ValueError("candidate group preimage changed")
                updated += 1
        conn.commit()
        return {
            "status": "fixture_applied" if updated else "no_change",
            "updated": updated,
        }
    except Exception:
        conn.rollback()
        raise


def prepare_next_pairs(database, audio_root, evidence):
    evidence = evidence.resolve()
    if not any(
        p in evidence.parents
        for p in (Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve())
    ):
        raise ValueError("candidate evidence must be temporary")
    with evidence.open("x") as out:
        json.dump(combined_evidence(ROOT), out, ensure_ascii=False, indent=2)
    with sqlite3.connect(database) as conn:
        before = row_map(conn)
        assert set_next_pairs(conn, audio_root, True)["updated"] == 4
        after = row_map(conn)
        for wid, row in before.items():
            if wid in NEW_IDS:
                assert {
                    k: v for k, v in after[wid].items() if k != "minimal_pair_group"
                } == {k: v for k, v in row.items() if k != "minimal_pair_group"}
            else:
                assert after[wid] == row
        conn.execute(
            "UPDATE settings SET daily_word_count=12,practice_mode='choose_word' WHERE user_id='workflow'"
        )
        conn.commit()
