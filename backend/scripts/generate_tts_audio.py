#!/usr/bin/env python3
"""Generate static MP3 audio assets for Tiny IPA content.

Uses edge-tts (async) to generate audio files for each word in a content
JSON. Designed for build-time use, not runtime.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/generate_tts_audio.py --source ../content/core_100_words.json

Dry-run (no network):
    python scripts/generate_tts_audio.py --source ../content/core_100_words.json --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent

DEFAULT_SOURCE = str(_REPO / "content" / "core_100_words.json")
DEFAULT_OUTPUT_DIR = str(_REPO / "audio" / "us")
DEFAULT_REPORT = str(_REPO / "content" / "generated" / "audio_report_us.json")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_words(source_path: Path) -> List[dict]:
    """Load words from JSON, supporting both top-level array and {words: [...]}."""
    with open(source_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "words" in data:
        return data["words"]
    raise ValueError(f"Expected array or {{words: [...]}}, got {type(data).__name__}")


def output_path_for_word(entry: dict, output_dir: Path, accent: str = "us") -> Path:
    """Derive the output .mp3 path from a word entry's ``audio_us`` or word_id."""
    audio_field = f"audio_{accent}"
    audio_path = entry.get(audio_field, "")
    if audio_path:
        # /audio/us/ship.mp3 -> ship.mp3 under output_dir
        fname = Path(audio_path).name
    else:
        wid = entry.get("word_id") or entry.get("word", "unknown")
        fname = f"{wid}.mp3"
    return output_dir / fname


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

# Type alias for injectable generator: (text, output_path) -> None on success, raises on failure
GenerateFn = Callable[[str, Path], None]


async def _edge_tts_generate(text: str, out_path: Path) -> None:
    """Generate an MP3 file using edge-tts (async).

    Raises RuntimeError on failure. The caller is responsible for ensuring
    ``edge_tts`` is installed (``pip install edge-tts``).
    """
    try:
        import edge_tts  # noqa: F811
    except ImportError:
        raise RuntimeError(
            "edge-tts is not installed. Run: pip install edge-tts"
        ) from None

    voice = os.getenv("TTS_VOICE_US", "en-US-JennyNeural")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


async def generate_audio_files(
    words: List[dict],
    *,
    output_dir: Path,
    accent: str = "us",
    only_missing: bool = False,
    dry_run: bool = False,
    limit: Optional[int] = None,
    generate_fn: Optional[GenerateFn] = None,
) -> dict:
    """Generate MP3 files for a list of word entries.

    Args:
        words: Word entry dicts with ``word_id`` and ``audio_us``/``audio_uk``.
        output_dir: Where to write .mp3 files.
        accent: ``"us"`` or ``"uk"``.
        only_missing: Skip words whose output file already exists.
        dry_run: Do everything except actually generate audio.
        limit: Only process at most this many words.
        generate_fn: Pluggable generator for testing. Defaults to edge-tts.

    Returns:
        Report dict with ``generated``, ``skipped``, ``failed``, ``total``,
        ``failures`` list, and ``dry_run`` boolean.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "generated": 0,
        "skipped": 0,
        "failed": 0,
        "total": 0,
        "dry_run": dry_run,
        "failures": [],
    }

    gen = generate_fn or _edge_tts_generate
    entries = words[:limit] if limit else words

    for entry in entries:
        report["total"] += 1
        wid = entry.get("word_id") or entry.get("word", "")
        out_path = output_path_for_word(entry, output_dir, accent)

        # Skip existing files
        if only_missing and out_path.exists() and out_path.stat().st_size > 0:
            report["skipped"] += 1
            continue

        if dry_run:
            report["generated"] += 1
            continue

        try:
            # Determine TTS text: use the word itself
            text = entry.get("word", str(wid))
            await gen(text, out_path)
            report["generated"] += 1
        except Exception as exc:
            report["failed"] += 1
            report["failures"].append({
                "word_id": wid,
                "word": entry.get("word", ""),
                "output": str(out_path),
                "reason": str(exc),
            })

    return report


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def write_report(report: dict, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def print_report(report: dict) -> None:
    print("=" * 60)
    print("Tiny IPA Audio Generation Report")
    print("=" * 60)
    mode = "DRY RUN" if report["dry_run"] else "LIVE"
    print(f"Mode:      {mode}")
    print(f"Total:     {report['total']}")
    print(f"Generated: {report['generated']}")
    print(f"Skipped:   {report['skipped']}")
    print(f"Failed:    {report['failed']}")
    if report["failures"]:
        print()
        print("--- Failures ---")
        for f in report["failures"]:
            print(f"  {f['word_id']}: {f['reason']}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate static MP3 audio for Tiny IPA content."
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Path to words JSON.")
    parser.add_argument("--accent", default="us", choices=["us", "uk"], help="Accent (default: us).")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: ../audio/<accent>).")
    parser.add_argument("--only-missing", action="store_true", help="Skip words with existing audio files.")
    parser.add_argument("--dry-run", action="store_true", help="Run without making network calls.")
    parser.add_argument("--limit", type=int, default=None, help="Limit to N words (for testing).")
    parser.add_argument("--report", default=None, help="Path to write JSON report.")
    parser.add_argument("--json", action="store_true", help="Print report as JSON to stdout.")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: source file not found: {source_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else Path(DEFAULT_OUTPUT_DIR)

    words = load_words(source_path)

    async def _run():
        return await generate_audio_files(
            words,
            output_dir=output_dir,
            accent=args.accent,
            only_missing=args.only_missing,
            dry_run=args.dry_run,
            limit=args.limit,
        )

    report = asyncio.run(_run())

    report_path = Path(args.report) if args.report else Path(DEFAULT_REPORT)
    write_report(report, report_path)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report)

    if report["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
