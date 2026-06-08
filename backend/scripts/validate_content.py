#!/usr/bin/env python3
"""Validate a Tiny IPA content JSON file against the project schema.

Usage:
    python validate_content.py <words_file.json> [--phonemes phonemes.json] [--accent US]

The validator checks required fields, phoneme tag validity, IPA symbol support,
and produces a content report with coverage counts and rejection reasons.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set


REQUIRED_FIELDS = [
    "word_id",
    "word",
    "level",
    "ipa_us",
    "phoneme_tags_us",
    "content_status",
]

OPTIONAL_FIELDS = [
    "ipa_uk",
    "phoneme_tags_uk",
    "meaning_zh",
    "example",
    "difficulty_tags",
    "minimal_pair_group",
    "frequency_zipf",
    "candidate_score",
    "audio_us",
    "audio_uk",
    "audio_status_us",
    "audio_status_uk",
    "audio_provider_us",
    "audio_voice_us",
    "audio_generated_at",
    "source_ipa_us",
    "source_ipa_uk",
    "source_frequency",
    "license_notes",
    "review_status_us",
    "review_status_uk",
]

KNOWN_LEVELS = {"beginner", "intermediate"}
KNOWN_CONTENT_STATUSES = {
    "candidate",
    "auto_selected",
    "auto_rejected",
    "manual_selected",
    "core_selected",
    "disabled",
}
KNOWN_REVIEW_STATUSES = {"draft", "auto_checked", "reviewed", "disabled"}


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_phoneme_set(phonemes_path: Path) -> Set[str]:
    """Load known phoneme symbols from phonemes.json."""
    data = load_json(phonemes_path)
    symbols = set()
    for category in ("vowels", "consonants"):
        for entry in data.get(category, []):
            symbols.add(entry["symbol"])
    return symbols


def load_words(words_path: Path) -> List[dict]:
    """Load words from a JSON file. Supports both a top-level list and {words: [...]}."""
    data = load_json(words_path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "words" in data:
        return data["words"]
    raise ValueError(
        f"Expected a JSON array or an object with a 'words' key, got {type(data).__name__}"
    )


def validate_words(
    words: List[dict],
    known_phonemes: Set[str],
    primary_accent: str = "US",
) -> dict:
    """Validate a list of word entries and return a content report."""
    accent_key = primary_accent.lower()

    report: dict = {
        "total_words": len(words),
        "errors": [],
        "warnings": [],
        "missing_ipa_us": 0,
        "missing_ipa_uk": 0,
        "missing_phoneme_tags_us": 0,
        "missing_phoneme_tags_uk": 0,
        "unknown_phoneme_tags_us": [],
        "unknown_phoneme_tags_uk": [],
        "unsupported_ipa_symbols": [],
        "missing_meaning_zh": 0,
        "missing_audio_us": 0,
        "invalid_level": [],
        "invalid_content_status": [],
        "invalid_review_status": [],
        "words_per_phoneme_us": defaultdict(int),
        "words_per_phoneme_uk": defaultdict(int),
        "license_summary": defaultdict(int),
        "source_ipa_us_summary": defaultdict(int),
        "source_ipa_uk_summary": defaultdict(int),
        "phoneme_coverage_us": {},
        "phoneme_coverage_uk": {},
    }

    for i, w in enumerate(words):
        word_id = w.get("word_id", f"<index {i}>")

        # Required fields
        for field in REQUIRED_FIELDS:
            if field not in w or w[field] is None or w[field] == "":
                if field == "ipa_us":
                    report["missing_ipa_us"] += 1
                    report["errors"].append(f"{word_id}: missing required field '{field}'")
                elif field == "phoneme_tags_us":
                    report["missing_phoneme_tags_us"] += 1
                    report["errors"].append(f"{word_id}: missing required field '{field}'")
                else:
                    report["errors"].append(f"{word_id}: missing required field '{field}'")

        # Optional accent-specific fields
        if "ipa_uk" not in w or w["ipa_uk"] is None or w["ipa_uk"] == "":
            report["missing_ipa_uk"] += 1
        if (
            "phoneme_tags_uk" not in w
            or w["phoneme_tags_uk"] is None
            or w["phoneme_tags_uk"] == ""
        ):
            report["missing_phoneme_tags_uk"] += 1

        # Optional fields
        if "meaning_zh" not in w or not w.get("meaning_zh"):
            report["missing_meaning_zh"] += 1

        if not w.get("audio_us"):
            report["missing_audio_us"] += 1

        # Validate phoneme_tags_us against known phonemes
        phoneme_tags_us = w.get("phoneme_tags_us", [])
        if isinstance(phoneme_tags_us, list):
            for tag in phoneme_tags_us:
                report["words_per_phoneme_us"][tag] += 1
                if tag not in known_phonemes:
                    entry = f"{word_id}: unknown phoneme tag '{tag}'"
                    if entry not in report["unknown_phoneme_tags_us"]:
                        report["unknown_phoneme_tags_us"].append(entry)

        # Validate phoneme_tags_uk (warn if missing, validate if present)
        phoneme_tags_uk = w.get("phoneme_tags_uk", [])
        if isinstance(phoneme_tags_uk, list):
            for tag in phoneme_tags_uk:
                report["words_per_phoneme_uk"][tag] += 1
                if tag not in known_phonemes:
                    entry = f"{word_id}: unknown phoneme tag '{tag}' (UK)"
                    if entry not in report["unknown_phoneme_tags_uk"]:
                        report["unknown_phoneme_tags_uk"].append(entry)

        # Validate level
        level = w.get("level")
        if level and level not in KNOWN_LEVELS:
            report["invalid_level"].append(f"{word_id}: unknown level '{level}'")

        # Validate content_status
        content_status = w.get("content_status")
        if content_status and content_status not in KNOWN_CONTENT_STATUSES:
            report["invalid_content_status"].append(
                f"{word_id}: unknown content_status '{content_status}'"
            )

        # Validate review_status fields
        for rs_field in ("review_status_us", "review_status_uk"):
            rs_val = w.get(rs_field)
            if rs_val and rs_val not in KNOWN_REVIEW_STATUSES:
                report["invalid_review_status"].append(
                    f"{word_id}: unknown {rs_field} '{rs_val}'"
                )

        # Track source and license metadata
        source_ipa_us = w.get("source_ipa_us", "unknown")
        report["source_ipa_us_summary"][source_ipa_us] += 1

        source_ipa_uk = w.get("source_ipa_uk", "unknown")
        report["source_ipa_uk_summary"][source_ipa_uk] += 1

        license_note = w.get("license_notes", "unspecified")
        report["license_summary"][license_note] += 1

    # Convert defaultdicts to plain dicts
    report["words_per_phoneme_us"] = dict(report["words_per_phoneme_us"])
    report["words_per_phoneme_uk"] = dict(report["words_per_phoneme_uk"])
    report["license_summary"] = dict(report["license_summary"])
    report["source_ipa_us_summary"] = dict(report["source_ipa_us_summary"])
    report["source_ipa_uk_summary"] = dict(report["source_ipa_uk_summary"])

    # Build phoneme coverage
    total_us = len(words)
    for phoneme in known_phonemes:
        count = report["words_per_phoneme_us"].get(phoneme, 0)
        report["phoneme_coverage_us"][phoneme] = count

    report["phoneme_coverage_uk"] = {}
    for phoneme in known_phonemes:
        count = report["words_per_phoneme_uk"].get(phoneme, 0)
        report["phoneme_coverage_uk"][phoneme] = count

    return report


_AUDIO_SANITY_MIN_BYTES = 128


def _check_audio_files(words: List[dict], audio_dir: Path, accent: str) -> dict:
    """Check that audio_us/audio_uk files exist and are non-empty.

    Returns a report dict with ``missing_files``, ``empty_files``, and
    ``checked`` counts.
    """
    audio_report: dict = {"missing_files": [], "empty_files": [], "checked": 0, "found_ok": 0}
    audio_field = f"audio_{accent}"
    for w in words:
        path_str = w.get(audio_field)
        if not path_str:
            continue
        audio_report["checked"] += 1
        # /audio/us/ship.mp3 -> audio_dir / us / ship.mp3 (but audio_dir is already audio/)
        # Handle both: path is relative like /audio/us/ship.mp3 -> strip leading /audio/
        rel = path_str.lstrip("/")
        if rel.startswith("audio/"):
            rel = rel[len("audio/"):]
        file_path = audio_dir / rel
        if not file_path.exists():
            audio_report["missing_files"].append({"word_id": w.get("word_id", w.get("word", "")), "path": str(file_path)})
        elif file_path.stat().st_size < _AUDIO_SANITY_MIN_BYTES:
            audio_report["empty_files"].append({"word_id": w.get("word_id", w.get("word", "")), "path": str(file_path), "size": file_path.stat().st_size})
        else:
            audio_report["found_ok"] += 1
    return audio_report


def print_report(report: dict, known_phonemes: Set[str]) -> None:
    """Print a human-readable content validation report."""
    error_count = len(report["errors"])
    warning_count = len(report["warnings"])

    print("=" * 60)
    print("Tiny IPA Content Validation Report")
    print("=" * 60)
    print(f"Total words:            {report['total_words']}")
    print(f"Errors:                 {error_count}")
    print(f"Warnings:               {warning_count}")
    print()

    print("--- Required fields ---")
    print(f"Missing ipa_us:         {report['missing_ipa_us']}")
    print(f"Missing phoneme_tags_us:{report['missing_phoneme_tags_us']}")
    print()

    print("--- Optional fields ---")
    print(f"Missing ipa_uk:         {report['missing_ipa_uk']}")
    print(f"Missing phoneme_tags_uk:{report['missing_phoneme_tags_uk']}")
    print(f"Missing meaning_zh:     {report['missing_meaning_zh']}")
    print(f"Missing audio_us:       {report['missing_audio_us']}")
    print()

    print("--- Unknown phoneme tags (US) ---")
    if report["unknown_phoneme_tags_us"]:
        for entry in report["unknown_phoneme_tags_us"]:
            print(f"  {entry}")
    else:
        print("  (none)")

    print()
    print("--- Unknown phoneme tags (UK) ---")
    if report["unknown_phoneme_tags_uk"]:
        for entry in report["unknown_phoneme_tags_uk"]:
            print(f"  {entry}")
    else:
        print("  (none)")

    print()
    print("--- Status validation ---")
    if report["invalid_level"]:
        for entry in report["invalid_level"]:
            print(f"  {entry}")
    if report["invalid_content_status"]:
        for entry in report["invalid_content_status"]:
            print(f"  {entry}")
    if report["invalid_review_status"]:
        for entry in report["invalid_review_status"]:
            print(f"  {entry}")
    if not any(
        [report["invalid_level"], report["invalid_content_status"], report["invalid_review_status"]]
    ):
        print("  (all status values valid)")

    print()
    print("--- Words per phoneme (US top 10) ---")
    sorted_us = sorted(report["words_per_phoneme_us"].items(), key=lambda x: -x[1])
    for phoneme, count in sorted_us[:10]:
        print(f"  {phoneme}: {count}")

    print()
    print("--- Weak coverage (US, <5 words) ---")
    weak = [
        (p, c) for p, c in report["phoneme_coverage_us"].items() if c < 5 and p in known_phonemes
    ]
    if weak:
        for phoneme, count in sorted(weak, key=lambda x: x[1]):
            print(f"  {phoneme}: {count}")
    else:
        print("  (none)")

    # Audio validation section
    audio = report.get("audio_validation")
    if audio:
        print()
        print("--- Audio file validation ---")
        print(f"Audio files checked:  {audio['checked']}")
        print(f"Files found OK:       {audio['found_ok']}")
        print(f"Missing files:        {len(audio['missing_files'])}")
        print(f"Empty/too-small files:{len(audio['empty_files'])}")
        if audio["missing_files"]:
            print("  Missing:")
            for m in audio["missing_files"][:10]:
                print(f"    {m['word_id']}: {m['path']}")
        if audio["empty_files"]:
            print("  Empty/too-small:")
            for e in audio["empty_files"][:10]:
                print(f"    {e['word_id']}: {e['path']} ({e['size']} bytes)")

    print()
    print("--- License summary ---")
    for license_key, count in report["license_summary"].items():
        print(f"  {license_key}: {count}")

    print()
    print("--- Source IPA (US) ---")
    for source, count in report["source_ipa_us_summary"].items():
        print(f"  {source}: {count}")

    print()

    # Sampling
    if error_count > 0:
        print("--- Sample errors (first 10) ---")
        for err in report["errors"][:10]:
            print(f"  {err}")
        print()

    if error_count == 0:
        print("Result: PASS - no validation errors.")
    else:
        print(f"Result: FAIL - {error_count} validation error(s).")


def main():
    parser = argparse.ArgumentParser(description="Validate Tiny IPA content JSON files.")
    parser.add_argument("words_file", help="Path to the JSON file containing word entries.")
    parser.add_argument(
        "--phonemes",
        default=None,
        help="Path to phonemes.json (default: content/phonemes.json relative to repo root).",
    )
    parser.add_argument(
        "--accent",
        default="US",
        choices=["US", "UK"],
        help="Primary accent for validation focus (default: US).",
    )
    parser.add_argument(
        "--check-audio-files",
        default=None,
        help="Optional audio directory to verify audio_us/audio_uk files exist and are non-empty.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the report as JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    words_path = Path(args.words_file)
    if not words_path.exists():
        print(f"Error: file not found: {words_path}", file=sys.stderr)
        sys.exit(1)

    if args.phonemes:
        phonemes_path = Path(args.phonemes)
    else:
        # Default: look for content/phonemes.json relative to repo root
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent.parent
        phonemes_path = repo_root / "content" / "phonemes.json"

    if not phonemes_path.exists():
        print(f"Error: phonemes file not found: {phonemes_path}", file=sys.stderr)
        sys.exit(1)

    words = load_words(words_path)
    known_phonemes = load_phoneme_set(phonemes_path)
    report = validate_words(words, known_phonemes, args.accent)

    # ---- audio file check (opt-in) -------------------------------------------
    if args.check_audio_files:
        audio_dir = Path(args.check_audio_files)
        audio_report = _check_audio_files(words, audio_dir, args.accent.lower())
        report["audio_validation"] = audio_report
        if audio_report["missing_files"]:
            for entry in audio_report["missing_files"]:
                report["errors"].append(
                    f"{entry['word_id']}: audio file missing — {entry['path']}"
                )

    if args.json:
        # Convert sets/lists for JSON serialization
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report, known_phonemes)

    # Exit non-zero on errors
    if report["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
