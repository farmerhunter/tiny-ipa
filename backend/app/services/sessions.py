"""Session orchestration for GET /api/today.

Handles the full flow: check for existing session → create or resume →
build the full API response.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.db import get_db
from app.models import DailySession, SessionItem, Settings, Word
from app.services.db_store import (
    create_session,
    create_session_item,
    get_session_for_date,
    get_session_items,
    get_settings,
    get_word_by_id,
)
from app.services.questions import generate_question
from app.services.scheduler import select_daily_words


def _today_date_str() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(s: str) -> int:
    """Cross-process stable hash — ``hashlib.md5`` instead of Python ``hash()``."""
    return int(hashlib.md5(s.encode()).hexdigest(), 16) & 0x7FFFFFFF


def _seed_from_date(session_date: str) -> int:
    """Deterministic seed so same-date calls get the same word ordering."""
    return _stable_hash(session_date)


def build_today_response(
    conn,
    *,
    user_id: str = "default",
    accent: str = "US",
    db_path: str = "",
) -> dict:
    """Run the full /api/today flow and return the response dict.

    This is the single entry point called by the route handler.
    """
    session_date = _today_date_str()

    # ---- load settings ------------------------------------------------------
    settings = get_settings(conn, user_id)
    if settings is None:
        return {
            "error": "CONTENT_NOT_READY",
            "detail": "Settings not initialised. Run import_words.py first.",
        }

    daily_word_count = settings.daily_word_count

    # ---- check for existing session -----------------------------------------
    existing = get_session_for_date(conn, user_id, session_date, accent)
    if existing is not None:
        items = get_session_items(conn, existing.id)
        return _build_response(
            session=existing,
            items=items,
            daily_word_count=daily_word_count,
            conn=conn,
            accent=accent,
        )

    # ---- create new session -------------------------------------------------
    seed = _seed_from_date(session_date)
    words = select_daily_words(conn, daily_word_count, accent, seed=seed)

    if not words:
        return {
            "error": "CONTENT_NOT_READY",
            "detail": "No usable words found. Run import_words.py first.",
        }

    # Build a distractor pool from all available word IPAs
    all_ipas = _build_distractor_pool(conn, accent)

    session_id = f"{session_date}-{user_id}"
    session = DailySession(
        id=session_id,
        user_id=user_id,
        session_date=session_date,
        primary_accent=accent,
        status="in_progress",
        created_at=_now_iso(),
        completed_at=None,
    )
    create_session(conn, session)

    items: List[SessionItem] = []
    for i, word in enumerate(words):
        item_id = f"{session_id}_item_{i + 1:03d}"
        item = SessionItem(
            id=item_id,
            session_id=session_id,
            word_id=word.id,
            order_index=i,
            target_phonemes=word.phoneme_tags_us if accent == "US" else (word.phoneme_tags_uk or []),
            question_type="choose_ipa",
            status="pending",
        )
        create_session_item(conn, item)
        items.append(item)

    return _build_response(
        session=session,
        items=items,
        daily_word_count=daily_word_count,
        conn=conn,
        accent=accent,
    )


def _build_distractor_pool(conn, accent: str) -> List[str]:
    """Collect IPA strings from the words table for distractor generation."""
    ipa_field = "ipa_us" if accent.upper() == "US" else "ipa_uk"
    rows = conn.execute(
        f"""
        SELECT DISTINCT {ipa_field} FROM words
        WHERE {ipa_field} IS NOT NULL AND {ipa_field} != ''
        LIMIT 200
        """
    ).fetchall()
    return [r[0] for r in rows if r[0]]


def _build_response(
    *,
    session: DailySession,
    items: List[SessionItem],
    daily_word_count: int,
    conn,
    accent: str,
) -> dict:
    """Assemble the /api/today JSON response from session + items."""
    distractor_pool = _build_distractor_pool(conn, accent)
    item_dicts: List[dict] = []
    for item in items:
        word = get_word_by_id(conn, item.word_id)
        if word is None:
            continue

        question = generate_question(
            word,
            accent=accent,
            distractor_pool=distractor_pool,
            seed=_stable_hash(item.id),
        )

        item_dicts.append(
            {
                "session_item_id": item.id,
                "word_id": word.id,
                "display_ipa": word.ipa_us if accent == "US" else (word.ipa_uk or ""),
                "word": word.word,
                "meaning_zh": word.meaning_zh,
                "audio_url": word.audio_us if accent == "US" else word.audio_uk,
                "target_phonemes": item.target_phonemes,
                "question": question,
            }
        )

    return {
        "session_id": session.id,
        "date": session.session_date,
        "primary_accent": session.primary_accent,
        "daily_word_count": daily_word_count,
        "status": session.status,
        "items": item_dicts,
    }
