"""Tests for import_words.py and the supporting db / schema / store modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure scripts are importable.
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from import_words import build_phoneme_rows, import_words  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.models import Settings  # noqa: E402
from app.services.db_schema import init_db, table_names  # noqa: E402
from app.services.db_store import (  # noqa: E402
    count_words,
    get_phoneme_by_id,
    get_settings,
    get_word_by_id,
    upsert_settings,
    upsert_word,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTENT_SAMPLE = FIXTURES / "content_sample.json"
PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(name="temp_db")
def temp_db_fixture(tmp_path: Path):
    """Create a fresh SQLite database in a temporary directory."""
    db_path = str(tmp_path / "test.sqlite")
    return db_path


# ---------------------------------------------------------------------------
# db_schema
# ---------------------------------------------------------------------------


class TestSchemaInitialisation:
    """Tests for ``app.services.db_schema``."""

    def test_init_creates_expected_tables(self, temp_db):
        conn = get_connection(temp_db)
        init_db(conn)
        names = table_names(conn)
        conn.close()
        for expected in [
            "attempts",
            "daily_sessions",
            "phoneme_stats",
            "phonemes",
            "session_items",
            "settings",
            "words",
        ]:
            assert expected in names, f"Table '{expected}' missing from {names}"

    def test_init_is_idempotent(self, temp_db):
        conn = get_connection(temp_db)
        init_db(conn)
        before = table_names(conn)
        init_db(conn)  # second call
        after = table_names(conn)
        conn.close()
        assert before == after

    def test_init_adds_focus_phonemes_to_existing_settings_table(self, temp_db):
        conn = get_connection(temp_db)
        conn.execute(
            """
            CREATE TABLE settings (
                user_id              TEXT PRIMARY KEY,
                primary_accent       TEXT    NOT NULL,
                daily_word_count     INTEGER NOT NULL,
                show_translation     INTEGER NOT NULL,
                show_accent_compare  INTEGER NOT NULL,
                practice_mode        TEXT    NOT NULL,
                review_strength      TEXT    NOT NULL,
                updated_at           TEXT    NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO settings (
                user_id, primary_accent, daily_word_count,
                show_translation, show_accent_compare,
                practice_mode, review_strength, updated_at
            ) VALUES ('default', 'US', 10, 1, 0, 'ipa_first', 'normal', '2026-06-06T00:00:00Z')
            """
        )
        init_db(conn)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(settings)").fetchall()
        }
        settings = get_settings(conn, "default")
        conn.close()

        assert "focus_phonemes" in columns
        assert settings is not None
        assert settings.focus_phonemes == []


# ---------------------------------------------------------------------------
# db_store — words
# ---------------------------------------------------------------------------


class TestWordStore:
    """Tests for word CRUD in ``app.services.db_store``."""

    @pytest.fixture(autouse=True)
    def _init(self, temp_db):
        """Each test gets its own initialised database."""
        conn = get_connection(temp_db)
        init_db(conn)
        self.conn = conn
        self.db_path = temp_db
        yield
        conn.close()

    def test_upsert_and_retrieve_word(self):
        data = {
            "word_id": "ship",
            "word": "ship",
            "level": "beginner",
            "ipa_us": "/ʃɪp/",
            "ipa_uk": "/ʃɪp/",
            "phoneme_tags_us": ["/ʃ/", "/ɪ/", "/p/"],
            "phoneme_tags_uk": ["/ʃ/", "/ɪ/", "/p/"],
            "meaning_zh": "船",
            "difficulty_tags": ["sh", "short_i"],
            "minimal_pair_group": "ship_sheep",
            "content_status": "core_selected",
        }
        wid = upsert_word(self.conn, data)
        assert wid == "ship"

        w = get_word_by_id(self.conn, "ship")
        assert w is not None
        assert w.word == "ship"
        assert w.ipa_us == "/ʃɪp/"
        assert w.ipa_uk == "/ʃɪp/"
        assert w.phoneme_tags_us == ["/ʃ/", "/ɪ/", "/p/"]
        assert w.phoneme_tags_uk == ["/ʃ/", "/ɪ/", "/p/"]
        assert w.meaning_zh == "船"
        assert w.difficulty_tags == ["sh", "short_i"]
        assert w.minimal_pair_group == "ship_sheep"
        assert w.content_status == "core_selected"

    def test_upsert_is_idempotent(self):
        data = {
            "word_id": "cat",
            "word": "cat",
            "level": "beginner",
            "ipa_us": "/kæt/",
            "phoneme_tags_us": ["/k/", "/æ/", "/t/"],
            "content_status": "core_selected",
        }
        upsert_word(self.conn, data)
        assert count_words(self.conn) == 1
        upsert_word(self.conn, data)
        assert count_words(self.conn) == 1  # no duplicate

    def test_upsert_preserves_accent_fields(self):
        """ipa_uk and phoneme_tags_uk must survive a round-trip."""
        data = {
            "word_id": "ship",
            "word": "ship",
            "level": "beginner",
            "ipa_us": "/ʃɪp/",
            "ipa_uk": "/ʃɪp/",
            "phoneme_tags_us": ["/ʃ/", "/ɪ/", "/p/"],
            "phoneme_tags_uk": ["/ʃ/", "/ɪ/", "/p/"],
            "content_status": "core_selected",
        }
        upsert_word(self.conn, data)
        w = get_word_by_id(self.conn, "ship")
        assert w.ipa_uk == "/ʃɪp/"
        assert w.phoneme_tags_uk == ["/ʃ/", "/ɪ/", "/p/"]

    def test_null_uk_fields(self):
        """Words with no UK data store NULLs and return None/empty."""
        data = {
            "word_id": "cat",
            "word": "cat",
            "level": "beginner",
            "ipa_us": "/kæt/",
            "phoneme_tags_us": ["/k/", "/æ/", "/t/"],
            "content_status": "auto_selected",
        }
        upsert_word(self.conn, data)
        w = get_word_by_id(self.conn, "cat")
        assert w.ipa_uk is None
        assert w.phoneme_tags_uk is None
        assert w.audio_uk is None

    def test_get_missing_word(self):
        assert get_word_by_id(self.conn, "nonexistent") is None


# ---------------------------------------------------------------------------
# db_store — settings
# ---------------------------------------------------------------------------


class TestSettingsStore:
    @pytest.fixture(autouse=True)
    def _init(self, temp_db):
        conn = get_connection(temp_db)
        init_db(conn)
        self.conn = conn
        yield
        conn.close()

    def test_default_settings_roundtrip(self):
        s = Settings(
            user_id="default",
            primary_accent="US",
            daily_word_count=10,
            show_translation=True,
            show_accent_compare=False,
            practice_mode="ipa_first",
            review_strength="normal",
            focus_phonemes=["/ʃ/", "/ɪ/"],
            updated_at="2026-06-06T00:00:00Z",
        )
        upsert_settings(self.conn, s)
        got = get_settings(self.conn, "default")
        assert got is not None
        assert got.primary_accent == "US"
        assert got.daily_word_count == 10
        assert got.show_translation is True
        assert got.show_accent_compare is False
        assert got.practice_mode == "ipa_first"
        assert got.review_strength == "normal"
        assert got.focus_phonemes == ["/ʃ/", "/ɪ/"]

    def test_get_missing_settings(self):
        assert get_settings(self.conn, "no_such_user") is None


# ---------------------------------------------------------------------------
# import_words script
# ---------------------------------------------------------------------------


class TestImportWords:
    """Integration tests for the import pipeline."""

    def test_import_fixture_success(self, temp_db):
        """Import the 3-word fixture and verify counts + contents."""
        report = import_words(
            source_path=CONTENT_SAMPLE,
            phonemes_path=PHONEMES_PATH,
            db_path=temp_db,
        )
        assert report["validation_passed"] is True
        assert report["inserted"] == 3
        assert report["skipped"] == 0
        assert len(report["errors"]) == 0
        assert report["phonemes_inserted"] == 41
        assert report.get("total_words_in_db") == 3

    def test_import_idempotent(self, temp_db):
        """Re-running import with the same data does not duplicate rows."""
        report1 = import_words(CONTENT_SAMPLE, PHONEMES_PATH, temp_db)
        report2 = import_words(CONTENT_SAMPLE, PHONEMES_PATH, temp_db)
        assert report2["inserted"] == report1["inserted"]
        assert report2.get("total_words_in_db") == 3

    def test_import_creates_default_settings(self, temp_db):
        """After import, the default settings row must exist."""
        import_words(CONTENT_SAMPLE, PHONEMES_PATH, temp_db)
        conn = get_connection(temp_db)
        settings = get_settings(conn, "default")
        conn.close()
        assert settings is not None
        assert settings.user_id == "default"
        assert settings.primary_accent == "US"
        assert settings.daily_word_count == 10
        assert settings.focus_phonemes == []

    def test_import_preserves_accent_fields(self, temp_db):
        """After import, ship.ipa_uk and phoneme_tags_uk are stored."""
        import_words(CONTENT_SAMPLE, PHONEMES_PATH, temp_db)
        conn = get_connection(temp_db)
        w = get_word_by_id(conn, "ship")
        conn.close()
        assert w is not None
        assert w.ipa_uk == "/ʃɪp/"
        assert w.phoneme_tags_uk == ["/ʃ/", "/ɪ/", "/p/"]

    def test_invalid_content_reports_errors(self, temp_db, tmp_path):
        """Words with missing required fields produce validation errors."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(json.dumps([{"word": "no_id"}]))
        report = import_words(bad_file, PHONEMES_PATH, temp_db)
        assert report["validation_passed"] is False
        assert report["validation_errors"] > 0

    def test_import_creates_tables(self, temp_db):
        """First import creates the full schema."""
        # Use a fresh db and verify tables don't exist beforehand.
        conn1 = get_connection(temp_db)
        tables_before = table_names(conn1)
        conn1.close()
        assert len(tables_before) == 0

        import_words(CONTENT_SAMPLE, PHONEMES_PATH, temp_db)

        conn2 = get_connection(temp_db)
        tables_after = table_names(conn2)
        conn2.close()
        assert len(tables_after) >= 7

    def test_unknown_phoneme_tags_us_blocks_import(self, temp_db, tmp_path):
        """Words with phoneme tags not in the inventory must fail the import."""
        bad_file = tmp_path / "bad_phoneme.json"
        bad_file.write_text(json.dumps([{
            "word_id": "ship",
            "word": "ship",
            "level": "beginner",
            "ipa_us": "/ʃɪp/",
            "phoneme_tags_us": ["/ʃ/", "/ɪ/", "/ɸ/"],  # /ɸ/ is not in phonemes.json
            "content_status": "core_selected",
        }]))
        report = import_words(bad_file, PHONEMES_PATH, temp_db)
        assert report["validation_passed"] is False
        assert report["validation_errors"] > 0
        assert any("unknown phoneme tag" in e.lower() for e in report["errors"])

    def test_skip_validation_flag(self, temp_db, tmp_path):
        """With --skip-validation, content errors are bypassed."""
        bad_file = tmp_path / "unvalidated.json"
        bad_file.write_text(json.dumps([{
            "word_id": "x",
            "word": "x",
            "level": "beginner",
            "ipa_us": "/ɛks/",
            "phoneme_tags_us": ["/ɪ/"],
            "content_status": "core_selected",
        }]))
        report = import_words(
            bad_file, PHONEMES_PATH, temp_db, skip_validation=True
        )
        assert report["inserted"] == 1
        assert len(report["errors"]) == 0

    def test_phoneme_rows_are_imported(self, temp_db):
        """Imported phonemes can be read back."""
        import_words(CONTENT_SAMPLE, PHONEMES_PATH, temp_db)
        conn = get_connection(temp_db)
        p = get_phoneme_by_id(conn, "/ʃ/")
        conn.close()
        assert p is not None
        assert p.symbol == "/ʃ/"
        assert p.category in ("consonant", "fricative")

    def test_sqlite_prefix_is_handled(self, temp_db):
        """The sqlite:/// prefix in db_path is stripped automatically."""
        db_uri = f"sqlite:///{temp_db}"
        import_words(CONTENT_SAMPLE, PHONEMES_PATH, db_uri)
        conn = get_connection(temp_db)
        assert count_words(conn) == 3
        conn.close()

    def test_level_specific_imports_do_not_clobber_other_level(
        self, temp_db, tmp_path
    ):
        """Entry and Mid imports can share word strings when word_id namespaces differ."""
        entry_file = tmp_path / "core_300_words.json"
        mid_file = tmp_path / "core_1000_words.json"

        entry_words = [
            _fixture_word(
                word_id=("shared" if i == 0 else f"entry_word_{i}"),
                word=("shared" if i == 0 else f"entryword{i}"),
                level="beginner",
                syllable_count=1,
            )
            for i in range(300)
        ]
        mid_words = []
        for i in range(1000):
            syllable_count = 1 if i < 250 else 2 if i < 750 else 3
            mid_words.append(
                _fixture_word(
                    word_id=("mid_shared" if i == 0 else f"mid_word_{i}"),
                    word=("shared" if i == 0 else f"midword{i}"),
                    level="intermediate",
                    syllable_count=syllable_count,
                )
            )

        entry_file.write_text(json.dumps({"words": entry_words}), encoding="utf-8")
        mid_file.write_text(json.dumps({"words": mid_words}), encoding="utf-8")

        entry_report = import_words(
            entry_file, PHONEMES_PATH, temp_db, content_level="entry"
        )
        mid_report = import_words(
            mid_file, PHONEMES_PATH, temp_db, content_level="mid"
        )

        conn = get_connection(temp_db)
        entry_shared = get_word_by_id(conn, "shared")
        mid_shared = get_word_by_id(conn, "mid_shared")
        total = count_words(conn)
        conn.close()

        assert entry_report["validation_passed"] is True
        assert mid_report["validation_passed"] is True
        assert total == 1300
        assert entry_shared is not None
        assert entry_shared.level == "beginner"
        assert mid_shared is not None
        assert mid_shared.level == "intermediate"
        assert mid_report["syllable_distribution_us"]["two"]["count"] == 500


# ---------------------------------------------------------------------------
# Phoneme inventory
# ---------------------------------------------------------------------------


class TestPhonemeRows:
    def test_builds_rows_from_phonemes_json(self):
        rows = build_phoneme_rows(PHONEMES_PATH)
        assert len(rows) == 41  # 17 vowels + 24 consonants
        symbols = {r["symbol"] for r in rows}
        assert "/ʃ/" in symbols
        assert "/ɪ/" in symbols
        assert "/iː/" in symbols
        # Every row must have required fields
        for r in rows:
            assert r["id"]
            assert r["symbol"]
            assert r["accent_scope"] in ("US", "UK", "both")


def _fixture_word(
    *,
    word_id: str,
    word: str,
    level: str,
    syllable_count: int,
) -> dict:
    if syllable_count == 1:
        ipa = "/kæt/"
        tags = ["/k/", "/æ/", "/t/"]
    elif syllable_count == 2:
        ipa = "/ˈteɪbəl/"
        tags = ["/t/", "/eɪ/", "/b/", "/ə/", "/l/"]
    else:
        ipa = "/ˈfæməli/"
        tags = ["/f/", "/æ/", "/m/", "/ə/", "/l/", "/iː/"]
    return {
        "word_id": word_id,
        "word": word,
        "level": level,
        "ipa_us": ipa,
        "ipa_uk": ipa,
        "phoneme_tags_us": tags,
        "phoneme_tags_uk": tags,
        "meaning_zh": f"词 {word}",
        "content_status": "core_selected",
        "syllable_count_us": syllable_count,
    }
