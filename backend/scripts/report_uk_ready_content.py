#!/usr/bin/env python3
"""Build the M9 UK-ready content subset and accent coverage report.

This script is intentionally a content/reporting tool. It does not change
learner defaults, grading, API response shapes, or runtime specialty practice.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from validate_content import load_json, load_phoneme_inventory, load_words

DEFAULT_ACCEPTED_UK_REVIEW_STATUSES = {"auto_checked", "reviewed"}
DEFAULT_WORD_FILES = ("content/core_300_words.json", "content/core_1000_words.json")
DEFAULT_SAMPLE_SIZE = 8
DEFAULT_CANDIDATE_LIMIT = 30


def _is_present(value: object) -> bool:
    return value is not None and value != "" and value != []


def _as_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _row_key(row: dict) -> tuple[str, str]:
    return (str(row.get("level", "")), str(row.get("word", "")))


def _source_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        pass
    return path.as_posix()


def load_word_sources(paths: Iterable[Path]) -> list[dict]:
    """Load word rows and attach source-file provenance."""
    rows: list[dict] = []
    seen_word_ids: set[str] = set()
    duplicates: list[str] = []
    for path in paths:
        for row in load_words(path):
            copied = dict(row)
            copied["_source_file"] = _source_label(path)
            word_id = str(copied.get("word_id", ""))
            if word_id in seen_word_ids:
                duplicates.append(word_id)
            seen_word_ids.add(word_id)
            rows.append(copied)
    if duplicates:
        dupes = ", ".join(sorted(set(duplicates))[:10])
        raise ValueError(f"Duplicate word_id values across sources: {dupes}")
    return rows


def load_difficult_contrasts(phonemes_path: Path) -> list[dict]:
    """Load difficult contrast definitions from phonemes.json."""
    data = load_json(phonemes_path)
    contrasts = []
    for entry in data.get("difficult_contrasts", []):
        pair = entry.get("pair")
        if isinstance(pair, list) and len(pair) == 2:
            contrasts.append({
                "pair": [str(pair[0]), str(pair[1])],
                "description_zh": entry.get("description_zh", ""),
            })
    return contrasts


def exclusion_reasons(
    row: dict,
    known_phonemes: set[str],
    accepted_uk_review_statuses: set[str],
) -> list[str]:
    """Return M9 UK-comparison exclusion reasons for a content row."""
    reasons: list[str] = []
    tags_us = _as_list(row.get("phoneme_tags_us"))
    tags_uk = _as_list(row.get("phoneme_tags_uk"))

    if row.get("content_status") == "disabled":
        reasons.append("content_status is disabled")
    if not _is_present(row.get("ipa_us")):
        reasons.append("missing ipa_us")
    if not _is_present(row.get("ipa_uk")):
        reasons.append("missing ipa_uk")
    if not tags_us:
        reasons.append("missing phoneme_tags_us")
    if not tags_uk:
        reasons.append("missing phoneme_tags_uk")
    review_status_uk = str(row.get("review_status_uk") or "")
    if review_status_uk not in accepted_uk_review_statuses:
        reasons.append(f"review_status_uk '{review_status_uk or '<missing>'}' is not accepted")

    unknown_us = sorted({tag for tag in tags_us if tag not in known_phonemes})
    unknown_uk = sorted({tag for tag in tags_uk if tag not in known_phonemes})
    if unknown_us:
        reasons.append(f"unsupported US phoneme tag(s): {', '.join(unknown_us)}")
    if unknown_uk:
        reasons.append(f"unsupported UK phoneme tag(s): {', '.join(unknown_uk)}")

    return reasons


def _accent_difference_reason(row: dict) -> str:
    reasons: list[str] = []
    if row.get("ipa_us") != row.get("ipa_uk"):
        reasons.append("IPA differs")
    if _as_list(row.get("phoneme_tags_us")) != _as_list(row.get("phoneme_tags_uk")):
        reasons.append("phoneme tags differ")
    return "; ".join(reasons)


def _known_caveat(row: dict) -> str:
    caveats: list[str] = []
    if row.get("review_status_uk") == "auto_checked":
        caveats.append("auto_checked; Architect pronunciation acceptance pending")
    if row.get("audio_uk") in (None, ""):
        caveats.append("no UK audio required for M9 comparison")
    if not _accent_difference_reason(row):
        caveats.append("same broad IPA/tags; comparison value is low")
    return "; ".join(caveats) or "none"


def _sample_reason(row: dict) -> str:
    reason = _accent_difference_reason(row)
    if reason:
        return f"eligible reviewed UK comparison row; {reason}"
    return "eligible reviewed UK comparison row"


def _coverage(rows: list[dict], field: str, known_phonemes: set[str]) -> dict[str, int]:
    counts = Counter()
    for row in rows:
        counts.update(set(_as_list(row.get(field))))
    return {phoneme: counts.get(phoneme, 0) for phoneme in sorted(known_phonemes)}


def _candidate_row(row: dict) -> dict:
    return {
        "word_id": row.get("word_id"),
        "word": row.get("word"),
        "level": row.get("level"),
        "ipa_us": row.get("ipa_us"),
        "ipa_uk": row.get("ipa_uk"),
        "phoneme_tags_us": _as_list(row.get("phoneme_tags_us")),
        "phoneme_tags_uk": _as_list(row.get("phoneme_tags_uk")),
        "review_status_uk": row.get("review_status_uk"),
        "source_file": row.get("_source_file"),
    }


def _accent_difference_candidates(rows: list[dict]) -> list[dict]:
    candidates = []
    for row in sorted(rows, key=_row_key):
        reason = _accent_difference_reason(row)
        if not reason:
            continue
        candidate = _candidate_row(row)
        candidate["reason"] = reason
        candidate["caveat"] = _known_caveat(row)
        candidates.append(candidate)
    return candidates


def _tag_sequence_minimal_pair_candidates(
    rows: list[dict],
    difficult_contrasts: list[dict],
) -> list[dict]:
    contrast_lookup = {}
    for contrast in difficult_contrasts:
        pair = tuple(contrast["pair"])
        contrast_lookup[frozenset(pair)] = contrast.get("description_zh", "")

    candidates = []
    seen_word_pairs: set[tuple[str, str, tuple[str, str]]] = set()
    sorted_rows = sorted(rows, key=_row_key)
    for left_index, left in enumerate(sorted_rows):
        left_tags = _as_list(left.get("phoneme_tags_us"))
        for right in sorted_rows[left_index + 1:]:
            right_tags = _as_list(right.get("phoneme_tags_us"))
            if len(left_tags) != len(right_tags):
                continue
            diffs = [
                (a, b)
                for a, b in zip(left_tags, right_tags)
                if a != b
            ]
            if len(diffs) != 1:
                continue
            contrast_key = frozenset(diffs[0])
            if contrast_key not in contrast_lookup:
                continue
            words_key = tuple(sorted([str(left.get("word")), str(right.get("word"))]))
            contrast_tuple = tuple(sorted(contrast_key))
            candidate_key = (words_key[0], words_key[1], contrast_tuple)
            if candidate_key in seen_word_pairs:
                continue
            seen_word_pairs.add(candidate_key)
            candidates.append({
                "left_word_id": left.get("word_id"),
                "left_word": left.get("word"),
                "right_word_id": right.get("word_id"),
                "right_word": right.get("word"),
                "contrast": sorted(contrast_key),
                "basis": "one phoneme-tag difference in phoneme_tags_us",
                "caveat": (
                    "mechanical candidate only; requires Architect/content review "
                    "before runtime specialty practice"
                ),
                "description_zh": contrast_lookup[contrast_key],
            })
    return candidates


def _target_phoneme_coverage(
    rows: list[dict],
    known_phonemes: set[str],
    phoneme_inventory: dict[str, dict],
) -> list[dict]:
    coverage_us = _coverage(rows, "phoneme_tags_us", known_phonemes)
    coverage_uk = _coverage(rows, "phoneme_tags_uk", known_phonemes)
    result = []
    for phoneme in sorted(known_phonemes):
        entry = phoneme_inventory.get(phoneme, {})
        result.append({
            "phoneme": phoneme,
            "category": entry.get("category"),
            "priority": entry.get("priority"),
            "eligible_words_us": coverage_us.get(phoneme, 0),
            "eligible_words_uk": coverage_uk.get(phoneme, 0),
        })
    return result


def build_uk_ready_report(
    rows: list[dict],
    known_phonemes: set[str],
    phoneme_inventory: dict[str, dict],
    difficult_contrasts: list[dict],
    accepted_uk_review_statuses: set[str] | None = None,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> dict:
    """Build an M9 UK-ready subset and accent coverage report."""
    accepted_uk_review_statuses = (
        accepted_uk_review_statuses or DEFAULT_ACCEPTED_UK_REVIEW_STATUSES
    )

    eligible: list[dict] = []
    excluded: list[dict] = []
    unsupported_uk_symbols = Counter()
    review_status_counts = Counter()
    content_status_counts = Counter()
    missing_uk_ipa_count = 0
    missing_uk_tags_count = 0

    for row in rows:
        review_status_counts[str(row.get("review_status_uk") or "<missing>")] += 1
        content_status_counts[str(row.get("content_status") or "<missing>")] += 1
        if not _is_present(row.get("ipa_uk")):
            missing_uk_ipa_count += 1
        if not _as_list(row.get("phoneme_tags_uk")):
            missing_uk_tags_count += 1
        for tag in _as_list(row.get("phoneme_tags_uk")):
            if tag not in known_phonemes:
                unsupported_uk_symbols[tag] += 1

        reasons = exclusion_reasons(row, known_phonemes, accepted_uk_review_statuses)
        if reasons:
            excluded.append({
                "word_id": row.get("word_id"),
                "word": row.get("word"),
                "review_status_uk": row.get("review_status_uk"),
                "content_status": row.get("content_status"),
                "reasons": reasons,
                "source_file": row.get("_source_file"),
            })
        else:
            eligible.append(row)

    source_ipa_uk_summary = Counter(row.get("source_ipa_uk") or "unknown" for row in eligible)
    source_ipa_us_summary = Counter(row.get("source_ipa_us") or "unknown" for row in eligible)
    license_summary = Counter(row.get("license_notes") or "unspecified" for row in eligible)
    source_file_summary = Counter(row.get("_source_file") or "unknown" for row in eligible)

    all_accent_difference_candidates = _accent_difference_candidates(eligible)
    all_minimal_pair_candidates = _tag_sequence_minimal_pair_candidates(
        eligible,
        difficult_contrasts,
    )
    accent_difference_candidates = all_accent_difference_candidates[:candidate_limit]
    minimal_pair_candidates = all_minimal_pair_candidates[:candidate_limit]
    target_phoneme_coverage = _target_phoneme_coverage(
        eligible,
        known_phonemes,
        phoneme_inventory,
    )

    sample_rows = accent_difference_candidates[:sample_size]
    if len(sample_rows) < sample_size:
        existing_ids = {row["word_id"] for row in sample_rows}
        for row in sorted(eligible, key=_row_key):
            if row.get("word_id") in existing_ids:
                continue
            sample_rows.append({
                **_candidate_row(row),
                "reason": _sample_reason(row),
                "caveat": _known_caveat(row),
            })
            if len(sample_rows) >= sample_size:
                break

    return {
        "report_name": "M9 UK-ready content subset and accent coverage report",
        "content_gate": {
            "accepted_review_status_uk": sorted(accepted_uk_review_statuses),
            "content_quality_acceptance": "Architect/content acceptance required",
            "runtime_scope": "content/report evidence only; no UK grading or UI behavior",
        },
        "totals": {
            "source_rows": len(rows),
            "eligible_rows": len(eligible),
            "excluded_rows": len(excluded),
            "missing_uk_ipa_count": missing_uk_ipa_count,
            "missing_uk_tags_count": missing_uk_tags_count,
            "unsupported_uk_symbol_count": sum(unsupported_uk_symbols.values()),
            "unsupported_uk_symbol_rows": sum(
                1
                for row in rows
                if any(tag not in known_phonemes for tag in _as_list(row.get("phoneme_tags_uk")))
            ),
            "accent_difference_candidate_count": len(all_accent_difference_candidates),
            "minimal_pair_candidate_count": len(all_minimal_pair_candidates),
            "target_phoneme_covered_count_us": sum(
                1 for entry in target_phoneme_coverage if entry["eligible_words_us"] > 0
            ),
            "target_phoneme_covered_count_uk": sum(
                1 for entry in target_phoneme_coverage if entry["eligible_words_uk"] > 0
            ),
        },
        "review_status_uk_counts": dict(sorted(review_status_counts.items())),
        "content_status_counts": dict(sorted(content_status_counts.items())),
        "source_metadata": {
            "source_files": dict(sorted(source_file_summary.items())),
            "source_ipa_us": dict(sorted(source_ipa_us_summary.items())),
            "source_ipa_uk": dict(sorted(source_ipa_uk_summary.items())),
            "license_notes": dict(sorted(license_summary.items())),
        },
        "unsupported_uk_symbols": dict(sorted(unsupported_uk_symbols.items())),
        "eligible_word_ids": [str(row.get("word_id")) for row in sorted(eligible, key=_row_key)],
        "sample_table": [
            {
                "word": row["word"],
                "us_ipa": row["ipa_us"],
                "uk_ipa": row["ipa_uk"],
                "review_status_uk": row["review_status_uk"],
                "reason_included": row["reason"],
                "caveat": row["caveat"],
            }
            for row in sample_rows
        ],
        "accent_difference_candidates": accent_difference_candidates,
        "minimal_pair_candidates": minimal_pair_candidates,
        "target_phoneme_candidate_coverage": target_phoneme_coverage,
        "known_caveats": [
            "UK rows marked auto_checked are mechanically eligible for this report, "
            "but still require Architect/content-quality acceptance before UI use.",
            "UK audio is not required for M9 comparison display.",
            "Minimal-pair candidates are mechanical tag-sequence candidates, not "
            "accepted runtime metadata.",
            "Target-phoneme coverage is candidate coverage only; M9 runtime selection "
            "is intentionally out of scope for this issue.",
        ],
        "excluded_rows_sample": excluded[:candidate_limit],
    }


def _markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        rendered = [str(cell).replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines)


def render_markdown_report(report: dict) -> str:
    """Render a human-readable Markdown report."""
    totals = report["totals"]
    source_metadata = report["source_metadata"]
    sample_rows = [
        [
            row["word"],
            row["us_ipa"],
            row["uk_ipa"],
            row["reason_included"],
            row["caveat"],
        ]
        for row in report["sample_table"]
    ]
    target_rows = [
        [
            row["phoneme"],
            row["category"],
            row["priority"],
            row["eligible_words_us"],
            row["eligible_words_uk"],
        ]
        for row in sorted(
            report["target_phoneme_candidate_coverage"],
            key=lambda item: (item["priority"] or 99, item["phoneme"]),
        )[:20]
    ]
    pair_rows = [
        [
            f"{row['left_word']} / {row['right_word']}",
            ", ".join(row["contrast"]),
            row["basis"],
            row["caveat"],
        ]
        for row in report["minimal_pair_candidates"][:10]
    ]

    lines = [
        "# M9 UK-Ready Content Subset and Accent Coverage Report",
        "",
        "This is the checked-in evidence artifact for issue #196. It is a "
        "content/report snapshot only; it does not enable UK grading, UK primary "
        "accent selection, UK comparison UI/API, minimal-pair runtime, or "
        "target-phoneme runtime behavior.",
        "",
        "## Gate",
        "",
        f"- Accepted `review_status_uk` values for this report: "
        f"{', '.join(report['content_gate']['accepted_review_status_uk'])}",
        "- Content-quality acceptance: Architect/content acceptance required.",
        "- UK comparison remains display-only in later M9 work; US grading remains unchanged.",
        "",
        "## Summary",
        "",
        f"- Source rows: {totals['source_rows']}",
        f"- Eligible UK-ready rows: {totals['eligible_rows']}",
        f"- Excluded rows: {totals['excluded_rows']}",
        f"- Missing UK IPA count: {totals['missing_uk_ipa_count']}",
        f"- Missing UK phoneme tags count: {totals['missing_uk_tags_count']}",
        f"- Unsupported UK symbol count: {totals['unsupported_uk_symbol_count']}",
        f"- Accent-difference candidates: {totals['accent_difference_candidate_count']}",
        f"- Minimal-pair candidates: {totals['minimal_pair_candidate_count']}",
        f"- Target phonemes covered by US tags: {totals['target_phoneme_covered_count_us']}",
        f"- Target phonemes covered by UK tags: {totals['target_phoneme_covered_count_uk']}",
        "",
        "## Sample Table",
        "",
        _markdown_table(
            ["word", "US IPA", "UK IPA", "reason included", "caveat"],
            sample_rows,
        ),
        "",
        "## Source and License Metadata",
        "",
        "Source files:",
        "",
    ]
    for source, count in source_metadata["source_files"].items():
        lines.append(f"- `{source}`: {count}")
    lines.extend(["", "UK IPA sources:", ""])
    for source, count in source_metadata["source_ipa_uk"].items():
        lines.append(f"- {source}: {count}")
    lines.extend(["", "License notes:", ""])
    for license_note, count in source_metadata["license_notes"].items():
        lines.append(f"- {license_note}: {count}")

    lines.extend([
        "",
        "## Review Status Coverage",
        "",
    ])
    for status, count in report["review_status_uk_counts"].items():
        lines.append(f"- `{status}`: {count}")

    lines.extend([
        "",
        "## Minimal-Pair Candidate Sample",
        "",
    ])
    if pair_rows:
        lines.append(_markdown_table(
            ["words", "contrast", "basis", "caveat"],
            pair_rows,
        ))
    else:
        lines.append("No mechanical minimal-pair candidates were found.")

    lines.extend([
        "",
        "## Target-Phoneme Candidate Coverage Sample",
        "",
        _markdown_table(
            ["phoneme", "category", "priority", "eligible words US", "eligible words UK"],
            target_rows,
        ),
        "",
        "## Caveats and Exclusions",
        "",
    ])
    for caveat in report["known_caveats"]:
        lines.append(f"- {caveat}")
    if report["unsupported_uk_symbols"]:
        lines.extend(["", "Unsupported UK symbols:", ""])
        for symbol, count in report["unsupported_uk_symbols"].items():
            lines.append(f"- `{symbol}`: {count}")
    else:
        lines.extend(["", "Unsupported UK symbols: none."])

    excluded_rows = [
        [
            row["word"],
            row["review_status_uk"],
            row["content_status"],
            "; ".join(row["reasons"]),
        ]
        for row in report["excluded_rows_sample"][:10]
    ]
    lines.extend([
        "",
        "Excluded rows sample:",
        "",
        _markdown_table(
            ["word", "review_status_uk", "content_status", "reason excluded"],
            excluded_rows,
        ) if excluded_rows else "(none)",
    ])

    return "\n".join(lines)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    parser = argparse.ArgumentParser(
        description="Build the M9 UK-ready content subset/accent coverage report."
    )
    parser.add_argument(
        "--words",
        action="append",
        default=None,
        help=(
            "Word JSON file. May be repeated. Defaults to core_300_words.json "
            "and core_1000_words.json."
        ),
    )
    parser.add_argument(
        "--phonemes",
        default=str(repo_root / "content" / "phonemes.json"),
        help="Path to phonemes.json.",
    )
    parser.add_argument(
        "--accepted-review-status-uk",
        action="append",
        default=None,
        help=(
            "Accepted UK review status for this report. May be repeated. "
            "Defaults to auto_checked and reviewed."
        ),
    )
    parser.add_argument("--json-output", default=None, help="Optional JSON report path.")
    parser.add_argument(
        "--markdown-output",
        default=None,
        help="Optional Markdown report path. Prints Markdown when no output path is set.",
    )
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--candidate-limit", type=int, default=DEFAULT_CANDIDATE_LIMIT)
    args = parser.parse_args()

    word_paths = [
        Path(path) if Path(path).is_absolute() else repo_root / path
        for path in (args.words or DEFAULT_WORD_FILES)
    ]
    phonemes_path = Path(args.phonemes)
    if not phonemes_path.is_absolute():
        phonemes_path = repo_root / phonemes_path

    phoneme_inventory = load_phoneme_inventory(phonemes_path)
    known_phonemes = set(phoneme_inventory)
    report = build_uk_ready_report(
        load_word_sources(word_paths),
        known_phonemes,
        phoneme_inventory,
        load_difficult_contrasts(phonemes_path),
        accepted_uk_review_statuses=set(
            args.accepted_review_status_uk or DEFAULT_ACCEPTED_UK_REVIEW_STATUSES
        ),
        candidate_limit=args.candidate_limit,
        sample_size=args.sample_size,
    )
    markdown = render_markdown_report(report)

    if args.json_output:
        output = Path(args.json_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    if args.markdown_output:
        output = Path(args.markdown_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown + "\n")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
