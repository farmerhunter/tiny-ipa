#!/usr/bin/env python3
"""Derive corrected Core100 tags; DB application requires a separately reviewed plan."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

from select_candidates import parse_ipa_to_phonemes

ROOT = Path(__file__).resolve().parents[2]


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_corrections(root: Path = ROOT) -> tuple[dict, dict]:
    patch = json.loads((root / "content/core_100_phoneme_corrections.json").read_text())
    if patch["schema"] != "tiny-ipa-core100-tag-corrections/v1":
        raise ValueError("unknown corrections schema")
    if patch["source"] != "content/core_100_words.json":
        raise ValueError("unexpected correction source")
    source = (root / patch["source"]).read_bytes()
    if hashlib.sha256(source).hexdigest() != patch["source_sha256"]:
        raise ValueError("frozen correction source changed")
    content = json.loads(source)
    words = {w["word_id"]: w for w in content["words"]}
    seen = set()
    for change in patch["changes"]:
        wid = change["word_id"]
        if wid in seen or wid not in words:
            raise ValueError("invalid correction identity")
        seen.add(wid)
        word = words[wid]
        if word["ipa_us"] != change["ipa_us"] or word["phoneme_tags_us"] != change["before"]:
            raise ValueError("correction preimage differs")
        if not word.get("_phoneme_override_note"):
            raise ValueError("vowel override requires existing provenance")
        parsed, unknown = parse_ipa_to_phonemes(word["ipa_us"])
        expected = [{"/ə/": "/ʌ/", "/ɝ/": "/ɚ/"}.get(t, t) for t in parsed]
        if unknown or change["after"] != expected:
            raise ValueError(
                "correction must preserve all parsed tags and documented vowel mapping"
            )
    return content, patch


def derive(content: dict, patch: dict) -> dict:
    corrected = copy.deepcopy(content)
    changes = {c["word_id"]: c for c in patch["changes"]}
    for word in corrected["words"]:
        if word["word_id"] in changes:
            word["phoneme_tags_us"] = changes[word["word_id"]]["after"].copy()
    return corrected


def plan(connection: sqlite3.Connection, patch: dict) -> dict:
    changes, state = [], []
    for change in patch["changes"]:
        row = connection.execute(
            "SELECT ipa_us,phoneme_tags_us FROM words WHERE id=?", (change["word_id"],)
        ).fetchone()
        if row is None or row[0] != change["ipa_us"]:
            raise ValueError("correction word/IPA differs")
        current = json.loads(row[1])
        state.append([change["word_id"], row[0], current])
        if current == change["after"]:
            continue
        if current != change["before"]:
            raise ValueError("existing tags differ from both reviewed states")
        changes.append(change)
    value = {
        "patch_sha256": digest(patch),
        "state_sha256": digest(state),
        "changes": changes,
        "change_count": len(changes),
    }
    return {**value, "plan_sha256": digest(value)}


def apply(connection: sqlite3.Connection, patch: dict, expected: str) -> dict:
    if connection.in_transaction:
        raise ValueError("refusing an existing transaction")
    connection.execute("BEGIN IMMEDIATE")
    try:
        current = plan(connection, patch)
        if current["plan_sha256"] != expected:
            raise ValueError("tags changed since the reviewed plan")
        for change in current["changes"]:
            cursor = connection.execute(
                "UPDATE words SET phoneme_tags_us=? WHERE id=?",
                (
                    json.dumps(change["after"], ensure_ascii=False),
                    change["word_id"],
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("correction must affect exactly one word")
        connection.commit()
        return {
            "status": "tags_corrected",
            "updated": current["change_count"],
            "plan_sha256": expected,
        }
    except Exception:
        connection.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--apply-plan-sha256")
    args = parser.parse_args()
    content, patch = load_corrections()
    if args.db is None:
        if args.apply_plan_sha256:
            parser.error("DB required for application")
        print(json.dumps(derive(content, patch), ensure_ascii=False, indent=2))
        return
    database = args.db.resolve(strict=True)
    for path in (args.db, *args.db.absolute().parents):
        if path.is_symlink():
            parser.error("database paths must not contain symlinks")
    allowed = [Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()]
    if database != Path("/var/lib/tiny-ipa/tiny-ipa.sqlite") and not any(
        root in database.parents for root in allowed
    ):
        parser.error("DB must be the exact reviewed production path or a temporary fixture")
    mode = "rw" if args.apply_plan_sha256 else "ro"
    with sqlite3.connect(f"{database.as_uri()}?mode={mode}", uri=True) as connection:
        result = (
            apply(connection, patch, args.apply_plan_sha256)
            if args.apply_plan_sha256
            else plan(connection, patch)
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
