#!/usr/bin/env python3
"""Read repository content and report learning-evidence limits, without promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from report_choose_word_distractors import _word_from_entry  # noqa: E402
from select_candidates import parse_ipa_to_phonemes  # noqa: E402
from validate_content import load_phoneme_set, validate_words  # noqa: E402

from app.services.distractors import build_choose_word_quality_report  # noqa: E402


def audit_content(words: list[dict], manifest: dict, known: set[str]) -> dict:
    audio_ids = set(manifest["audio"]["required_word_ids"])
    word_ids = {w["word_id"] for w in words}
    differences = []
    coverage = Counter()
    for word in words:
        parsed, unknown = parse_ipa_to_phonemes(word["ipa_us"])
        declared = set(word["phoneme_tags_us"])
        if word["word_id"] in audio_ids:
            coverage.update(declared)
        removed = set(parsed) - declared
        added = declared - set(parsed)
        explained_added = set()
        if word.get("_phoneme_override_note"):
            for source, target in [("/ə/", "/ʌ/"), ("/ɝ/", "/ɚ/")]:
                if source in parsed and target in added:
                    explained_added.add(target)
        unexplained_removed = removed - {"/ə/", "/ɝ/"} if explained_added else removed
        if removed or added or unknown:
            differences.append(
                {
                    "word_id": word["word_id"],
                    "ipa_us": word["ipa_us"],
                    "parsed_tags": parsed,
                    "declared_tags": sorted(declared),
                    "override_note": word.get("_phoneme_override_note"),
                    "unknown_symbols": unknown,
                    "normalization_additions": sorted(explained_added),
                    "unexplained_missing_tags": sorted(unexplained_removed),
                    "unexplained_added_tags": sorted(added - explained_added),
                }
            )
    validation = validate_words(words, known)
    quality = build_choose_word_quality_report([_word_from_entry(w) for w in words])
    return {
        "scope": "Core100 source + expanded US audio manifest; no live database",
        "word_count": len(words),
        "audio_word_count": len(word_ids & audio_ids),
        "missing_audio_word_ids": sorted(word_ids - audio_ids),
        "unknown_audio_word_ids": sorted(audio_ids - word_ids),
        "audio_phoneme_coverage": dict(sorted(coverage.items())),
        "known_phonemes_without_audio_words": sorted(known - coverage.keys()),
        "ipa_tag_differences": differences,
        "unexplained_tag_word_ids": [
            d["word_id"]
            for d in differences
            if d["unknown_symbols"] or d["unexplained_missing_tags"] or d["unexplained_added_tags"]
        ],
        "schema_errors": validation["errors"],
        "choose_word_distractors": quality,
        "evidence_limits": [
            "Tag parser deduplicates phones; it cannot establish ordered minimal pairs.",
            "Source author metadata does not establish speaker identity or audio/IPA agreement.",
            "Integrity and decoding do not establish phonetic or educational correctness.",
            "Whole-answer correctness updates all target tags; it is not a listening diagnosis.",
        ],
    }


def probe_attempt_semantics() -> dict:
    from fastapi.testclient import TestClient
    from import_words import import_words

    from app import db
    from app.models import User
    from app.services.auth import hash_password
    from app.services.db_store import create_user

    with tempfile.TemporaryDirectory(prefix="tiny-ipa-scoring-audit-") as directory:
        database = str(Path(directory).resolve() / "probe.sqlite")
        environment = {
            "TINY_IPA_ENV": "development",
            "TINY_IPA_DB_PATH": database,
            "TINY_IPA_COOKIE_SECURE": "false",
            "TINY_IPA_REQUIRE_PACKAGED_AUDIO": "false",
            "TINY_IPA_SESSION_SECRET": "disposable-scoring-audit-only",
            "TINY_IPA_ALLOWED_ORIGINS": "http://testserver",
            "TINY_IPA_KEEP_WAL_ANCHOR": "false",
        }
        with patch.dict(os.environ, environment), patch.object(db, "DEFAULT_DB_PATH", database):
            from app.main import create_app

            import_words(
                ROOT / "content/core_100_words.json",
                ROOT / "content/phonemes.json",
                db_path=database,
            )
            with db.get_connection(database) as connection:
                create_user(
                    connection,
                    User(
                        id="default",
                        username="audit-fixture",
                        password_hash=hash_password("audit-only"),
                        is_owner=True,
                        is_active=True,
                        created_at="2026-10-27T00:00:00Z",
                        updated_at="2026-10-27T00:00:00Z",
                    ),
                )
            with TestClient(create_app()) as client:
                login = client.post(
                    "/api/auth/login",
                    json={
                        "username": "audit-fixture",
                        "password": "audit-only",
                    },
                )
                login.raise_for_status()
                response = client.post("/api/practice/next-normal")
                response.raise_for_status()
                item = response.json()["items"][0]
                payload = {
                    "session_item_id": item["session_item_id"],
                    "selected_answer": item["display_ipa"],
                }
                attempts = [client.post("/api/attempt", json=payload) for _ in range(5)]
                for attempt in attempts:
                    attempt.raise_for_status()
                progress = client.get("/api/progress")
                progress.raise_for_status()
                observed = {
                    "scope": "fresh disposable Core100 database and synthetic account only",
                    "word_id": item["word_id"],
                    "unique_submitted_items": 1,
                    "submission_statuses": [r.status_code for r in attempts],
                    "recorded_total_attempts": progress.json()["total_attempts"],
                    "phoneme_stats_after_replay": attempts[-1].json()["updated_phonemes"],
                    "duplicate_attempt_risk": progress.json()["total_attempts"] > 1,
                }
                wrong = response.json()["items"][1]
                result = client.post(
                    "/api/attempt",
                    json={
                        "session_item_id": wrong["session_item_id"],
                        "selected_answer": "/audit-wrong/",
                    },
                )
                result.raise_for_status()
                observed["whole_answer_wrong_updates"] = result.json()["updated_phonemes"]
                observed["whole_answer_wrong_target_tags"] = wrong["target_phonemes"]
                return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe-attempts",
        action="store_true",
        help="also reproduce scoring on a fresh disposable DB, never a live DB",
    )
    args = parser.parse_args()
    source = ROOT / "content/core_100_words.json"
    manifest = ROOT / "deploy/jingyun/core100-content-audio.manifest.json"
    report = audit_content(
        json.loads(source.read_text())["words"],
        json.loads(manifest.read_text()),
        load_phoneme_set(ROOT / "content/phonemes.json"),
    )
    report["inputs"] = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (source, manifest, ROOT / "content/phonemes.json")
    }
    if args.probe_attempts:
        report["attempt_semantics_probe"] = probe_attempt_semantics()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
