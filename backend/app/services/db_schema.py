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
    # users
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS users (
        id             TEXT PRIMARY KEY,
        username       TEXT    NOT NULL UNIQUE,
        password_hash  TEXT    NOT NULL,
        is_owner       INTEGER NOT NULL DEFAULT 0,
        is_active      INTEGER NOT NULL DEFAULT 1,
        created_at     TEXT    NOT NULL,
        updated_at     TEXT    NOT NULL
    )
    """,
    # ------------------------------------------------------------------
    # auth_sessions
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS auth_sessions (
        id            TEXT PRIMARY KEY,
        user_id       TEXT    NOT NULL,
        token_hash    TEXT    NOT NULL UNIQUE,
        created_at    TEXT    NOT NULL,
        last_seen_at  TEXT    NOT NULL,
        expires_at    TEXT    NOT NULL,
        revoked_at    TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
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
        learner_level        TEXT    NOT NULL DEFAULT 'entry',
        ui_language          TEXT    NOT NULL DEFAULT 'zh-CN',
        focus_phonemes       TEXT    NOT NULL DEFAULT '[]', -- JSON array
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
        completed_at    TEXT,
        group_index     INTEGER NOT NULL DEFAULT 1,
        group_type      TEXT    NOT NULL DEFAULT 'normal',
        learner_level   TEXT    NOT NULL DEFAULT 'entry',
        source_session_item_ids TEXT NOT NULL DEFAULT '[]',
        source_scope     TEXT,
        source_group_id  TEXT,
        focus_phonemes   TEXT NOT NULL DEFAULT '[]'
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
    ensure_users_schema(conn)
    ensure_auth_sessions_schema(conn)
    ensure_settings_schema(conn)
    ensure_daily_sessions_schema(conn)


def ensure_users_schema(conn: sqlite3.Connection) -> None:
    """Apply compatibility patches for existing users tables."""
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if table is None:
        return

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    if "is_owner" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_owner INTEGER NOT NULL DEFAULT 0")
    if "is_active" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    if "created_at" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
    if "updated_at" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")


def ensure_auth_sessions_schema(conn: sqlite3.Connection) -> None:
    """Apply compatibility patches for existing auth_sessions tables."""
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='auth_sessions'"
    ).fetchone()
    if table is None:
        return

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(auth_sessions)").fetchall()
    }
    if "last_seen_at" not in columns:
        conn.execute(
            "ALTER TABLE auth_sessions ADD COLUMN last_seen_at TEXT NOT NULL DEFAULT ''"
        )
    if "expires_at" not in columns:
        conn.execute("ALTER TABLE auth_sessions ADD COLUMN expires_at TEXT NOT NULL DEFAULT ''")
    if "revoked_at" not in columns:
        conn.execute("ALTER TABLE auth_sessions ADD COLUMN revoked_at TEXT")


def ensure_settings_schema(conn: sqlite3.Connection) -> None:
    """Apply tiny compatibility patches for existing settings tables."""
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
    ).fetchone()
    if table is None:
        return

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(settings)").fetchall()
    }
    if "focus_phonemes" not in columns:
        conn.execute(
            "ALTER TABLE settings ADD COLUMN focus_phonemes TEXT NOT NULL DEFAULT '[]'"
        )
    if "learner_level" not in columns:
        conn.execute(
            "ALTER TABLE settings ADD COLUMN learner_level TEXT NOT NULL DEFAULT 'entry'"
        )
    if "ui_language" not in columns:
        conn.execute(
            "ALTER TABLE settings ADD COLUMN ui_language TEXT NOT NULL DEFAULT 'zh-CN'"
        )


def ensure_daily_sessions_schema(conn: sqlite3.Connection) -> None:
    """Apply compatibility patches for existing daily_sessions tables."""
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_sessions'"
    ).fetchone()
    if table is None:
        return

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(daily_sessions)").fetchall()
    }
    if "group_index" not in columns:
        conn.execute(
            "ALTER TABLE daily_sessions ADD COLUMN group_index INTEGER NOT NULL DEFAULT 1"
        )
    if "group_type" not in columns:
        conn.execute(
            "ALTER TABLE daily_sessions ADD COLUMN group_type TEXT NOT NULL DEFAULT 'normal'"
        )
    if "learner_level" not in columns:
        conn.execute(
            "ALTER TABLE daily_sessions ADD COLUMN learner_level TEXT NOT NULL DEFAULT 'entry'"
        )
    if "source_session_item_ids" not in columns:
        conn.execute(
            "ALTER TABLE daily_sessions ADD COLUMN source_session_item_ids "
            "TEXT NOT NULL DEFAULT '[]'"
        )
    if "source_scope" not in columns:
        conn.execute("ALTER TABLE daily_sessions ADD COLUMN source_scope TEXT")
    if "source_group_id" not in columns:
        conn.execute("ALTER TABLE daily_sessions ADD COLUMN source_group_id TEXT")
    if "focus_phonemes" not in columns:
        conn.execute(
            "ALTER TABLE daily_sessions ADD COLUMN focus_phonemes "
            "TEXT NOT NULL DEFAULT '[]'"
        )


def table_names(conn: sqlite3.Connection) -> List[str]:
    """Return a sorted list of user-defined table names in the database."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return sorted(r["name"] for r in rows)
