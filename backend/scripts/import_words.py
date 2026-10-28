#!/usr/bin/env python3
"""Import words and phoneme inventory into the SQLite runtime database.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/import_words.py --source ../content/generated/candidate_words.json

The script validates source content, initialises the database schema if
needed, upserts words and phonemes, creates default settings, and prints
an import report.

Dependencies: reuse validation helpers from ``validate_content.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Ensure the backend package is importable when running this script directly.
_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Reuse validation helpers from the validate_content script.
_SCRIPTS = _HERE
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from correct_expanded_tags import check_regression, prepare_import  # noqa: E402
from validate_content import (  # noqa: E402
    import_structure_errors,
    infer_content_level,
    load_phoneme_set,
    load_words,
    validate_words,
)

from app.db import DEFAULT_DB_PATH, get_db  # noqa: E402
from app.models import Settings  # noqa: E402
from app.services.db_schema import init_db, table_names  # noqa: E402
from app.services.db_store import (  # noqa: E402
    count_words,
    get_settings,
    upsert_phoneme,
    upsert_settings,
    upsert_word,
)

# ---------------------------------------------------------------------------
# Default paths (relative to repo root)
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent

DEFAULT_SOURCE = os.getenv(
    "TINY_IPA_CONTENT_SOURCE",
    str(_REPO_ROOT / "content" / "generated" / "candidate_words.json"),
)
DEFAULT_PHONEMES = str(_REPO_ROOT / "content" / "phonemes.json")

# ---------------------------------------------------------------------------
# Phoneme inventory import
# ---------------------------------------------------------------------------


def build_phoneme_rows(phonemes_path: Path) -> List[dict]:
    """Parse ``content/phonemes.json`` into a flat list of db-row dicts."""
    with open(phonemes_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    rows: List[dict] = []
    # Determine accent_scope heuristically: currently the inventory is
    # shared between US and UK.
    for category in ("vowels", "consonants"):
        for entry in data.get(category, []):
            rows.append(
                {
                    "id": entry["symbol"],
                    "symbol": entry["symbol"],
                    "accent_scope": "both",
                    "category": entry.get("category", category),
                    "priority": entry.get("priority", 2),
                    "example_word": entry.get("example_word"),
                    "description_zh": entry.get("description_zh"),
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Import pipeline
# ---------------------------------------------------------------------------


def import_words(
    source_path: Path,
    phonemes_path: Path,
    db_path: str,
    *,
    skip_validation: bool = False,
    content_level: Optional[str] = None,
) -> dict:
    """Run the full import pipeline and return a report dict.

    Args:
        source_path: Path to the words JSON file.
        phonemes_path: Path to ``content/phonemes.json``.
        db_path: SQLite database path (``sqlite:///`` prefix stripped if
                 present, for CLI ergonomics).
        skip_validation: If True, skip semantic content validation (not recommended
                         for production; useful for trusted fixtures).
                         Structural/US inventory checks still apply.

    Returns:
        A report dict with keys: inserted, updated, skipped, errors,
        phonemes_inserted, validation_passed, tables_created.
    """
    # Normalise optional sqlite:/// prefix
    if db_path.startswith("sqlite:///"):
        db_path = db_path[len("sqlite:///"):]

    report: dict = {
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
        "phonemes_inserted": 0,
        "validation_passed": False,
        "validation_errors": 0,
        "tables_created": [],
        "content_level": content_level,
    }

    report.update(committed=False, rolled_back=False)
    try:
        words = load_words(source_path)
        structural_errors = import_structure_errors(words)
        if structural_errors:
            report["errors"] = structural_errors
            report["validation_errors"] = len(structural_errors)
            return report
        words, bindings, tag_changes = prepare_import(source_path, words)
        report["tag_corrections"] = bindings
        structural_errors = import_structure_errors(words)
        if structural_errors:
            report["errors"] = structural_errors
            report["validation_errors"] = len(structural_errors)
            return report
        known_phonemes = load_phoneme_set(phonemes_path)
        for word in words:
            for tag in word["phoneme_tags_us"]:
                if tag not in known_phonemes:
                    wid = word.get("word_id", word.get("id"))
                    report["errors"].append(f"{wid}: unknown phoneme tag '{tag}'")
        if report["errors"]:
            report["validation_errors"] = len(report["errors"])
            return report
        if not skip_validation:
            val_report = validate_words(
                words, known_phonemes, content_level=content_level
            )
            for key, default in (("content_level", None), ("level_counts", {}),
                                 ("content_status_counts", {}), ("syllable_distribution_us", {}),
                                 ("multisyllable_count", 0), ("multisyllable_percent", 0.0)):
                report[key] = val_report.get(key, default)
            report["errors"] = val_report["errors"]
            report["validation_errors"] = len(report["errors"])
            if report["errors"]:
                return report
            report["validation_passed"] = True
        phoneme_rows = build_phoneme_rows(phonemes_path)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        report["errors"].append(f"invalid content: {exc}")
        report["validation_errors"] = len(report["errors"])
        return report

    stage = "open database"
    started = False
    original_count = None
    try:
        with get_db(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            started = True
            existing_tables = set(table_names(conn))
            original_count = count_words(conn) if "words" in existing_tables else 0
            if "words" in existing_tables:
                stage = "tag regression check"
                check_regression(conn, words, tag_changes)
            stage = "initialize schema"
            init_db(conn)
            report["tables_created"] = sorted(set(table_names(conn)) - existing_tables)
            for word in words:
                stage = f"word {word.get('word_id', word.get('id'))}"
                upsert_word(conn, word)
                report["inserted"] += 1
            for phoneme in phoneme_rows:
                stage = f"phoneme {phoneme['id']}"
                upsert_phoneme(conn, phoneme)
                report["phonemes_inserted"] += 1
            stage = "default settings"
            if get_settings(conn, "default") is None:
                upsert_settings(conn, Settings(
                    user_id="default", updated_at=datetime.now(timezone.utc).isoformat()
                ))
            report["total_words_in_db"] = count_words(conn)
            stage = "commit"
        report["committed"] = True
    except Exception as exc:
        report["errors"].append(f"{stage}: {exc}")
        report.update(
            inserted=0, updated=0, phonemes_inserted=0, tables_created=[], rolled_back=started
        )
        if original_count is not None:
            report["total_words_in_db"] = original_count
    return report


def print_report(report: dict) -> None:
    """Print a human-readable import report to stdout."""
    print("=" * 60)
    print("Tiny IPA Import Report")
    print("=" * 60)
    print(f"Validation: {'PASS' if report['validation_passed'] else 'SKIPPED'}"
          f" ({report['validation_errors']} errors)")
    tables = (
        ", ".join(report["tables_created"])
        if report["tables_created"]
        else "(none — already existed)"
    )
    print(f"Tables created:  {tables}")
    for binding in report.get("tag_corrections", []):
        print(f"Tag corrections: {binding['source']} ({len(binding['corrected_word_ids'])} words)")
    print(f"Transaction: {'COMMITTED' if report.get('committed') else 'NOT COMMITTED'}")
    print(f"Words inserted:  {report['inserted']}")
    print(f"Words skipped:   {report['skipped']}")
    print(f"Total words:     {report.get('total_words_in_db', '?')}")
    print(f"Phonemes added:  {report['phonemes_inserted']}")
    if report.get("content_level"):
        print(f"Content level:   {report['content_level']}")
        print(f"Level counts:    {report.get('level_counts', {})}")
        print(f"Syllables:       {report.get('syllable_distribution_us', {})}")
        print(
            "Multisyllable:   "
            f"{report.get('multisyllable_count', 0)} "
            f"({report.get('multisyllable_percent', 0.0)}%)"
        )
    print(f"Import errors:   {len(report['errors'])}")
    if report["errors"]:
        print()
        print("--- Errors (first 20) ---")
        for err in report["errors"][:20]:
            print(f"  {err}")
        if len(report["errors"]) > 20:
            print(f"  ... and {len(report['errors']) - 20} more")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import words and phonemes into the Tiny IPA SQLite database."
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help="Path to source words JSON file (default: content/generated/candidate_words.json).",
    )
    parser.add_argument(
        "--phonemes",
        default=DEFAULT_PHONEMES,
        help="Path to phonemes.json (default: content/phonemes.json).",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="SQLite database path or sqlite:/// URI (default: same as runtime DEFAULT_DB_PATH).",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip content validation (use only with trusted fixtures).",
    )
    parser.add_argument(
        "--content-level",
        choices=["auto", "entry", "mid"],
        default="auto",
        help=(
            "Apply level-aware validation before import. auto maps "
            "core_300_words.json to entry and core_1000_words.json to mid."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the report as JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: source file not found: {source_path}", file=sys.stderr)
        sys.exit(1)

    phonemes_path = Path(args.phonemes)
    if not phonemes_path.exists():
        print(f"Error: phonemes file not found: {phonemes_path}", file=sys.stderr)
        sys.exit(1)

    db_path = args.db_url if args.db_url else DEFAULT_DB_PATH
    content_level = (
        infer_content_level(source_path)
        if args.content_level == "auto"
        else args.content_level
    )
    report = import_words(
        source_path=source_path,
        phonemes_path=phonemes_path,
        db_path=db_path,
        skip_validation=args.skip_validation,
        content_level=content_level,
    )

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report)

    if report["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
