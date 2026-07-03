#!/usr/bin/env python3
"""Build an M13 choose_word runtime distractor quality report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.models import Word  # noqa: E402
from app.services.distractors import build_choose_word_quality_report  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_words(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("words"), list):
        return data["words"]
    raise ValueError(f"{path} must be a JSON array or object with a words array")


def _word_from_entry(entry: dict) -> Word:
    return Word(
        id=str(entry.get("word_id") or entry.get("id") or entry.get("word") or ""),
        word=str(entry.get("word") or ""),
        level=str(entry.get("level") or ""),
        ipa_us=str(entry.get("ipa_us") or ""),
        ipa_uk=entry.get("ipa_uk"),
        phoneme_tags_us=list(entry.get("phoneme_tags_us") or []),
        phoneme_tags_uk=entry.get("phoneme_tags_uk"),
        meaning_zh=entry.get("meaning_zh"),
        audio_us=entry.get("audio_us"),
        audio_uk=entry.get("audio_uk"),
        difficulty_tags=entry.get("difficulty_tags"),
        minimal_pair_group=entry.get("minimal_pair_group"),
        content_status=str(entry.get("content_status") or "candidate"),
    )


def load_word_models(paths: list[Path]) -> list[Word]:
    words: list[Word] = []
    for path in paths:
        words.extend(_word_from_entry(entry) for entry in _load_words(path))
    return words


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report choose_word distractor scorer quality for content JSON files."
    )
    parser.add_argument(
        "sources",
        nargs="*",
        type=Path,
        default=[
            _REPO_ROOT / "content" / "core_300_words.json",
            _REPO_ROOT / "content" / "core_1000_words.json",
        ],
        help="Content JSON files to inspect.",
    )
    parser.add_argument("--accent", default="US", choices=["US", "UK"])
    parser.add_argument("--choice-count", type=int, default=4)
    parser.add_argument("--sample-limit", type=int, default=10)
    parser.add_argument("--json-output", type=Path, default=None)
    args = parser.parse_args(argv)

    words = load_word_models(args.sources)
    report = build_choose_word_quality_report(
        words,
        accent=args.accent,
        choice_count=args.choice_count,
        sample_limit=args.sample_limit,
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
