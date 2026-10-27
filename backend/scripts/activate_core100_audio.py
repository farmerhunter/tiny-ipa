#!/usr/bin/env python3
"""Candidate: plan audio URL additions; apply only after separate host approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

from prepare_core100_audio import VERIFIER


def _hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def plan(connection: sqlite3.Connection, content: dict, manifest_sha256: str) -> dict:
    words = {w["word_id"]: w for w in content["words"]}
    rows = connection.execute("SELECT id, word, ipa_us, audio_us FROM words ORDER BY id").fetchall()
    if {row[0] for row in rows} != set(words):
        raise ValueError("existing word IDs differ from the reviewed content")
    changes = []
    for wid, word, ipa, current in rows:
        expected = words[wid]
        if word != expected["word"] or ipa != expected["ipa_us"]:
            raise ValueError("existing word/IPA differs from the reviewed content")
        target = expected.get("audio_us")
        if current == target:
            continue
        if current is not None or target != f"/audio/us/{wid}.mp3":
            raise ValueError("only missing audio URL additions are allowed")
        changes.append({"word_id": wid, "before": None, "after": target})
    value = {
        "manifest_sha256": manifest_sha256,
        "word_state_sha256": _hash([tuple(row) for row in rows]),
        "changes": changes,
        "change_count": len(changes),
    }
    return {**value, "plan_sha256": _hash(value)}


def apply(
    connection: sqlite3.Connection, content: dict, manifest_sha256: str, expected_plan_sha256: str
) -> dict:
    if connection.in_transaction:
        raise ValueError("refusing to join an existing transaction")
    connection.execute("BEGIN IMMEDIATE")
    try:
        current = plan(connection, content, manifest_sha256)
        if current["plan_sha256"] != expected_plan_sha256:
            raise ValueError("database changed since the reviewed plan")
        if list(connection.execute("PRAGMA foreign_key_check")):
            raise ValueError("database has foreign-key violations")
        for change in current["changes"]:
            cursor = connection.execute(
                "UPDATE words SET audio_us=? WHERE id=? AND audio_us IS NULL",
                (change["after"], change["word_id"]),
            )
            if cursor.rowcount != 1:
                raise ValueError("audio update did not affect exactly one reviewed word")
        connection.commit()
        return {
            "status": "audio_urls_added",
            "updated": current["change_count"],
            "plan_sha256": expected_plan_sha256,
        }
    except Exception:
        connection.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--audio-root", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--apply-plan-sha256")
    args = parser.parse_args()
    database = args.db.resolve(strict=True)
    temporary_roots = (Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve())
    production = Path("/var/lib/tiny-ipa/tiny-ipa.sqlite")
    if args.db.is_symlink():
        parser.error("database must not be a symlink")
    if database == production:
        if args.db.absolute() != production or any(p.is_symlink() for p in args.db.parents):
            parser.error("production database path must be exact and contain no symlinks")
    elif not any(root in database.parents for root in temporary_roots):
        parser.error("database must be the reviewed Tiny IPA path or a disposable temporary file")
    VERIFIER.verify(args.manifest, args.repo_root, args.audio_root)
    manifest = json.loads(args.manifest.read_text())
    content = json.loads((args.repo_root / manifest["content"]["path"]).read_text())
    manifest_sha = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    mode = "rw" if args.apply_plan_sha256 else "ro"
    connection = sqlite3.connect(f"{database.as_uri()}?mode={mode}", uri=True)
    try:
        if args.apply_plan_sha256:
            result = apply(connection, content, manifest_sha, args.apply_plan_sha256)
        else:
            result = plan(connection, content, manifest_sha)
        print(json.dumps(result, sort_keys=True))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
