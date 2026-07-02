"""Tests for audio static serving and audio metadata validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from validate_content import _check_audio_files  # noqa: E402

from tests.auth_helpers import authenticated_client, bootstrap_owner_user  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTENT_SAMPLE = FIXTURES / "content_sample.json"


# ============================================================================
# Static /audio/ serving
# ============================================================================


class TestAudioStaticServing:
    """Tests for FastAPI static file mount at /audio/."""

    def test_audio_file_served(self, tmp_path: Path, monkeypatch):
        """A file under audio/ is served by FastAPI static mount."""
        audio_dir = tmp_path / "audio" / "us"
        audio_dir.mkdir(parents=True)
        (audio_dir / "ship.mp3").write_text("fake-mp3-content")

        monkeypatch.setenv("TINY_IPA_AUDIO_DIR", str(tmp_path / "audio"))
        # Rebuild app with the new audio dir
        import importlib

        import app.main as main_mod
        importlib.reload(main_mod)

        client = TestClient(main_mod.app)
        resp = client.get("/audio/us/ship.mp3")
        assert resp.status_code == 200
        assert resp.content == b"fake-mp3-content"

    def test_audio_404_for_missing(self, tmp_path: Path, monkeypatch):
        """Missing audio files return 404."""
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir(parents=True)
        monkeypatch.setenv("TINY_IPA_AUDIO_DIR", str(audio_dir))

        import importlib

        import app.main as main_mod
        importlib.reload(main_mod)

        client = TestClient(main_mod.app)
        resp = client.get("/audio/us/nonexistent.mp3")
        assert resp.status_code == 404


# ============================================================================
# Audio metadata validation
# ============================================================================


class TestAudioValidation:
    """Tests for validate_content.py --check-audio-files."""

    def test_found_ok(self, tmp_path: Path):
        """Existing non-empty files are counted as found_ok."""
        audio_dir = tmp_path / "us"
        audio_dir.mkdir(parents=True)
        (audio_dir / "ship.mp3").write_text("x" * 200)

        words = [{
            "word_id": "ship", "word": "ship",
            "audio_us": "/audio/us/ship.mp3",
        }]
        report = _check_audio_files(words, tmp_path, "us")
        assert report["checked"] == 1
        assert report["found_ok"] == 1
        assert len(report["missing_files"]) == 0

    def test_missing_reported(self, tmp_path: Path):
        """Missing audio files are reported."""
        words = [{
            "word_id": "ship", "word": "ship",
            "audio_us": "/audio/us/ship.mp3",
        }]
        report = _check_audio_files(words, tmp_path, "us")
        assert report["checked"] == 1
        assert len(report["missing_files"]) == 1
        assert report["missing_files"][0]["word_id"] == "ship"

    def test_empty_file_reported(self, tmp_path: Path):
        """Files below sanity threshold are flagged as empty/too-small."""
        audio_dir = tmp_path / "us"
        audio_dir.mkdir(parents=True)
        (audio_dir / "ship.mp3").write_text("tiny")

        words = [{
            "word_id": "ship", "word": "ship",
            "audio_us": "/audio/us/ship.mp3",
        }]
        report = _check_audio_files(words, tmp_path, "us")
        assert len(report["empty_files"]) == 1

    def test_no_audio_field_is_skipped(self, tmp_path: Path):
        """Words without audio_us are not checked."""
        words = [{"word_id": "ship", "word": "ship"}]
        report = _check_audio_files(words, tmp_path, "us")
        assert report["checked"] == 0

    def test_invalid_prefix_reported(self, tmp_path: Path):
        """Paths not starting with /audio/<accent>/ are flagged."""
        audio_dir = tmp_path / "wrong"
        audio_dir.mkdir(parents=True)
        (audio_dir / "ship.mp3").write_text("x" * 200)

        words = [{
            "word_id": "ship", "word": "ship",
            "audio_us": "/audio/uk/ship.mp3",  # wrong accent prefix for US check
        }]
        report = _check_audio_files(words, tmp_path, "us")
        assert len(report["invalid_prefix"]) == 1
        assert report["checked"] == 1

    def test_valid_prefix_passes(self, tmp_path: Path):
        """Correct /audio/us/ prefix for US accent passes prefix check."""
        audio_dir = tmp_path / "us"
        audio_dir.mkdir(parents=True)
        (audio_dir / "ship.mp3").write_text("x" * 200)

        words = [{
            "word_id": "ship", "word": "ship",
            "audio_us": "/audio/us/ship.mp3",
        }]
        report = _check_audio_files(words, tmp_path, "us")
        assert len(report["invalid_prefix"]) == 0
        assert report["found_ok"] == 1

    def test_uk_accent(self, tmp_path: Path):
        """audio_uk field is checked when accent=uk."""
        audio_dir = tmp_path / "uk"
        audio_dir.mkdir(parents=True)
        (audio_dir / "ship.mp3").write_text("x" * 200)

        words = [{
            "word_id": "ship", "word": "ship",
            "audio_uk": "/audio/uk/ship.mp3",
        }]
        report = _check_audio_files(words, tmp_path, "uk")
        assert report["checked"] == 1
        assert report["found_ok"] == 1


# ============================================================================
# /api/today audio_url
# ============================================================================


class TestTodayAudioUrl:
    """Tests that /api/today includes audio_url from audio_us."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.sqlite")
        # Import and seed
        from import_words import import_words  # noqa: E402
        import_words(
            source_path=CONTENT_SAMPLE,
            phonemes_path=(
                Path(__file__).resolve().parent.parent.parent
                / "content"
                / "phonemes.json"
            ),
            db_path=db_path,
        )
        bootstrap_owner_user(db_path)
        import app.db as db_mod
        self._orig_db = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path

        # Mount audio dir
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        monkeypatch.setenv("TINY_IPA_AUDIO_DIR", str(audio_dir))
        import importlib

        import app.main as main_mod
        importlib.reload(main_mod)
        self.client = authenticated_client(TestClient(main_mod.app))

        yield
        db_mod.DEFAULT_DB_PATH = self._orig_db

    def test_today_includes_audio_url(self):
        resp = self.client.post("/api/practice/next-normal")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data
        # ship has audio_us set in fixture
        ship_item = next((i for i in data["items"] if i["word"] == "ship"), None)
        assert ship_item is not None
        assert ship_item.get("audio_url") == "/audio/us/ship.mp3"

    def test_today_null_audio_url_when_missing(self):
        resp = self.client.post("/api/practice/next-normal")
        data = resp.json()
        # cat has audio_us=null in fixture
        cat_item = next((i for i in data["items"] if i["word"] == "cat"), None)
        assert cat_item is not None
        assert cat_item.get("audio_url") is None
