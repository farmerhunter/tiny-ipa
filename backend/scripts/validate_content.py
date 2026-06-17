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
from collections import defaultdict
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
KNOWN_DIFFICULTY_TAGS = {
    "broad_a",
    "ch",
    "cup_vowel",
    "diphthong",
    "j",
    "l",
    "long_i",
    "long_u",
    "ng",
    "open_o",
    "r",
    "r_schwa",
    "r_stressed",
    "schwa",
    "sh",
    "short_a",
    "short_e",
    "short_i",
    "short_u",
    "th_voiced",
    "th_voiceless",
    "v",
    "w",
    "zh",
}


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_phoneme_inventory(phonemes_path: Path) -> Dict[str, dict]:
    """Load known phoneme entries keyed by symbol from phonemes.json."""
    data = load_json(phonemes_path)
    inventory = {}
    for category in ("vowels", "consonants"):
        for entry in data.get(category, []):
            inventory[entry["symbol"]] = entry
    return inventory


def load_phoneme_set(phonemes_path: Path) -> Set[str]:
    """Load known phoneme symbols from phonemes.json."""
    return set(load_phoneme_inventory(phonemes_path))


def load_coverage_targets(config_path: Path) -> Dict[str, int]:
    """Load US phoneme coverage thresholds from selection_config.json."""
    if not config_path.exists():
        return {}
    data = load_json(config_path)
    targets = data.get("phoneme_coverage_targets_us", {})
    if not isinstance(targets, dict):
        raise ValueError("Expected phoneme_coverage_targets_us to be an object")
    return {str(phoneme): int(minimum) for phoneme, minimum in targets.items()}


def load_blocklisted_words(blocklist_path: Path) -> Set[str]:
    """Load blocked word strings from blocklists.json."""
    if not blocklist_path.exists():
        return set()
    data = load_json(blocklist_path)
    words = data.get("words", [])
    if not isinstance(words, list):
        raise ValueError("Expected blocklists.json 'words' to be an array")
    return {str(word).strip().lower() for word in words if str(word).strip()}


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
    coverage_targets_us: Optional[Dict[str, int]] = None,
    priority_phonemes: Optional[Set[str]] = None,
    blocklisted_words: Optional[Set[str]] = None,
) -> dict:
    """Validate a list of word entries and return a content report."""
    del primary_accent
    coverage_targets_us = coverage_targets_us or {}
    priority_phonemes = priority_phonemes or set()
    blocklisted_words = blocklisted_words or set()

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
        "unknown_difficulty_tags": [],
        "blocked_words": [],
        "duplicate_ipa_with_different_words": [],
        "coverage_targets_us": dict(coverage_targets_us),
        "coverage_failures_us": [],
        "priority_phoneme_coverage_us": {},
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
    active_ipa_us_by_word: dict[str, list[str]] = defaultdict(list)

    for i, w in enumerate(words):
        word_id = w.get("word_id", f"<index {i}>")
        word = str(w.get("word", "")).strip().lower()
        content_status = w.get("content_status")

        if word and content_status != "disabled":
            ipa_us = str(w.get("ipa_us", "")).strip()
            if ipa_us:
                active_ipa_us_by_word[ipa_us].append(word)

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
            report["warnings"].append(f"{word_id}: missing optional field 'ipa_uk'")
        if (
            "phoneme_tags_uk" not in w
            or w["phoneme_tags_uk"] is None
            or w["phoneme_tags_uk"] == ""
        ):
            report["missing_phoneme_tags_uk"] += 1
            report["warnings"].append(
                f"{word_id}: missing optional field 'phoneme_tags_uk'"
            )

        # Optional fields
        if "meaning_zh" not in w or not w.get("meaning_zh"):
            report["missing_meaning_zh"] += 1
            report["errors"].append(f"{word_id}: missing required Core 300 field 'meaning_zh'")

        if not w.get("audio_us"):
            report["missing_audio_us"] += 1
            report["warnings"].append(f"{word_id}: missing optional field 'audio_us'")

        if word in blocklisted_words:
            entry = f"{word_id}: blocked word '{w.get('word')}'"
            report["blocked_words"].append(entry)
            report["errors"].append(entry)

        # Validate phoneme_tags_us against known phonemes
        phoneme_tags_us = w.get("phoneme_tags_us", [])
        if isinstance(phoneme_tags_us, list):
            for tag in phoneme_tags_us:
                report["words_per_phoneme_us"][tag] += 1
                if tag not in known_phonemes:
                    entry = f"{word_id}: unknown phoneme tag '{tag}'"
                    if entry not in report["unknown_phoneme_tags_us"]:
                        report["unknown_phoneme_tags_us"].append(entry)
                    report["errors"].append(entry)
        elif phoneme_tags_us:
            report["errors"].append(f"{word_id}: phoneme_tags_us must be an array")

        # Validate phoneme_tags_uk (warn if missing, validate if present)
        phoneme_tags_uk = w.get("phoneme_tags_uk", [])
        if isinstance(phoneme_tags_uk, list):
            for tag in phoneme_tags_uk:
                report["words_per_phoneme_uk"][tag] += 1
                if tag not in known_phonemes:
                    entry = f"{word_id}: unknown phoneme tag '{tag}' (UK)"
                    if entry not in report["unknown_phoneme_tags_uk"]:
                        report["unknown_phoneme_tags_uk"].append(entry)
                    report["warnings"].append(entry)
        elif phoneme_tags_uk:
            report["warnings"].append(f"{word_id}: phoneme_tags_uk must be an array")

        difficulty_tags = w.get("difficulty_tags", [])
        if isinstance(difficulty_tags, list):
            for tag in difficulty_tags:
                if tag not in KNOWN_DIFFICULTY_TAGS:
                    entry = f"{word_id}: unknown difficulty tag '{tag}'"
                    report["unknown_difficulty_tags"].append(entry)
                    report["errors"].append(entry)
        elif difficulty_tags:
            report["errors"].append(f"{word_id}: difficulty_tags must be an array")

        # Validate level
        level = w.get("level")
        if level and level not in KNOWN_LEVELS:
            entry = f"{word_id}: unknown level '{level}'"
            report["invalid_level"].append(entry)
            report["errors"].append(entry)

        # Validate content_status
        if content_status and content_status not in KNOWN_CONTENT_STATUSES:
            entry = f"{word_id}: unknown content_status '{content_status}'"
            report["invalid_content_status"].append(entry)
            report["errors"].append(entry)

        # Validate review_status fields
        for rs_field in ("review_status_us", "review_status_uk"):
            rs_val = w.get(rs_field)
            if rs_val and rs_val not in KNOWN_REVIEW_STATUSES:
                entry = f"{word_id}: unknown {rs_field} '{rs_val}'"
                report["invalid_review_status"].append(entry)
                report["errors"].append(entry)

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

    for ipa_us, ipa_words in sorted(active_ipa_us_by_word.items()):
        unique_words = sorted(set(ipa_words))
        if len(unique_words) <= 1:
            continue
        for word in unique_words:
            if any(
                other != word
                and 2 <= len(word) <= 4
                and len(other) >= len(word) + 2
                and other.startswith(word)
                for other in unique_words
            ):
                entry = (
                    f"ipa_us {ipa_us}: word '{word}' shares IPA with "
                    f"longer word(s) {unique_words}"
                )
                report["duplicate_ipa_with_different_words"].append(entry)
                report["errors"].append(entry)
                break

    # Build phoneme coverage
    for phoneme in known_phonemes:
        count = report["words_per_phoneme_us"].get(phoneme, 0)
        report["phoneme_coverage_us"][phoneme] = count
    for phoneme, minimum in sorted(coverage_targets_us.items()):
        count = report["phoneme_coverage_us"].get(phoneme, 0)
        if count < minimum:
            failure = {"phoneme": phoneme, "count": count, "minimum": minimum}
            report["coverage_failures_us"].append(failure)
            report["errors"].append(
                f"coverage: {phoneme} has {count} word(s), minimum {minimum}"
            )
    for phoneme in sorted(priority_phonemes):
        report["priority_phoneme_coverage_us"][phoneme] = report[
            "phoneme_coverage_us"
        ].get(phoneme, 0)

    report["phoneme_coverage_uk"] = {}
    for phoneme in known_phonemes:
        count = report["words_per_phoneme_uk"].get(phoneme, 0)
        report["phoneme_coverage_uk"][phoneme] = count

    return report


_AUDIO_SANITY_MIN_BYTES = 128
_EXPECTED_AUDIO_PREFIX: dict[str, str] = {"us": "/audio/us/", "uk": "/audio/uk/"}


def _check_audio_files(words: List[dict], audio_dir: Path, accent: str) -> dict:
    """Check that audio files exist, are non-empty, and have correct path prefix.

    Returns a report dict with ``missing_files``, ``empty_files``,
    ``invalid_prefix``, ``checked``, and ``found_ok`` counts.
    """
    audio_report: dict = {
        "missing_files": [],
        "empty_files": [],
        "invalid_prefix": [],
        "checked": 0,
        "found_ok": 0,
    }
    audio_field = f"audio_{accent}"
    expected_prefix = _EXPECTED_AUDIO_PREFIX.get(accent, f"/audio/{accent}/")

    for w in words:
        path_str = w.get(audio_field)
        if not path_str:
            continue
        audio_report["checked"] += 1
        wid = w.get("word_id") or w.get("word", "")

        # Validate accent-specific prefix (e.g. /audio/us/ for US)
        if not path_str.startswith(expected_prefix):
            audio_report["invalid_prefix"].append({
                "word_id": wid,
                "path": path_str,
                "expected_prefix": expected_prefix,
            })
            continue

        # Strip /audio/ prefix to resolve relative to audio_dir
        # path_str is "/audio/us/ship.mp3" -> rel = "us/ship.mp3"
        rel = path_str.lstrip("/")
        if rel.startswith("audio/"):
            rel = rel[len("audio/"):]
        file_path = audio_dir / rel

        if not file_path.exists():
            audio_report["missing_files"].append({
                "word_id": wid, "path": str(file_path),
            })
        elif file_path.stat().st_size < _AUDIO_SANITY_MIN_BYTES:
            audio_report["empty_files"].append({
                "word_id": wid, "path": str(file_path),
                "size": file_path.stat().st_size,
            })
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
    print("--- Unknown difficulty tags ---")
    if report["unknown_difficulty_tags"]:
        for entry in report["unknown_difficulty_tags"]:
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

    print()
    print("--- Core 300 coverage thresholds (US) ---")
    if not report["coverage_targets_us"]:
        print("  (none configured)")
    elif report["coverage_failures_us"]:
        for failure in report["coverage_failures_us"]:
            print(
                f"  {failure['phoneme']}: {failure['count']} "
                f"(minimum {failure['minimum']})"
            )
    else:
        print("  (all configured thresholds met)")

    print()
    print("--- Priority phoneme coverage (US) ---")
    if report["priority_phoneme_coverage_us"]:
        for phoneme, count in report["priority_phoneme_coverage_us"].items():
            print(f"  {phoneme}: {count}")
    else:
        print("  (none configured)")

    # Audio validation section
    audio = report.get("audio_validation")
    if audio:
        print()
        print("--- Audio file validation ---")
        print(f"Audio files checked:  {audio['checked']}")
        print(f"Files found OK:       {audio['found_ok']}")
        print(f"Missing files:        {len(audio['missing_files'])}")
        print(f"Invalid prefix:       {len(audio.get('invalid_prefix', []))}")
        print(f"Empty/too-small files:{len(audio['empty_files'])}")
        if audio.get("invalid_prefix"):
            print("  Invalid prefix:")
            for ip in audio["invalid_prefix"][:10]:
                print(f"    {ip['word_id']}: {ip['path']} (expected {ip['expected_prefix']})")
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

    if warning_count > 0:
        print("--- Sample warnings (first 10) ---")
        for warning in report["warnings"][:10]:
            print(f"  {warning}")
        print()

    if error_count == 0 and warning_count == 0:
        print("Result: PASS - no validation errors.")
    elif error_count == 0:
        print(f"Result: PASS_WITH_WARNINGS - {warning_count} warning(s).")
    else:
        print(f"Result: FAIL - {error_count} validation error(s), {warning_count} warning(s).")


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
        "--coverage-config",
        default=None,
        help=(
            "Path to selection_config.json for Core 300 coverage thresholds "
            "(default: content/selection_config.json if present)."
        ),
    )
    parser.add_argument(
        "--blocklist",
        default=None,
        help=(
            "Path to blocklists.json for unsafe/blocked word checks "
            "(default: content/blocklists.json if present)."
        ),
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

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    if args.coverage_config:
        coverage_config_path = Path(args.coverage_config)
    elif words_path.name == "core_300_words.json":
        coverage_config_path = repo_root / "content" / "selection_config.json"
    else:
        coverage_config_path = None
    blocklist_path = (
        Path(args.blocklist)
        if args.blocklist
        else repo_root / "content" / "blocklists.json"
    )

    words = load_words(words_path)
    phoneme_inventory = load_phoneme_inventory(phonemes_path)
    known_phonemes = set(phoneme_inventory)
    priority_phonemes = {
        symbol for symbol, entry in phoneme_inventory.items() if entry.get("priority") == 1
    }
    report = validate_words(
        words,
        known_phonemes,
        args.accent,
        coverage_targets_us=(
            load_coverage_targets(coverage_config_path) if coverage_config_path else {}
        ),
        priority_phonemes=priority_phonemes,
        blocklisted_words=load_blocklisted_words(blocklist_path),
    )

    # ---- audio file check (opt-in) -------------------------------------------
    if args.check_audio_files:
        audio_dir = Path(args.check_audio_files)
        audio_report = _check_audio_files(words, audio_dir, args.accent.lower())
        report["audio_validation"] = audio_report
        # Missing static audio is visible but non-blocking for M6 content validation.
        for entry in audio_report["missing_files"]:
            report["warnings"].append(
                f"{entry['word_id']}: audio file missing - {entry['path']}"
            )
        for entry in audio_report["empty_files"]:
            report["warnings"].append(
                f"{entry['word_id']}: audio file too small "
                f"({entry['size']} bytes) - {entry['path']}"
            )
        for entry in audio_report["invalid_prefix"]:
            report["errors"].append(
                f"{entry['word_id']}: invalid audio path prefix - "
                f"{entry['path']} (expected {entry['expected_prefix']})"
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
