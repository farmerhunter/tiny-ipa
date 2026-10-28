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

from correct_core100_tags import derive, load_corrections  # noqa: E402
from report_choose_word_distractors import _word_from_entry  # noqa: E402
from select_candidates import parse_ipa_to_phonemes  # noqa: E402
from validate_content import load_phoneme_set, validate_words  # noqa: E402

from app.services.distractors import build_choose_word_quality_report  # noqa: E402


def tag_differences(words: list[dict], accent: str = "us") -> list[dict]:
    differences = []
    for word in words:
        ipa = word.get(f"ipa_{accent}")
        if not ipa:
            continue
        parsed, unknown = parse_ipa_to_phonemes(ipa)
        declared = set(word.get(f"phoneme_tags_{accent}") or [])
        removed, added = set(parsed) - declared, declared - set(parsed)
        explained_added, explained_removed = set(), set()
        if accent == "us" and word.get("_phoneme_override_note"):
            for source, target in [("/ə/", "/ʌ/"), ("/ɝ/", "/ɚ/")]:
                if source in parsed and target in added:
                    explained_added.add(target)
                    explained_removed.add(source)
        if removed or added or unknown:
            differences.append(
                {
                    "word_id": word["word_id"],
                    f"ipa_{accent}": ipa,
                    "parsed_tags": parsed,
                    "declared_tags": sorted(declared),
                    "override_note": word.get("_phoneme_override_note"),
                    "unknown_symbols": unknown,
                    "normalization_additions": sorted(explained_added),
                    "unexplained_missing_tags": sorted(removed - explained_removed),
                    "unexplained_added_tags": sorted(added - explained_added),
                }
            )
    return differences


def audit_pack(source: Path, manifest: dict, known: set[str]) -> dict:
    words = json.loads(source.read_text())["words"]
    assets = {a["word_id"]: a for a in manifest["audio"]["assets"]}
    referenced, bound, candidates, unbound = [], [], [], []
    for word in words:
        word_id = word["word_id"]
        asset = assets.get(word_id)
        url = word.get("audio_us")
        if url:
            referenced.append(word_id)
            if asset and url == f"/audio/{asset['path']}":
                bound.append(word_id)
            else:
                unbound.append(word_id)
        elif asset:
            candidates.append(word_id)
    audio_manifest = {"audio": {"required_word_ids": bound}}
    report = audit_content(words, audio_manifest, known)
    report["scope"] = f"{source.relative_to(ROOT)} source references; no import or live database"
    report["audio_binding"] = {
        "source_url_count": len(referenced),
        "manifest_bound_reference_word_ids": sorted(bound),
        "unbound_reference_word_ids": sorted(unbound),
        "manifest_candidates_without_source_url": sorted(candidates),
        "source_status_counts": dict(
            sorted(Counter(w.get("audio_status_us") or "unspecified" for w in words).items())
        ),
        "limit": (
            "Exact word_id + URL binding to the existing package manifest only; "
            "no live availability or phonetic certification. Mid aliases are not inferred."
        ),
    }
    report["declared_us_phoneme_coverage"] = dict(
        sorted(Counter(tag for word in words for tag in set(word["phoneme_tags_us"])).items())
    )
    report["choose_word_excluded_word_ids"] = sorted(
        w["word_id"]
        for w in words
        if w.get("content_status") == "disabled" or not w.get("word") or not w.get("ipa_us")
    )
    pair_counts = Counter(
        w["minimal_pair_group"]
        for w in words
        if w.get("minimal_pair_group") and w.get("content_status") != "disabled"
    )
    report["sound_compare_metadata"] = {
        "tagged_words": sum(pair_counts.values()),
        "groups_with_two_or_more_words": sorted(
            key for key, count in pair_counts.items() if count >= 2
        ),
        "limit": "Metadata eligibility only; not ordered minimal-pair or recording certification.",
    }
    report["uk_ipa_tag_differences"] = tag_differences(words, "uk")
    report["missing_uk_ipa_word_ids"] = sorted(w["word_id"] for w in words if not w.get("ipa_uk"))
    _, corrections = load_corrections()
    by_id = {w["word_id"]: w for w in words}
    report["core100_patch_applicability"] = {
        "exact_before_word_ids": sorted(
            c["word_id"]
            for c in corrections["changes"]
            if c["word_id"] in by_id and by_id[c["word_id"]]["phoneme_tags_us"] == c["before"]
        ),
        "limit": (
            "Exact IDs and tag-before values only, not authorization to apply; Mid IDs excluded."
        ),
    }
    return report


def audit_content(words: list[dict], manifest: dict, known: set[str]) -> dict:
    audio_ids = set(manifest["audio"]["required_word_ids"])
    word_ids = {w["word_id"] for w in words}
    differences = tag_differences(words)
    coverage = Counter()
    for word in words:
        if word["word_id"] in audio_ids:
            coverage.update(set(word["phoneme_tags_us"]))
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
                    "phoneme_stats_after_replay": attempts[0].json()["updated_phonemes"],
                    "replayed_responses": sum(r.json().get("replayed", False) for r in attempts),
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
    parser.add_argument(
        "--all-packs",
        action="store_true",
        help="also audit Core300/Core1000 source references without importing",
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
    content, corrections = load_corrections()
    report["corrected_candidate"] = audit_content(
        derive(content, corrections)["words"],
        json.loads(manifest.read_text()),
        load_phoneme_set(ROOT / "content/phonemes.json"),
    )
    if args.all_packs:
        sources = [ROOT / f"content/core_{size}_words.json" for size in (300, 1000)]
        report["expanded_packs"] = {
            source.stem: audit_pack(
                source,
                json.loads(manifest.read_text()),
                load_phoneme_set(ROOT / "content/phonemes.json"),
            )
            for source in sources
        }
        report["inputs"].update(
            {
                source.relative_to(ROOT).as_posix(): hashlib.sha256(source.read_bytes()).hexdigest()
                for source in sources
            }
        )
    report["inputs"]["content/core_100_phoneme_corrections.json"] = hashlib.sha256(
        (ROOT / "content/core_100_phoneme_corrections.json").read_bytes()
    ).hexdigest()
    if args.probe_attempts:
        report["attempt_semantics_probe"] = probe_attempt_semantics()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
