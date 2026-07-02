"""Repository helpers for words, phonemes, settings, sessions, and session_items tables.

Plain sqlite3 queries — no ORM. JSON-serialised list fields are handled
at this layer so callers work with Python lists, not raw strings.
"""

from __future__ import annotations

import json
import sqlite3
from typing import List, Optional

from app.models import (
    Attempt,
    AuthSession,
    DailySession,
    Phoneme,
    SessionItem,
    Settings,
    User,
    Word,
)
from app.services.db_schema import (
    ensure_auth_sessions_schema,
    ensure_daily_sessions_schema,
    ensure_settings_schema,
    ensure_users_schema,
)

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


def _user_from_row(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        is_owner=bool(row["is_owner"]),
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _auth_session_from_row(row: sqlite3.Row) -> AuthSession:
    return AuthSession(
        id=row["id"],
        user_id=row["user_id"],
        token_hash=row["token_hash"],
        created_at=row["created_at"],
        last_seen_at=row["last_seen_at"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
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
        learner_level=row["learner_level"],
        ui_language=row["ui_language"],
        focus_phonemes=_parse_list(row["focus_phonemes"]) or [],
        updated_at=row["updated_at"],
    )


# ============================================================================
# Users
# ============================================================================


def create_user(conn: sqlite3.Connection, user: User) -> str:
    """Insert a user row. Returns the user id."""
    ensure_users_schema(conn)
    conn.execute(
        """
        INSERT INTO users (
            id, username, password_hash, is_owner, is_active, created_at, updated_at
        ) VALUES (
            :id, :username, :password_hash, :is_owner, :is_active, :created_at, :updated_at
        )
        """,
        {
            "id": user.id,
            "username": user.username,
            "password_hash": user.password_hash,
            "is_owner": int(user.is_owner),
            "is_active": int(user.is_active),
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        },
    )
    return user.id


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> Optional[User]:
    ensure_users_schema(conn)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    return _user_from_row(row)


def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[User]:
    ensure_users_schema(conn)
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        return None
    return _user_from_row(row)


def count_owner_users(conn: sqlite3.Connection) -> int:
    ensure_users_schema(conn)
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM users WHERE is_owner = 1"
    ).fetchone()
    return int(row["cnt"] if row else 0)


# ============================================================================
# Auth sessions
# ============================================================================


def create_auth_session(conn: sqlite3.Connection, session: AuthSession) -> str:
    """Insert a server-side auth session row. Returns the session id."""
    ensure_auth_sessions_schema(conn)
    conn.execute(
        """
        INSERT INTO auth_sessions (
            id, user_id, token_hash, created_at, last_seen_at, expires_at, revoked_at
        ) VALUES (
            :id, :user_id, :token_hash, :created_at, :last_seen_at, :expires_at, :revoked_at
        )
        """,
        {
            "id": session.id,
            "user_id": session.user_id,
            "token_hash": session.token_hash,
            "created_at": session.created_at,
            "last_seen_at": session.last_seen_at,
            "expires_at": session.expires_at,
            "revoked_at": session.revoked_at,
        },
    )
    return session.id


def get_auth_session_by_token_hash(
    conn: sqlite3.Connection, token_hash: str
) -> Optional[AuthSession]:
    ensure_auth_sessions_schema(conn)
    row = conn.execute(
        "SELECT * FROM auth_sessions WHERE token_hash = ?", (token_hash,)
    ).fetchone()
    if row is None:
        return None
    return _auth_session_from_row(row)


def touch_auth_session(
    conn: sqlite3.Connection, session_id: str, last_seen_at: str
) -> None:
    ensure_auth_sessions_schema(conn)
    conn.execute(
        "UPDATE auth_sessions SET last_seen_at = ? WHERE id = ?",
        (last_seen_at, session_id),
    )


def revoke_auth_session_by_token_hash(
    conn: sqlite3.Connection, token_hash: str, revoked_at: str
) -> None:
    ensure_auth_sessions_schema(conn)
    conn.execute(
        """
        UPDATE auth_sessions
        SET revoked_at = ?
        WHERE token_hash = ? AND revoked_at IS NULL
        """,
        (revoked_at, token_hash),
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
    ensure_settings_schema(conn)
    conn.execute(
        """
        INSERT OR REPLACE INTO settings (
            user_id, primary_accent, daily_word_count,
            show_translation, show_accent_compare,
            practice_mode, review_strength, learner_level, ui_language,
            focus_phonemes, updated_at
        ) VALUES (
            :user_id, :primary_accent, :daily_word_count,
            :show_translation, :show_accent_compare,
            :practice_mode, :review_strength, :learner_level, :ui_language,
            :focus_phonemes, :updated_at
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
            "learner_level": settings.learner_level,
            "ui_language": settings.ui_language,
            "focus_phonemes": _to_json(settings.focus_phonemes),
            "updated_at": settings.updated_at,
        },
    )


def get_settings(conn: sqlite3.Connection, user_id: str = "default") -> Optional[Settings]:
    ensure_settings_schema(conn)
    row = conn.execute(
        "SELECT * FROM settings WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return None
    return _settings_from_row(row)


# ============================================================================
# Daily sessions
# ============================================================================


def _session_from_row(row: sqlite3.Row) -> DailySession:
    return DailySession(
        id=row["id"],
        user_id=row["user_id"],
        session_date=row["session_date"],
        primary_accent=row["primary_accent"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        group_index=row["group_index"],
        group_type=row["group_type"],
        learner_level=row["learner_level"],
        source_session_item_ids=_parse_list(row["source_session_item_ids"]) or [],
        source_scope=row["source_scope"],
        source_group_id=row["source_group_id"],
        focus_phonemes=_parse_list(row["focus_phonemes"]) or [],
    )


def _session_item_from_row(row: sqlite3.Row) -> SessionItem:
    return SessionItem(
        id=row["id"],
        session_id=row["session_id"],
        word_id=row["word_id"],
        order_index=row["order_index"],
        target_phonemes=_parse_list(row["target_phonemes"]) or [],
        question_type=row["question_type"],
        status=row["status"],
    )


def create_session(conn: sqlite3.Connection, session: DailySession) -> str:
    """Insert a new daily session row. Returns the session id."""
    ensure_daily_sessions_schema(conn)
    conn.execute(
        """
        INSERT INTO daily_sessions (
            id, user_id, session_date, primary_accent, status, created_at, completed_at,
            group_index, group_type, learner_level, source_session_item_ids,
            source_scope, source_group_id, focus_phonemes
        ) VALUES (
            :id, :user_id, :session_date, :primary_accent, :status, :created_at,
            :completed_at, :group_index, :group_type, :learner_level, :source_session_item_ids,
            :source_scope, :source_group_id, :focus_phonemes
        )
        """,
        {
            "id": session.id,
            "user_id": session.user_id,
            "session_date": session.session_date,
            "primary_accent": session.primary_accent,
            "status": session.status,
            "created_at": session.created_at,
            "completed_at": session.completed_at,
            "group_index": session.group_index,
            "group_type": session.group_type,
            "learner_level": session.learner_level,
            "source_session_item_ids": _to_json(session.source_session_item_ids),
            "source_scope": session.source_scope,
            "source_group_id": session.source_group_id,
            "focus_phonemes": _to_json(session.focus_phonemes),
        },
    )
    return session.id


def get_active_session_for_date(
    conn: sqlite3.Connection,
    user_id: str,
    session_date: str,
    primary_accent: str,
    group_type: str = "normal",
    source_scope: Optional[str] = None,
    source_group_id: Optional[str] = None,
    focus_phonemes: Optional[List[str]] = None,
    learner_level: Optional[str] = None,
) -> Optional[DailySession]:
    """Return the active same-day group for the given type, if one exists."""
    ensure_daily_sessions_schema(conn)
    filters = [
        "user_id = ?",
        "session_date = ?",
        "primary_accent = ?",
        "group_type = ?",
        "status = 'in_progress'",
    ]
    params: list = [user_id, session_date, primary_accent, group_type]
    if source_scope is not None:
        filters.append("source_scope = ?")
        params.append(source_scope)
    if source_group_id is not None:
        filters.append("source_group_id = ?")
        params.append(source_group_id)
    if focus_phonemes is not None:
        filters.append("focus_phonemes = ?")
        params.append(_to_json(focus_phonemes))
    if learner_level is not None:
        filters.append("learner_level = ?")
        params.append(learner_level)
    row = conn.execute(
        f"""
        SELECT * FROM daily_sessions
        WHERE {" AND ".join(filters)}
        ORDER BY group_index DESC, created_at DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    if row is None:
        return None
    return _session_from_row(row)


def get_session_for_date(
    conn: sqlite3.Connection, user_id: str, session_date: str, primary_accent: str
) -> Optional[DailySession]:
    """Return the daily session for the given user, date and accent, or None."""
    ensure_daily_sessions_schema(conn)
    row = conn.execute(
        """
        SELECT * FROM daily_sessions
        WHERE user_id = ? AND session_date = ? AND primary_accent = ?
        ORDER BY
          CASE WHEN status = 'in_progress' AND group_type = 'normal' THEN 0 ELSE 1 END,
          group_index DESC,
          created_at DESC
        LIMIT 1
        """,
        (user_id, session_date, primary_accent),
    ).fetchone()
    if row is None:
        return None
    return _session_from_row(row)


def get_next_session_group_index(
    conn: sqlite3.Connection,
    user_id: str,
    session_date: str,
    primary_accent: str,
) -> int:
    """Return the next same-day practice group index for user/date/accent."""
    ensure_daily_sessions_schema(conn)
    row = conn.execute(
        """
        SELECT COALESCE(MAX(group_index), 0) AS max_group
        FROM daily_sessions
        WHERE user_id = ? AND session_date = ? AND primary_accent = ?
        """,
        (user_id, session_date, primary_accent),
    ).fetchone()
    return int(row["max_group"] if row else 0) + 1


def mark_session_completed(
    conn: sqlite3.Connection,
    session_id: str,
    completed_at: str,
) -> None:
    """Mark a practice group completed."""
    ensure_daily_sessions_schema(conn)
    conn.execute(
        """
        UPDATE daily_sessions
        SET status = 'completed', completed_at = ?
        WHERE id = ?
        """,
        (completed_at, session_id),
    )


def mark_session_abandoned(
    conn: sqlite3.Connection,
    session_id: str,
    completed_at: str,
) -> None:
    """Mark a practice group abandoned without counting it as completed."""
    ensure_daily_sessions_schema(conn)
    conn.execute(
        """
        UPDATE daily_sessions
        SET status = 'abandoned', completed_at = ?
        WHERE id = ? AND status = 'in_progress'
        """,
        (completed_at, session_id),
    )


def create_session_item(conn: sqlite3.Connection, item: SessionItem) -> str:
    """Insert a session item row. Returns the item id."""
    conn.execute(
        """
        INSERT INTO session_items (
            id, session_id, word_id, order_index, target_phonemes, question_type, status
        ) VALUES (
            :id, :session_id, :word_id, :order_index, :target_phonemes, :question_type, :status
        )
        """,
        {
            "id": item.id,
            "session_id": item.session_id,
            "word_id": item.word_id,
            "order_index": item.order_index,
            "target_phonemes": _to_json(item.target_phonemes),
            "question_type": item.question_type,
            "status": item.status,
        },
    )
    return item.id


def get_session_by_id(conn: sqlite3.Connection, session_id: str) -> Optional[DailySession]:
    """Return a daily session by its primary key, or None."""
    ensure_daily_sessions_schema(conn)
    row = conn.execute(
        "SELECT * FROM daily_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None:
        return None
    return _session_from_row(row)


def get_session_items(
    conn: sqlite3.Connection, session_id: str
) -> List[SessionItem]:
    """Return all session items for a session, ordered by order_index."""
    rows = conn.execute(
        "SELECT * FROM session_items WHERE session_id = ? ORDER BY order_index",
        (session_id,),
    ).fetchall()
    return [_session_item_from_row(r) for r in rows]


def get_latest_attempts_for_session_items(
    conn: sqlite3.Connection,
    session_item_ids: List[str],
) -> dict[str, dict]:
    """Return the latest persisted attempt for each requested session item."""
    if not session_item_ids:
        return {}

    placeholders = ",".join("?" for _ in session_item_ids)
    rows = conn.execute(
        f"""
        SELECT a.*
        FROM attempts a
        JOIN (
            SELECT session_item_id, MAX(created_at) AS created_at
            FROM attempts
            WHERE session_item_id IN ({placeholders})
            GROUP BY session_item_id
        ) latest
          ON latest.session_item_id = a.session_item_id
         AND latest.created_at = a.created_at
        ORDER BY a.created_at DESC
        """,
        session_item_ids,
    ).fetchall()
    return {
        row["session_item_id"]: {
            "selected_answer": row["selected_answer"],
            "correct_answer": row["correct_answer"],
            "is_correct": bool(row["is_correct"]),
        }
        for row in rows
    }


def get_recent_incorrect_attempt_sources(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    primary_accent: str,
    limit: int = 10,
) -> List[dict]:
    """Return recent wrong-answer words with their latest source session item."""
    rows = conn.execute(
        """
        SELECT a.word_id, a.session_item_id, a.created_at AS last_wrong_at
        FROM attempts a
        JOIN words w ON w.id = a.word_id
        WHERE a.user_id = ?
          AND a.primary_accent = ?
          AND a.is_correct = 0
          AND w.content_status != 'disabled'
        ORDER BY a.created_at DESC
        """,
        (user_id, primary_accent),
    ).fetchall()
    sources = []
    seen_word_ids = set()
    for row in rows:
        if row["word_id"] in seen_word_ids:
            continue
        seen_word_ids.add(row["word_id"])
        sources.append({
            "word_id": row["word_id"],
            "session_item_id": row["session_item_id"],
            "last_wrong_at": row["last_wrong_at"],
        })
        if len(sources) >= limit:
            break
    return sources


def get_session_incorrect_attempt_sources(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    primary_accent: str,
    session_id: str,
    limit: int = 10,
) -> List[dict]:
    """Return wrong-answer words sourced from one practice group."""
    rows = conn.execute(
        """
        SELECT a.word_id, a.session_item_id, a.created_at AS last_wrong_at
        FROM attempts a
        JOIN session_items si ON si.id = a.session_item_id
        JOIN words w ON w.id = a.word_id
        WHERE a.user_id = ?
          AND a.primary_accent = ?
          AND si.session_id = ?
          AND a.is_correct = 0
          AND w.content_status != 'disabled'
        ORDER BY a.created_at DESC
        """,
        (user_id, primary_accent, session_id),
    ).fetchall()
    sources = []
    seen_word_ids = set()
    for row in rows:
        if row["word_id"] in seen_word_ids:
            continue
        seen_word_ids.add(row["word_id"])
        sources.append({
            "word_id": row["word_id"],
            "session_item_id": row["session_item_id"],
            "last_wrong_at": row["last_wrong_at"],
        })
        if len(sources) >= limit:
            break
    return sources


# ============================================================================
# Attempts
# ============================================================================


def create_attempt(conn: sqlite3.Connection, attempt: Attempt) -> str:
    """Insert an attempt row. Returns the attempt id."""
    conn.execute(
        """
        INSERT INTO attempts (
            id, user_id, session_item_id, word_id, primary_accent,
            question_type, target_phoneme, selected_answer, correct_answer,
            is_correct, created_at
        ) VALUES (
            :id, :user_id, :session_item_id, :word_id, :primary_accent,
            :question_type, :target_phoneme, :selected_answer, :correct_answer,
            :is_correct, :created_at
        )
        """,
        {
            "id": attempt.id,
            "user_id": attempt.user_id,
            "session_item_id": attempt.session_item_id,
            "word_id": attempt.word_id,
            "primary_accent": attempt.primary_accent,
            "question_type": attempt.question_type,
            "target_phoneme": attempt.target_phoneme,
            "selected_answer": attempt.selected_answer,
            "correct_answer": attempt.correct_answer,
            "is_correct": int(attempt.is_correct),
            "created_at": attempt.created_at,
        },
    )
    return attempt.id


def mark_session_item_complete(conn: sqlite3.Connection, session_item_id: str) -> None:
    """Mark a session item complete after an attempt."""
    conn.execute(
        "UPDATE session_items SET status = 'complete' WHERE id = ?",
        (session_item_id,),
    )


def all_session_items_attempted(conn: sqlite3.Connection, session_id: str) -> bool:
    """Return True once every item in a session has at least one attempt."""
    row = conn.execute(
        """
        SELECT
          COUNT(*) AS total_items,
          COUNT(DISTINCT a.session_item_id) AS attempted_items
        FROM session_items si
        LEFT JOIN attempts a ON a.session_item_id = si.id
        WHERE si.session_id = ?
        """,
        (session_id,),
    ).fetchone()
    if row is None or row["total_items"] == 0:
        return False
    return row["attempted_items"] >= row["total_items"]
