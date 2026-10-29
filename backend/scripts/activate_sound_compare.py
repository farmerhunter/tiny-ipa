"""Plan eight pair fields; apply only an explicitly reviewed current plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from content_activation import (
    PAIR_IDS,
    bindings,
    catalog,
    database,
    media,
    reviewed,
    schema,
    transaction,
)
from correct_core100_tags import derive, load_corrections
from prepare_sound_compare import load_pairs


def plan(conn, action: str, root: Path, evidence: Path, audio_root: Path | None = None):
    if action not in ("enable", "disable"):
        raise ValueError("unknown pair action")
    pairs = load_pairs(root)
    expected_evidence = (root / "content/sound_compare_pairs_candidate.json").read_bytes()
    if evidence.is_symlink() or evidence.read_bytes() != expected_evidence:
        raise ValueError("explicit evidence differs from reviewed source")
    members = {m["word_id"]: (p["group"], m) for p in pairs["pairs"] for m in p["members"]}
    if set(members) != PAIR_IDS or len(pairs["pairs"]) != 4:
        raise ValueError("expected exact four groups/eight words")
    schema(
        conn,
        {
            "words": (
                "id",
                "word",
                "level",
                "ipa_us",
                "phoneme_tags_us",
                "audio_us",
                "minimal_pair_group",
                "content_status",
            ),
            "daily_sessions": ("id", "status", "group_type"),
            "session_items": ("session_id", "word_id"),
            "phonemes": ("id", "accent_scope"),
        },
    )
    ids = catalog(conn, root)
    content, corrections = load_corrections(root)
    words = {w["word_id"]: w for w in derive(content, corrections)["words"]}
    audio_manifest = json.loads((root / pairs["audio_manifest"]).read_text())
    assets = [a for a in audio_manifest["audio"]["assets"] if a["word_id"] in members]
    if action == "enable":
        if audio_root is None:
            raise ValueError("enable requires explicit verified audio root")
        media(audio_root, assets)
        known = {
            r[0]
            for r in conn.execute("SELECT id FROM phonemes WHERE accent_scope IN ('US','both')")
        }
        if any(set(m["ordered_phones_us"]) - known for _, m in members.values()):
            raise ValueError("required phoneme inventory missing")
    rows = []
    for wid in sorted(members):
        row = conn.execute(
            "SELECT word,level,ipa_us,phoneme_tags_us,audio_us,content_status,"
            "minimal_pair_group FROM words WHERE id=?",
            (wid,),
        ).fetchone()
        if not row or tuple(row[:3]) != (wid, "beginner", members[wid][1]["ipa_us"]):
            raise ValueError(f"pair identity differs: {wid}")
        if action == "enable" and (
            json.loads(row[3]) != words[wid]["phoneme_tags_us"]
            or row[4] != members[wid][1]["audio_url"]
            or row[5] != words[wid]["content_status"]
        ):
            raise ValueError(f"pair enabled content differs: {wid}")
        rows.append((wid, *row))
    states = [r[-1] for r in rows]
    desired = [members[r[0]][0] for r in rows]
    if states != [None] * 8 and states != desired:
        raise ValueError(
            "mixed/conflicting pair fields: "
            + json.dumps(
                [
                    {"word_id": r[0], "observed": r[-1], "expected_enabled": members[r[0]][0]}
                    for r in rows
                    if r[-1] is not None
                ],
                sort_keys=True,
            )
        )
    groups = sorted({p["group"] for p in pairs["pairs"]})
    occupants = [
        tuple(r)
        for r in conn.execute(
            "SELECT id,minimal_pair_group FROM words WHERE "
            "minimal_pair_group IN (?,?,?,?) ORDER BY id",
            groups,
        )
    ]
    if any(wid not in members or members[wid][0] != group for wid, group in occupants):
        raise ValueError("unexpected global group member")
    blocked = 0
    if action == "disable":
        # Match the application session-status authority, across all dates.
        blocked = conn.execute(
            "SELECT count(DISTINCT ds.id) FROM daily_sessions ds "
            "JOIN session_items si ON si.session_id=ds.id "
            "WHERE ds.group_type='minimal_pair' AND ds.status='in_progress' "
            "AND si.word_id IN (?,?,?,?,?,?,?,?)",
            sorted(members),
        ).fetchone()[0]
    changes = [
        {
            "word_id": r[0],
            "before": r[-1],
            "after": members[r[0]][0] if action == "enable" else None,
        }
        for r in rows
        if r[-1] != (members[r[0]][0] if action == "enable" else None)
    ]
    value = {
        "action": action,
        "source_bindings": bindings(
            root,
            [
                *pairs["sources"],
                pairs["audio_manifest"],
                "content/core_100_phoneme_corrections.json",
                "content/sound_compare_pairs_candidate.json",
            ],
        ),
        "evidence_sha256": hashlib.sha256(expected_evidence).hexdigest(),
        "catalog_ids": ids,
        "preimages": rows,
        "group_occupants": occupants,
        "blocked_sessions": blocked,
        "changes": changes,
        "change_count": len(changes),
        "field": "minimal_pair_group",
    }
    return reviewed(value)


def apply(conn, action, root, evidence, audio_root, expected):
    def write(current):
        for change in current["changes"]:
            cursor = conn.execute(
                "UPDATE words SET minimal_pair_group=? WHERE id=? AND minimal_pair_group IS ?",
                (change["after"], change["word_id"], change["before"]),
            )
            if cursor.rowcount != 1:
                raise ValueError("pair preimage changed")

    return transaction(
        conn, expected, lambda: plan(conn, action, root, evidence, audio_root), write
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enable", "disable"))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path)
    parser.add_argument("--apply-plan-sha256")
    args = parser.parse_args()
    conn = database(args.db, args.apply_plan_sha256)
    try:
        result = (
            apply(
                conn,
                args.action,
                args.repo_root,
                args.evidence,
                args.audio_root,
                args.apply_plan_sha256,
            )
            if args.apply_plan_sha256
            else plan(conn, args.action, args.repo_root, args.evidence, args.audio_root)
        )
        print(json.dumps(result, sort_keys=True))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
