"""Small shared guards for source-bound, explicitly reviewed content mutations."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

EXTRA_IDS = frozenset(
    (
        "book",
        "boy",
        "brother",
        "country",
        "double",
        "down",
        "father",
        "mother",
        "never",
        "oil",
        "weather",
        "young",
    )
)
PAIR_IDS = frozenset(("back", "bag", "came", "cat", "game", "hat", "map", "match"))


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def bindings(root: Path, names) -> dict:
    from prepare_core100_audio import VERIFIER

    return {
        name: hashlib.sha256(VERIFIER._regular_under(root, name).read_bytes()).hexdigest()
        for name in sorted(names)
    }


def schema(conn, tables):
    for name, columns in tables.items():
        actual = {r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')}
        if not set(columns) <= actual:
            raise ValueError(f"required schema missing: {name}")


def catalog(conn, root):
    source = json.loads((root / "content/core_100_words.json").read_text())["words"]
    original = {w["word_id"] for w in source}
    if len(source) != len(original) or len(original) != 100:
        raise ValueError("invalid original catalog")
    ids = {r[0] for r in conn.execute("SELECT id FROM words")}
    if ids not in (original, original | EXTRA_IDS):
        raise ValueError(
            "catalog drift: "
            + json.dumps(
                {
                    "missing_original_ids": sorted(original - ids)[:16],
                    "unexpected_ids": sorted(ids - original - EXTRA_IDS)[:16],
                    "present_increment_ids": sorted(ids & EXTRA_IDS),
                    "actual_count": len(ids),
                },
                sort_keys=True,
            )
        )
    return sorted(ids)


def media(audio_root: Path, assets):
    from prepare_core100_audio import VERIFIER

    for asset in assets:
        path = VERIFIER._regular_under(audio_root, asset["path"])
        if (
            path.stat().st_size != asset["bytes"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]
        ):
            raise ValueError(f"wrong audio bytes: {asset['word_id']}")


def reviewed(value):
    return {**value, "plan_sha256": digest(value)}


def transaction(conn, expected, planner, writer):
    if conn.in_transaction:
        raise ValueError("refusing an existing transaction")
    conn.execute("BEGIN IMMEDIATE")
    try:
        current = planner()
        if current["plan_sha256"] != expected:
            raise ValueError("stale reviewed plan")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("database has foreign-key violations")
        if current.get("blocked_sessions"):
            conn.rollback()
            return {
                "status": "blocked_unfinished_sessions",
                "updated": 0,
                "blocked_sessions": current["blocked_sessions"],
            }
        writer(current)
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("mutation violates foreign keys")
        conn.commit()
        return {
            "status": "applied" if current["change_count"] else "no_change",
            "updated": current["change_count"],
            "plan_sha256": expected,
        }
    except Exception:
        conn.rollback()
        raise


def database(path: Path, apply_hash=None):
    resolved = path.resolve(strict=True)
    if path.is_symlink() or not resolved.is_file():
        raise ValueError("database must be an existing regular file")
    production = Path("/var/lib/tiny-ipa/tiny-ipa.sqlite")
    if resolved == production:
        if path.absolute() != production or any(p.is_symlink() for p in path.parents):
            raise ValueError("production path must be exact without symlinks")
    elif not any(
        p in resolved.parents
        for p in (Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve())
    ):
        raise ValueError("database must be a reviewed Tiny IPA path or disposable temporary file")
    conn = sqlite3.connect(f"{resolved.as_uri()}?mode={'rw' if apply_hash else 'ro'}", uri=True)
    conn.execute("PRAGMA foreign_keys=ON")
    if not apply_hash:
        conn.execute("PRAGMA query_only=ON")
    return conn
