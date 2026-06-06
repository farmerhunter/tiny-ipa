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
from typing import Dict, List, Optional, Set

# Ensure the backend package is importable when running this script directly.
_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Reuse validation helpers from the validate_content script.
_SCRIPTS = _HERE
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from validate_content import (  # noqa: E402
    load_phoneme_set,
    load_words,
    validate_words,
)

from app.db import get_db  # noqa: E402
from app.models import Settings  # noqa: E402
from app.services.db_schema import init_db, table_names  # noqa: E402
from app.services.db_store import (  # noqa: E402
    count_phonemes,
    count_words,
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
) -> dict:
    """Run the full import pipeline and return a report dict.

    Args:
        source_path: Path to the words JSON file.
        phonemes_path: Path to ``content/phonemes.json``.
        db_path: SQLite database path (``sqlite:///`` prefix stripped if
                 present, for CLI ergonomics).
        skip_validation: If True, skip content validation (not recommended
                         for production; useful for trusted fixtures).

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
    }

    # ---- validation --------------------------------------------------------
    if not skip_validation:
        known_phonemes = load_phoneme_set(phonemes_path)
        words = load_words(source_path)
        val_report = validate_words(words, known_phonemes)
        # Unknown US phoneme tags are hard errors — reject the import.
        if val_report["unknown_phoneme_tags_us"]:
            for tag_entry in val_report["unknown_phoneme_tags_us"]:
                report["errors"].append(tag_entry)
        # Append other validation errors.
        if val_report["errors"]:
            report["errors"].extend(val_report["errors"])
        report["validation_errors"] = len(report["errors"])
        if report["errors"]:
            return report
        report["validation_passed"] = True
    else:
        # Still need the word list for import
        words = load_words(source_path)

    # ---- database initialisation -------------------------------------------
    with get_db(db_path) as conn:
        existing_tables = set(table_names(conn))
        init_db(conn)
        new_tables = sorted(set(table_names(conn)) - existing_tables)
        report["tables_created"] = new_tables

        # ---- word import ---------------------------------------------------
        for w in words:
            word_id = w.get("word_id") or w.get("id", "")
            if not word_id:
                report["skipped"] += 1
                report["errors"].append("entry without word_id — skipped")
                continue
            try:
                upsert_word(conn, w)
                # For the report we count every write as "inserted" since
                # we can't cheaply distinguish insert from update with
                # INSERT OR REPLACE without a prior SELECT.
                report["inserted"] += 1
            except Exception as exc:
                report["skipped"] += 1
                report["errors"].append(f"{word_id}: db error — {exc}")

        total_words = count_words(conn)
        report["total_words_in_db"] = total_words

        # ---- phoneme import ------------------------------------------------
        phoneme_rows = build_phoneme_rows(phonemes_path)
        for pr in phoneme_rows:
            try:
                upsert_phoneme(conn, pr)
                report["phonemes_inserted"] += 1
            except Exception as exc:
                report["errors"].append(f"{pr['id']}: phoneme db error — {exc}")

        # ---- default settings ----------------------------------------------
        default_settings = Settings(
            user_id="default",
            primary_accent="US",
            daily_word_count=10,
            show_translation=True,
            show_accent_compare=False,
            practice_mode="ipa_first",
            review_strength="normal",
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        upsert_settings(conn, default_settings)

    return report


def print_report(report: dict) -> None:
    """Print a human-readable import report to stdout."""
    print("=" * 60)
    print("Tiny IPA Import Report")
    print("=" * 60)
    print(f"Validation: {'PASS' if report['validation_passed'] else 'SKIPPED'}"
          f" ({report['validation_errors']} errors)")
    print(f"Tables created:  {', '.join(report['tables_created']) if report['tables_created'] else '(none — already existed)'}")
    print(f"Words inserted:  {report['inserted']}")
    print(f"Words skipped:   {report['skipped']}")
    print(f"Total words:     {report.get('total_words_in_db', '?')}")
    print(f"Phonemes added:  {report['phonemes_inserted']}")
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
        default="sqlite:///./tiny_ipa_dev.sqlite",
        help="SQLite database path or sqlite:/// URI (default: sqlite:///./tiny_ipa_dev.sqlite).",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip content validation (use only with trusted fixtures).",
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

    report = import_words(
        source_path=source_path,
        phonemes_path=phonemes_path,
        db_path=args.db_url,
        skip_validation=args.skip_validation,
    )

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report)

    if report["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
