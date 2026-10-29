"""Prepare twelve licensed assets and a reviewed INSERT-only Core300 increment."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

from content_activation import (
    EXTRA_IDS,
    PAIR_IDS,
    bindings,
    catalog,
    database,
    digest,
    media,
    reviewed,
    schema,
    transaction,
)
from correct_core100_tags import derive, load_corrections
from correct_expanded_tags import load_pack
from prepare_core100_audio import VERIFIER, _directory, _write, check_media
from prepare_sound_compare import load_pairs
from validate_content import import_structure_errors, load_phoneme_set, validate_words

from app.services.db_store import word_values

COLUMNS = (
    "id",
    "word",
    "level",
    "ipa_us",
    "ipa_uk",
    "phoneme_tags_us",
    "phoneme_tags_uk",
    "meaning_zh",
    "audio_us",
    "audio_uk",
    "difficulty_tags",
    "minimal_pair_group",
    "content_status",
)


def stored(word):
    values = word_values(word)
    return {column: values["word_id" if column == "id" else column] for column in COLUMNS}


def source(root):
    manifest_path = "deploy/jingyun/core300-content-audio.manifest.json"
    manifest = json.loads(VERIFIER._regular_under(root, manifest_path).read_text())
    build = manifest["build"]
    names = [
        manifest_path,
        "content/core_300_words.json",
        "content/core_300_phoneme_corrections.json",
        "content/core_100_words.json",
        "content/core_100_phoneme_corrections.json",
        "content/phonemes.json",
        "deploy/jingyun/core100-content-audio.manifest.json",
        "deploy/jingyun/core300-audio-attribution.md",
        "content/sound_compare_pairs_candidate.json",
    ]
    identities = bindings(root, names)
    if (
        build["source_content"] != "content/core_300_words.json"
        or build["source_content_sha256"] != identities[build["source_content"]]
        or build["tag_corrections"]
        != {
            "path": "content/core_300_phoneme_corrections.json",
            "sha256": identities["content/core_300_phoneme_corrections.json"],
        }
        or build["reuse_manifest"]
        != {
            "path": "deploy/jingyun/core100-content-audio.manifest.json",
            "sha256": identities["deploy/jingyun/core100-content-audio.manifest.json"],
        }
    ):
        raise ValueError("Core300 source/correction/reuse binding differs")
    raw, patch = load_pack(300, root)
    content = derive(raw, patch)
    words = {w["word_id"]: w for w in content["words"]}
    if len(words) != len(content["words"]) or len(words) != 300:
        raise ValueError("invalid frozen Core300 identities")
    old = json.loads((root / "deploy/jingyun/core100-content-audio.manifest.json").read_text())
    old_assets = {a["word_id"]: a for a in old["audio"]["assets"]}
    assets = {a["word_id"]: a for a in manifest["audio"]["assets"]}
    if (
        len(old_assets) != 99
        or len(old["audio"]["assets"]) != 99
        or len(assets) != len(manifest["audio"]["assets"])
        or set(assets) != set(old_assets) | EXTRA_IDS
        or set(build["new_word_ids"]) != EXTRA_IDS
        or len(build["new_word_ids"]) != 12
        or len(manifest["audio"]["required_word_ids"]) != 111
        or any(assets[wid] != asset for wid, asset in old_assets.items())
        or set(manifest["audio"]["required_word_ids"]) != set(assets)
    ):
        raise ValueError("expected original99 plus exact12 asset bindings")
    overlay = json.loads(json.dumps(content))
    for word in overlay["words"]:
        word["audio_us"] = f"/audio/us/{word['word_id']}.mp3" if word["word_id"] in assets else None
    if (
        manifest["content"]["path"] != "content/generated/core_300_audio_candidate.json"
        or hashlib.sha256(
            (json.dumps(overlay, ensure_ascii=False, indent=2) + "\n").encode()
        ).hexdigest()
        != manifest["content"]["sha256"]
    ):
        raise ValueError("Core300 derived content binding differs")
    selected = []
    for wid in sorted(EXTRA_IDS):
        asset = assets[wid]
        if (
            asset["path"] != f"us/{wid}.mp3"
            or not 0 < asset["bytes"] <= 10 * 1024 * 1024
            or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"])
            or build["sources"][wid]["sha256"] != asset["sha256"]
        ):
            raise ValueError("increment audio identity/path differs")
        word = words[wid].copy()
        if (
            word["level"] != "beginner"
            or word["content_status"] == "disabled"
            or word.get("minimal_pair_group") is not None
        ):
            raise ValueError("unexpected increment source status")
        word["audio_us"] = f"/audio/{asset['path']}"
        selected.append(word)
    if (
        import_structure_errors(selected)
        or validate_words(selected, load_phoneme_set(root / "content/phonemes.json"))["errors"]
    ):
        raise ValueError("invalid increment source fields/tags")
    credits = manifest["audio"]["credits"]
    VERIFIER._credits_relative(credits)
    if identities["deploy/jingyun/core300-audio-attribution.md"] != credits["sha256"]:
        raise ValueError("increment attribution binding differs")
    original, corrections = load_corrections(root)
    original = derive(original, corrections)
    for word in original["words"]:
        word["audio_us"] = (
            f"/audio/us/{word['word_id']}.mp3" if word["word_id"] in old_assets else None
        )
    pairs = load_pairs(root)
    return (
        selected,
        [assets[wid] for wid in sorted(EXTRA_IDS)],
        original["words"],
        pairs,
        identities,
        credits,
    )


def prepare_media(root: Path, audio_root: Path, cache_root: Path, validate_media=False):
    _, assets, _, _, identities, credits = source(root)
    payloads = []
    for asset in assets:
        cached = VERIFIER._regular_under(cache_root, asset["sha256"] + ".mp3")
        data = cached.read_bytes()
        if len(data) != asset["bytes"] or hashlib.sha256(data).hexdigest() != asset["sha256"]:
            raise ValueError("cached increment recording differs")
        payloads.append((asset, data))
    allowed = (
        root / "audio"
        if root.resolve() in audio_root.resolve().parents
        else Path(tempfile.gettempdir()).resolve()
    )
    audio_root = _directory(audio_root, allowed)
    _directory(audio_root / "us", audio_root)
    for asset, data in payloads:
        target = audio_root / asset["path"]
        _write(target, data, asset["sha256"])
        if validate_media:
            check_media(target)
    _write(
        audio_root / credits["path"],
        (root / "deploy/jingyun/core300-audio-attribution.md").read_bytes(),
        credits["sha256"],
    )
    media(audio_root, assets)
    return {
        "status": "twelve_assets_prepared",
        "audio_count": 12,
        "audio_bytes": sum(a["bytes"] for a in assets),
        "assets": assets,
        "attribution_metadata": credits,
        "source_bindings": identities,
        "database_changed": False,
        "retained_on_failure": True,
    }


def plan(conn, root: Path, audio_root: Path):
    words, assets, original, pairs, identities, credits = source(root)
    schema(
        conn,
        {
            "words": COLUMNS,
            "phonemes": ("id", "accent_scope"),
            "users": ("id",),
            "settings": ("user_id",),
            "daily_sessions": ("id", "status", "group_type"),
            "session_items": ("id", "session_id", "word_id"),
            "attempts": ("id",),
            "phoneme_stats": ("user_id",),
            "auth_sessions": ("id",),
        },
    )
    ids = catalog(conn, root)
    media(audio_root, assets)
    credit_file = VERIFIER._regular_under(audio_root, credits["path"])
    if hashlib.sha256(credit_file.read_bytes()).hexdigest() != credits["sha256"]:
        raise ValueError("prepared increment attribution differs")
    known = {r[0] for r in conn.execute("SELECT id FROM phonemes")}
    if known != load_phoneme_set(root / "content/phonemes.json"):
        raise ValueError("existing phoneme inventory differs")
    us = {r[0] for r in conn.execute("SELECT id FROM phonemes WHERE accent_scope IN ('US','both')")}
    if any(set(w["phoneme_tags_us"]) - us for w in words):
        raise ValueError("existing US phonemes do not support increment")
    rows = {
        r[0]: dict(zip(COLUMNS, r))
        for r in conn.execute("SELECT " + ",".join(COLUMNS) + " FROM words ORDER BY id")
    }
    pair_groups = {m["word_id"]: pair["group"] for pair in pairs["pairs"] for m in pair["members"]}
    pair_state = {wid: rows[wid]["minimal_pair_group"] for wid in sorted(PAIR_IDS)}
    if pair_state not in ({wid: None for wid in sorted(PAIR_IDS)}, pair_groups):
        raise ValueError("original pair state must be all off or exact eight enabled")
    for word in original:
        expected = stored(word)
        if word["word_id"] in PAIR_IDS:
            expected["minimal_pair_group"] = pair_state[word["word_id"]]
        if rows[word["word_id"]] != expected:
            raise ValueError(f"original100 content drift: {word['word_id']}")
    targets = [stored(word) for word in words]
    present = [row["id"] for row in targets if row["id"] in rows]
    if present and (len(present) != 12 or any(rows[t["id"]] != t for t in targets)):
        raise ValueError(
            "partial/conflicting increment rows; refusing UPSERT: "
            + json.dumps(
                {
                    "present_ids": present,
                    "conflicting_fields": {
                        t["id"]: [c for c in COLUMNS if rows[t["id"]][c] != t[c]]
                        for t in targets
                        if t["id"] in rows and rows[t["id"]] != t
                    },
                },
                sort_keys=True,
            )
        )
    inserts = [] if present else targets
    return reviewed(
        {
            "action": "insert_core300_twelve",
            "source_bindings": identities,
            "catalog_ids": ids,
            "original100_state_sha256": digest([rows[w["word_id"]] for w in original]),
            "pair_state": pair_state,
            "existing_increment": [rows[wid] for wid in present],
            "insert_fields": list(COLUMNS),
            "inserts": inserts,
            "change_count": len(inserts),
            "assets": assets,
            "attribution_metadata": credits,
        }
    )


def apply(conn, root, audio_root, expected):
    def write(current):
        for row in current["inserts"]:
            conn.execute(
                "INSERT INTO words ("
                + ",".join(COLUMNS)
                + ") VALUES ("
                + ",".join("?" for _ in COLUMNS)
                + ")",
                [row[c] for c in COLUMNS],
            )

    return transaction(conn, expected, lambda: plan(conn, root, audio_root), write)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--prepare-media", action="store_true")
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--check-media", action="store_true")
    parser.add_argument("--apply-plan-sha256")
    args = parser.parse_args()
    if args.prepare_media:
        if not args.cache_root or args.db or args.apply_plan_sha256:
            parser.error("media preparation requires cache, without DB/apply")
        result = prepare_media(args.repo_root, args.audio_root, args.cache_root, args.check_media)
    else:
        if not args.db:
            parser.error("DB plan/apply requires explicit --db")
        conn = database(args.db, args.apply_plan_sha256)
        try:
            result = (
                apply(conn, args.repo_root, args.audio_root, args.apply_plan_sha256)
                if args.apply_plan_sha256
                else plan(conn, args.repo_root, args.audio_root)
            )
        finally:
            conn.close()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
