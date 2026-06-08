"""Tests for generate_tts_audio.py — no real network calls."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from generate_tts_audio import (  # noqa: E402
    generate_audio_files,
    load_words,
    output_path_for_word,
    write_report,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Fake generator
# ---------------------------------------------------------------------------


async def _fake_generate(text: str, out_path: Path, voice: str = "") -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"fake mp3: {text} voice={voice}\n")


# ---------------------------------------------------------------------------
# Output path derivation
# ---------------------------------------------------------------------------


class TestOutputPath:
    def test_from_audio_us_field(self, tmp_path):
        entry = {"word_id": "ship", "word": "ship", "audio_us": "/audio/us/ship.mp3"}
        got = output_path_for_word(entry, tmp_path, "us")
        assert got == tmp_path / "ship.mp3"

    def test_fallback_from_word_id(self, tmp_path):
        entry = {"word_id": "ship", "word": "ship"}
        got = output_path_for_word(entry, tmp_path, "us")
        assert got == tmp_path / "ship.mp3"

    def test_uk_accent(self, tmp_path):
        entry = {"word_id": "ship", "word": "ship", "audio_uk": "/audio/uk/ship.mp3"}
        got = output_path_for_word(entry, tmp_path, "uk")
        assert got == tmp_path / "ship.mp3"


# ---------------------------------------------------------------------------
# Word loading
# ---------------------------------------------------------------------------


class TestLoadWords:
    def test_load_array(self, tmp_path):
        p = tmp_path / "words.json"
        p.write_text(json.dumps([{"word_id": "a"}, {"word_id": "b"}]))
        words = load_words(p)
        assert len(words) == 2

    def test_load_words_key(self, tmp_path):
        p = tmp_path / "words.json"
        p.write_text(json.dumps({"_note": "core 100", "words": [{"word_id": "x"}]}))
        words = load_words(p)
        assert len(words) == 1

    def test_load_invalid(self, tmp_path):
        p = tmp_path / "words.json"
        p.write_text('{"not_words": 1}')
        with pytest.raises(ValueError):
            load_words(p)


# ---------------------------------------------------------------------------
# Generation (using asyncio.run — no pytest-asyncio dependency)
# ---------------------------------------------------------------------------


class TestGenerateAudio:
    def test_generates_files(self, tmp_path):
        words = [
            {"word_id": "ship", "word": "ship", "audio_us": "/audio/us/ship.mp3"},
            {"word_id": "cat", "word": "cat", "audio_us": "/audio/us/cat.mp3"},
        ]
        report = asyncio.run(generate_audio_files(
            words, output_dir=tmp_path, accent="us", generate_fn=_fake_generate,
        ))
        assert report["generated"] == 2
        assert report["failed"] == 0
        assert (tmp_path / "ship.mp3").exists()
        assert (tmp_path / "cat.mp3").exists()

    def test_skips_existing_by_default(self, tmp_path):
        """Default behaviour: existing non-empty files are skipped (no overwrite)."""
        existing = tmp_path / "ship.mp3"
        existing.write_text("already here")
        words = [
            {"word_id": "ship", "word": "ship", "audio_us": "/audio/us/ship.mp3"},
            {"word_id": "cat", "word": "cat", "audio_us": "/audio/us/cat.mp3"},
        ]
        report = asyncio.run(generate_audio_files(
            words, output_dir=tmp_path, accent="us", generate_fn=_fake_generate,
        ))
        assert report["skipped"] == 1
        assert report["generated"] == 1
        assert existing.read_text() == "already here"

    def test_overwrite_replaces_existing(self, tmp_path):
        """With --overwrite, existing files are overwritten."""
        existing = tmp_path / "ship.mp3"
        existing.write_text("old content")
        words = [
            {"word_id": "ship", "word": "ship", "audio_us": "/audio/us/ship.mp3"},
        ]
        report = asyncio.run(generate_audio_files(
            words, output_dir=tmp_path, accent="us",
            overwrite=True, generate_fn=_fake_generate,
        ))
        assert report["generated"] == 1
        assert report["skipped"] == 0
        # Content was overwritten
        assert "fake mp3" in existing.read_text()

    def test_per_word_failure(self, tmp_path):
        words = [
            {"word_id": "good", "word": "good"},
            {"word_id": "fail", "word": "fail"},
            {"word_id": "bad", "word": "bad"},
        ]

        async def _selective_fail(text: str, out_path: Path, voice: str = "") -> None:
            if text in ("fail", "bad"):
                raise RuntimeError(f"test failure: {text}")
            await _fake_generate(text, out_path)

        report = asyncio.run(generate_audio_files(
            words, output_dir=tmp_path, accent="us", generate_fn=_selective_fail,
        ))
        assert report["generated"] == 1
        assert report["failed"] == 2
        assert len(report["failures"]) == 2
        assert report["failures"][0]["word_id"] == "fail"
        assert report["failures"][1]["word_id"] == "bad"
        assert (tmp_path / "good.mp3").exists()

    def test_dry_run_no_files(self, tmp_path):
        words = [
            {"word_id": "ship", "word": "ship"},
            {"word_id": "cat", "word": "cat"},
        ]
        report = asyncio.run(generate_audio_files(
            words, output_dir=tmp_path, accent="us",
            dry_run=True, generate_fn=_fake_generate,
        ))
        assert report["generated"] == 2
        assert report["dry_run"] is True
        assert not (tmp_path / "ship.mp3").exists()

    def test_limit(self, tmp_path):
        words = [{"word_id": f"w{i}", "word": f"w{i}"} for i in range(10)]
        report = asyncio.run(generate_audio_files(
            words, output_dir=tmp_path, accent="us",
            limit=3, generate_fn=_fake_generate,
        ))
        assert report["total"] == 3
        assert report["generated"] == 3

    def test_report_shape(self, tmp_path):
        words = [{"word_id": "x", "word": "x"}]
        report = asyncio.run(generate_audio_files(
            words, output_dir=tmp_path, accent="us", generate_fn=_fake_generate,
        ))
        for key in ("generated", "skipped", "failed", "total", "failures", "dry_run"):
            assert key in report, f"missing key: {key}"


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------


class TestReport:
    def test_write_report(self, tmp_path):
        rp = tmp_path / "report.json"
        write_report({"generated": 1, "skipped": 0, "failed": 0, "total": 1}, rp)
        assert rp.exists()
        data = json.loads(rp.read_text())
        assert data["generated"] == 1
