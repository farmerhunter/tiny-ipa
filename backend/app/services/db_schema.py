"""Database schema initialization for Tiny IPA.

Defines all M2 tables up front (words, phonemes, settings, daily_sessions,
session_items, attempts, phoneme_stats) but callers only need to call
``init_db(conn)`` to create the full schema. The function is idempotent:
it uses ``IF NOT EXISTS`` on every table.
"""

import sqlite3
from typing import List


TABLES_DDL: List[str] = [
    # ------------------------------------------------------------------
    # words
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS words (
        id                TEXT PRIMARY KEY,
        word              TEXT    NOT NULL,
        level             TEXT    NOT NULL,
        ipa_us            TEXT    NOT NULL,
        ipa_uk            TEXT,
        phoneme_tags_us   TEXT    NOT NULL,   -- JSON array
        phoneme_tags_uk   TEXT,                -- JSON array
        meaning_zh        TEXT,
        audio_us          TEXT,
        audio_uk          TEXT,
        difficulty_tags   TEXT,                -- JSON array
        minimal_pair_group TEXT,
        content_status    TEXT    NOT NULL
    )
    """,
    # ------------------------------------------------------------------
    # phonemes
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS phonemes (
        id            TEXT PRIMARY KEY,
        symbol        TEXT    NOT NULL,
        accent_scope  TEXT    NOT NULL,   -- "US" | "UK" | "both"
        category      TEXT    NOT NULL,   -- "vowel" | "diphthong" | "consonant" | ...
        priority      INTEGER NOT NULL,
        example_word  TEXT,
        description_zh TEXT
    )
    """,
    # ------------------------------------------------------------------
    # settings
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS settings (
        user_id              TEXT PRIMARY KEY,
        primary_accent       TEXT    NOT NULL,
        daily_word_count     INTEGER NOT NULL,
        show_translation     INTEGER NOT NULL,   -- boolean 0/1
        show_accent_compare  INTEGER NOT NULL,   -- boolean 0/1
        practice_mode        TEXT    NOT NULL,
        review_strength      TEXT    NOT NULL,
        updated_at           TEXT    NOT NULL
    )
    """,
    # ------------------------------------------------------------------
    # daily_sessions
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS daily_sessions (
        id              TEXT PRIMARY KEY,
        user_id         TEXT    NOT NULL,
        session_date    TEXT    NOT NULL,
        primary_accent  TEXT    NOT NULL,
        status          TEXT    NOT NULL,
        created_at      TEXT    NOT NULL,
        completed_at    TEXT
    )
    """,
    # ------------------------------------------------------------------
    # session_items
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS session_items (
        id               TEXT PRIMARY KEY,
        session_id       TEXT    NOT NULL,
        word_id          TEXT    NOT NULL,
        order_index      INTEGER NOT NULL,
        target_phonemes  TEXT    NOT NULL,   -- JSON array
        question_type    TEXT    NOT NULL,
        status           TEXT    NOT NULL,
        FOREIGN KEY (session_id) REFERENCES daily_sessions(id),
        FOREIGN KEY (word_id)     REFERENCES words(id)
    )
    """,
    # ------------------------------------------------------------------
    # attempts
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS attempts (
        id               TEXT PRIMARY KEY,
        user_id          TEXT NOT NULL,
        session_item_id  TEXT NOT NULL,
        word_id          TEXT NOT NULL,
        primary_accent   TEXT NOT NULL,
        question_type    TEXT NOT NULL,
        target_phoneme   TEXT,
        selected_answer  TEXT,
        correct_answer   TEXT NOT NULL,
        is_correct       INTEGER NOT NULL,   -- boolean 0/1
        created_at       TEXT NOT NULL,
        FOREIGN KEY (session_item_id) REFERENCES session_items(id),
        FOREIGN KEY (word_id)          REFERENCES words(id)
    )
    """,
    # ------------------------------------------------------------------
    # phoneme_stats
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS phoneme_stats (
        user_id         TEXT    NOT NULL,
        primary_accent  TEXT    NOT NULL,
        phoneme_id      TEXT    NOT NULL,
        attempt_count   INTEGER NOT NULL,
        correct_count   INTEGER NOT NULL,
        last_attempt_at TEXT,
        last_wrong_at   TEXT,
        mastery_status  TEXT    NOT NULL,
        PRIMARY KEY (user_id, primary_accent, phoneme_id)
    )
    """,
]


def init_db(conn: sqlite3.Connection) -> None:
    """Execute all DDL statements to create tables if they do not exist.

    Idempotent — safe to call on an already-initialised database.
    """
    for ddl in TABLES_DDL:
        conn.execute(ddl)


def table_names(conn: sqlite3.Connection) -> List[str]:
    """Return a sorted list of user-defined table names in the database."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return sorted(r["name"] for r in rows)
