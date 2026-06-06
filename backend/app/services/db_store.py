"""Repository helpers for words, phonemes, and settings tables.

Plain sqlite3 queries — no ORM. JSON-serialised list fields are handled
at this layer so callers work with Python lists, not raw strings.
"""

from __future__ import annotations

import json
import sqlite3
from typing import List, Optional

from app.models import Phoneme, Settings, Word


# ============================================================================
# Serialisation helpers
# ============================================================================

_LIST_FIELDS_WORDS = {
    "phoneme_tags_us",
    "phoneme_tags_uk",
    "difficulty_tags",
}

_NULLABLE_LIST_FIELDS_WORDS = {
    "phoneme_tags_uk",
    "difficulty_tags",
}


def _to_json(value: Optional[List[str]]) -> Optional[str]:
    """Encode a Python list as a JSON string."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _parse_list(raw: Optional[str]) -> Optional[List[str]]:
    """Decode a JSON string into a Python list, or return None."""
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def _word_from_row(row: sqlite3.Row) -> Word:
    """Build a Word dataclass from a sqlite3.Row."""
    return Word(
        id=row["id"],
        word=row["word"],
        level=row["level"],
        ipa_us=row["ipa_us"],
        ipa_uk=row["ipa_uk"],
        phoneme_tags_us=_parse_list(row["phoneme_tags_us"]) or [],
        phoneme_tags_uk=_parse_list(row["phoneme_tags_uk"]),
        meaning_zh=row["meaning_zh"],
        audio_us=row["audio_us"],
        audio_uk=row["audio_uk"],
        difficulty_tags=_parse_list(row["difficulty_tags"]),
        minimal_pair_group=row["minimal_pair_group"],
        content_status=row["content_status"],
    )


def _phoneme_from_row(row: sqlite3.Row) -> Phoneme:
    return Phoneme(
        id=row["id"],
        symbol=row["symbol"],
        accent_scope=row["accent_scope"],
        category=row["category"],
        priority=row["priority"],
        example_word=row["example_word"],
        description_zh=row["description_zh"],
    )


def _settings_from_row(row: sqlite3.Row) -> Settings:
    return Settings(
        user_id=row["user_id"],
        primary_accent=row["primary_accent"],
        daily_word_count=row["daily_word_count"],
        show_translation=bool(row["show_translation"]),
        show_accent_compare=bool(row["show_accent_compare"]),
        practice_mode=row["practice_mode"],
        review_strength=row["review_strength"],
        updated_at=row["updated_at"],
    )


# ============================================================================
# Words
# ============================================================================


def upsert_word(conn: sqlite3.Connection, word_data: dict) -> str:
    """Insert or replace a single word row. Returns the word id.

    ``word_data`` is the raw source dict; this function handles JSON
    encoding of list fields internally.
    """
    # Start with empty defaults for every bind parameter so sqlite3
    # never raises "You did not supply a value for binding N".
    values: dict = {
        "word_id": None,
        "word": None,
        "level": None,
        "ipa_us": None,
        "ipa_uk": None,
        "phoneme_tags_us": None,
        "phoneme_tags_uk": None,
        "meaning_zh": None,
        "audio_us": None,
        "audio_uk": None,
        "difficulty_tags": None,
        "minimal_pair_group": None,
        "content_status": None,
    }
    # Overlay caller data, mapping "id" → "word_id" for convenience.
    for k, v in word_data.items():
        if k == "id":
            values["word_id"] = v
        elif k in values:
            values[k] = v
    # JSON-encode list fields.
    for field in _LIST_FIELDS_WORDS:
        if values.get(field) is not None:
            values[field] = _to_json(values[field])

    conn.execute(
        """
        INSERT OR REPLACE INTO words (
            id, word, level, ipa_us, ipa_uk,
            phoneme_tags_us, phoneme_tags_uk,
            meaning_zh, audio_us, audio_uk,
            difficulty_tags, minimal_pair_group, content_status
        ) VALUES (
            :word_id, :word, :level, :ipa_us, :ipa_uk,
            :phoneme_tags_us, :phoneme_tags_uk,
            :meaning_zh, :audio_us, :audio_uk,
            :difficulty_tags, :minimal_pair_group, :content_status
        )
        """,
        values,
    )
    return values.get("word_id") or ""


def count_words(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS cnt FROM words").fetchone()
    return row["cnt"]


def get_word_by_id(conn: sqlite3.Connection, word_id: str) -> Optional[Word]:
    row = conn.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()
    if row is None:
        return None
    return _word_from_row(row)


# ============================================================================
# Phonemes
# ============================================================================


def upsert_phoneme(conn: sqlite3.Connection, phoneme_data: dict) -> str:
    """Insert or replace a single phoneme row. Returns the phoneme id."""
    conn.execute(
        """
        INSERT OR REPLACE INTO phonemes (
            id, symbol, accent_scope, category, priority, example_word, description_zh
        ) VALUES (
            :id, :symbol, :accent_scope, :category, :priority, :example_word, :description_zh
        )
        """,
        phoneme_data,
    )
    return phoneme_data["id"]


def count_phonemes(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS cnt FROM phonemes").fetchone()
    return row["cnt"]


def get_phoneme_by_id(conn: sqlite3.Connection, phoneme_id: str) -> Optional[Phoneme]:
    row = conn.execute("SELECT * FROM phonemes WHERE id = ?", (phoneme_id,)).fetchone()
    if row is None:
        return None
    return _phoneme_from_row(row)


# ============================================================================
# Settings
# ============================================================================


def upsert_settings(conn: sqlite3.Connection, settings: Settings) -> None:
    """Create or replace the settings row for a given user_id."""
    conn.execute(
        """
        INSERT OR REPLACE INTO settings (
            user_id, primary_accent, daily_word_count,
            show_translation, show_accent_compare,
            practice_mode, review_strength, updated_at
        ) VALUES (
            :user_id, :primary_accent, :daily_word_count,
            :show_translation, :show_accent_compare,
            :practice_mode, :review_strength, :updated_at
        )
        """,
        {
            "user_id": settings.user_id,
            "primary_accent": settings.primary_accent,
            "daily_word_count": settings.daily_word_count,
            "show_translation": int(settings.show_translation),
            "show_accent_compare": int(settings.show_accent_compare),
            "practice_mode": settings.practice_mode,
            "review_strength": settings.review_strength,
            "updated_at": settings.updated_at,
        },
    )


def get_settings(conn: sqlite3.Connection, user_id: str = "default") -> Optional[Settings]:
    row = conn.execute(
        "SELECT * FROM settings WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return None
    return _settings_from_row(row)
