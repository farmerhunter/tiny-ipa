#!/usr/bin/env python3
"""Promote generated Core 1000 candidates into a Mid runtime content set."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from curate_core_100 import PHONEME_OVERRIDES, assign_difficulty_tags  # noqa: E402
from select_candidates import estimate_syllable_count, syllable_bucket  # noqa: E402

DEFAULT_CANDIDATES = _REPO / "content" / "generated" / "core_1000_candidates.json"
DEFAULT_POOL = _REPO / "content" / "generated" / "candidate_words.json"
DEFAULT_CORE300 = _REPO / "content" / "core_300_words.json"
DEFAULT_MID_MEANINGS = _REPO / "content" / "core_1000_meanings_zh.json"
DEFAULT_OUTPUT = _REPO / "content" / "core_1000_words.json"
DEFAULT_REPORT = _REPO / "content" / "core_1000_curation_report.json"

CORE_1000_TARGETS = {"one": 250, "two": 500, "three_plus": 250}
VOWEL_LETTER_RE = re.compile(r"[aeiouy]")
ASCII_WORD_RE = re.compile(r"^[a-z]+$")

MANUAL_EXCLUDE_WORDS = {
    "abortion",
    "bomb",
    "casino",
    "corp",
    "death",
    "dvd",
    "feb",
    "http",
    "jail",
    "nfl",
    "tax",
    "tv",
    "vs",
}


def load_word_entries(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("words"), list):
        return data["words"]
    raise ValueError(f"{path} must be a JSON array or object with words")


def load_meaning_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get("meanings"), dict):
        return {
            str(word).strip().lower(): str(meaning).strip()
            for word, meaning in data["meanings"].items()
            if str(word).strip() and str(meaning).strip()
        }
    if isinstance(data, dict) and isinstance(data.get("words"), list):
        entries = data["words"]
    elif isinstance(data, list):
        entries = data
    else:
        raise ValueError(f"{path} must be a JSON array, words object, or meanings object")
    return {
        str(entry.get("word", "")).strip().lower(): str(entry["meaning_zh"]).strip()
        for entry in entries
        if entry.get("word") and entry.get("meaning_zh")
    }


def quality_rejection_reason(entry: dict) -> str | None:
    word = str(entry.get("word", "")).strip().lower()
    if word in MANUAL_EXCLUDE_WORDS:
        return "manual_quality_exclude"
    if not ASCII_WORD_RE.fullmatch(word):
        return "non_ascii_word"
    if len(word) <= 2:
        return "very_short_word"
    if not VOWEL_LETTER_RE.search(word):
        return "no_vowel_letter"
    if not entry.get("ipa_us") or not entry.get("phoneme_tags_us"):
        return "missing_us_pronunciation"
    return None


def _bucket(entry: dict) -> str:
    if entry.get("syllable_bucket_us"):
        return str(entry["syllable_bucket_us"])
    return syllable_bucket(estimate_syllable_count(str(entry.get("ipa_us", ""))))


def _sort_key(entry: dict) -> tuple:
    rank = entry.get("core1000_rank")
    score = entry.get("candidate_score") or 0
    return (
        rank if isinstance(rank, int) else 10_000,
        -float(score),
        str(entry.get("word", "")),
    )


def _unique_source(entries: Iterable[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for entry in entries:
        word = str(entry.get("word", "")).strip().lower()
        if not word or word in seen:
            continue
        seen.add(word)
        unique.append(entry)
    return unique


def curate_core_1000(
    candidates: list[dict],
    pool: list[dict],
    meaning_map: dict[str, str],
    mid_meaning_map: dict[str, str] | None = None,
) -> tuple[list[dict], dict]:
    mid_meaning_map = mid_meaning_map or {}
    source = _unique_source(sorted(candidates, key=_sort_key))
    fallback = _unique_source(sorted(pool, key=_sort_key))
    selected: list[dict] = []
    selected_words: set[str] = set()
    rejection_counts: Counter[str] = Counter()
    rejection_samples: dict[str, list[str]] = {}

    def bucket_count(target_bucket: str) -> int:
        return sum(
            1
            for item in selected
            if item["syllable_bucket_us"] == target_bucket
        )

    def consider(entry: dict, target_bucket: str) -> bool:
        word = str(entry.get("word", "")).strip().lower()
        if word in selected_words or _bucket(entry) != target_bucket:
            return False
        reason = quality_rejection_reason(entry)
        if reason:
            rejection_counts[reason] += 1
            rejection_samples.setdefault(reason, [])
            if len(rejection_samples[reason]) < 10:
                rejection_samples[reason].append(word)
            return False
        selected.append(
            _runtime_entry(entry, len(selected) + 1, meaning_map, mid_meaning_map)
        )
        selected_words.add(word)
        return True

    for target_bucket, target_count in CORE_1000_TARGETS.items():
        for entry in source:
            if bucket_count(target_bucket) >= target_count:
                break
            consider(entry, target_bucket)
        for entry in fallback:
            if bucket_count(target_bucket) >= target_count:
                break
            consider(entry, target_bucket)

    selected.sort(key=lambda item: item["core1000_runtime_rank"])
    report = build_report(selected, rejection_counts, rejection_samples)
    return selected, report


def _runtime_entry(
    src: dict,
    rank: int,
    meaning_map: dict[str, str],
    mid_meaning_map: dict[str, str],
) -> dict:
    entry = dict(src)
    word = str(entry.get("word", "")).strip().lower()
    source_word_id = str(entry.get("word_id") or word)
    if word in meaning_map:
        meaning = meaning_map[word]
        meaning_status = "inherited_core300"
    elif word in mid_meaning_map:
        meaning = mid_meaning_map[word]
        meaning_status = "curated_mid"
    elif entry.get("meaning_zh"):
        meaning = entry["meaning_zh"]
        meaning_status = str(entry.get("meaning_zh_review_status") or "source")
    else:
        meaning = f"待确认：{word}"
        meaning_status = "placeholder"
    entry["source_word_id"] = source_word_id
    entry["word_id"] = f"mid_{source_word_id}"
    entry["word"] = word
    entry["level"] = "intermediate"
    entry["content_status"] = "core_selected"
    entry["review_status_us"] = entry.get("review_status_us") or "auto_checked"
    entry["review_status_uk"] = entry.get("review_status_uk") or (
        "auto_checked" if entry.get("ipa_uk") else "draft"
    )
    entry["meaning_zh"] = meaning
    entry["meaning_zh_review_status"] = meaning_status
    if word in PHONEME_OVERRIDES:
        entry["phoneme_tags_us"] = PHONEME_OVERRIDES[word]
        entry["phoneme_override_note"] = (
            "Reuses accepted Core100 STRUT/r-colored override for ipa-dict "
            "US phoneme coverage."
        )
    entry["difficulty_tags"] = assign_difficulty_tags(entry.get("phoneme_tags_us", []))
    entry["syllable_count_us"] = int(
        entry.get("syllable_count_us")
        or estimate_syllable_count(str(entry.get("ipa_us", "")))
    )
    entry["syllable_bucket_us"] = syllable_bucket(entry["syllable_count_us"])
    entry["core1000_runtime_rank"] = rank
    entry.setdefault("source_ipa_us", "open-dict-data/ipa-dict en_US")
    entry.setdefault("source_ipa_uk", "open-dict-data/ipa-dict en_UK")
    entry.setdefault("source_frequency", "wordfreq")
    entry.setdefault("license_notes", "open-data")
    entry.setdefault("audio_us", None)
    entry.setdefault("audio_uk", None)
    return entry


def build_report(
    selected: list[dict],
    rejection_counts: Counter[str],
    rejection_samples: dict[str, list[str]],
) -> dict:
    distribution: dict[str, dict] = {}
    total = max(len(selected), 1)
    for bucket in ("one", "two", "three_plus", "unknown"):
        count = sum(1 for item in selected if item.get("syllable_bucket_us") == bucket)
        distribution[bucket] = {"count": count, "percent": round(count * 100 / total, 1)}

    placeholder_count = sum(
        1 for item in selected if item.get("meaning_zh_review_status") == "placeholder"
    )
    inherited_count = sum(
        1
        for item in selected
        if item.get("meaning_zh_review_status") == "inherited_core300"
    )
    curated_mid_count = sum(
        1 for item in selected if item.get("meaning_zh_review_status") == "curated_mid"
    )
    override_count = sum(1 for item in selected if item.get("phoneme_override_note"))
    missing_uk_count = sum(1 for item in selected if not item.get("ipa_uk"))
    source_summary = Counter(str(item.get("source_ipa_us", "unknown")) for item in selected)
    license_summary = Counter(str(item.get("license_notes", "unspecified")) for item in selected)

    return {
        "report_title": "Core 1000 Mid runtime curation report",
        "runtime_content_promoted": True,
        "core_1000_count": len(selected),
        "word_id_namespace": "mid_<source_word_id>",
        "syllable_targets": CORE_1000_TARGETS,
        "syllable_distribution_us": distribution,
        "multisyllable_count": distribution["two"]["count"] + distribution["three_plus"]["count"],
        "multisyllable_percent": round(
            (distribution["two"]["count"] + distribution["three_plus"]["count"]) * 100 / total,
            1,
        ),
        "meaning_zh_placeholder_count": placeholder_count,
        "meaning_zh_inherited_core300_count": inherited_count,
        "meaning_zh_curated_mid_count": curated_mid_count,
        "phoneme_override_count": override_count,
        "missing_uk_ipa_count": missing_uk_count,
        "rejection_reasons": dict(rejection_counts),
        "rejection_samples": rejection_samples,
        "source_ipa_us_summary": dict(source_summary),
        "license_summary": dict(license_summary),
        "sample_quality_review": [
            {
                "word": item["word"],
                "ipa_us": item.get("ipa_us"),
                "syllable_bucket_us": item.get("syllable_bucket_us"),
                "meaning_zh_review_status": item.get("meaning_zh_review_status"),
                "source_word_id": item.get("source_word_id"),
            }
            for item in selected[:20]
        ],
        "residual_risks": [
            "missing UK IPA remains non-blocking and visible in validation warnings",
        ],
    }


def write_runtime_file(path: Path, words: list[dict], report: dict) -> None:
    payload = {
        "_note": (
            "Mid/Core1000 runtime content generated from #124 Core1000 candidates. "
            "word_id values use the mid_ namespace so importing Mid content does not "
            "overwrite Entry/Core300 rows. See content/core_1000_curation_report.json "
            "for compact distribution and QA evidence."
        ),
        "_runtime_content_level": "mid",
        "_source_report": "content/core_1000_curation_report.json",
        "_word_count": len(words),
        "_syllable_distribution_us": report["syllable_distribution_us"],
        "words": words,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--pool", default=str(DEFAULT_POOL))
    parser.add_argument("--core-300", default=str(DEFAULT_CORE300))
    parser.add_argument("--mid-meanings", default=str(DEFAULT_MID_MEANINGS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--json", action="store_true", help="Print the compact report as JSON")
    args = parser.parse_args()

    candidates = load_word_entries(Path(args.candidates))
    pool = load_word_entries(Path(args.pool)) if Path(args.pool).exists() else candidates
    meaning_map = load_meaning_map(Path(args.core_300))
    mid_meaning_map = load_meaning_map(Path(args.mid_meanings))
    words, report = curate_core_1000(candidates, pool, meaning_map, mid_meaning_map)
    if len(words) != 1000:
        raise SystemExit(f"Expected 1000 curated words, produced {len(words)}")
    if report["meaning_zh_placeholder_count"]:
        raise SystemExit(
            "Mid/Core1000 curation produced "
            f"{report['meaning_zh_placeholder_count']} placeholder meaning_zh "
            f"entries; update {args.mid_meanings}"
        )

    output_path = Path(args.output)
    report_path = Path(args.report)
    write_runtime_file(output_path, words, report)
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Curated {len(words)} Mid/Core1000 words -> {output_path}")
        print(f"Report -> {report_path}")
        print(f"Syllables: {report['syllable_distribution_us']}")
        print(f"Meaning placeholders: {report['meaning_zh_placeholder_count']}")
        print(f"Missing UK IPA: {report['missing_uk_ipa_count']}")


if __name__ == "__main__":
    main()
