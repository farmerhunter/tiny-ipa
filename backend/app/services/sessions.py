"""Session orchestration for GET /api/today.

Handles the full flow: check for existing session → create or resume →
build the full API response.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import List, Optional

from app.models import DailySession, SessionItem
from app.services.db_store import (
    create_session,
    create_session_item,
    get_active_session_for_date,
    get_next_session_group_index,
    get_recent_incorrect_attempt_sources,
    get_session_by_id,
    get_session_incorrect_attempt_sources,
    get_session_items,
    get_settings,
    get_word_by_id,
    upsert_settings,
)
from app.services.questions import generate_question
from app.services.scheduler import select_daily_words

_LEARNER_LEVEL_LABELS = {
    "entry": "Entry",
    "mid": "Mid",
}


def _today_date_str() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(s: str) -> int:
    """Cross-process stable hash — ``hashlib.md5`` instead of Python ``hash()``."""
    return int(hashlib.md5(s.encode()).hexdigest(), 16) & 0x7FFFFFFF


def _seed_from_group(session_date: str, group_index: int, group_type: str) -> int:
    return _stable_hash(f"{session_date}:{group_index}:{group_type}")


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
    existing = get_active_session_for_date(conn, user_id, session_date, accent, "normal")
    if existing is not None:
        items = get_session_items(conn, existing.id)
        return _build_response(
            session=existing,
            items=items,
            daily_word_count=daily_word_count,
            conn=conn,
            accent=accent,
            origin="normal_resume",
            source_scope="normal_current",
            focus_phonemes=existing.focus_phonemes or settings.focus_phonemes,
            action_label=f"Resume {learner_level_label(existing.learner_level)} Group {existing.group_index}",
        )

    # ---- create new session -------------------------------------------------
    group_index = get_next_session_group_index(conn, user_id, session_date, accent)
    seed = _seed_from_group(session_date, group_index, "normal")
    words = select_daily_words(
        conn,
        daily_word_count,
        accent,
        seed=seed,
        user_id=user_id,
        review_strength=settings.review_strength,
        learner_level=settings.learner_level,
        focus_phonemes=settings.focus_phonemes,
    )

    if not words:
        return {
            "error": "CONTENT_NOT_READY",
            "detail": (
                f"No usable {learner_level_label(settings.learner_level)} words found. "
                "Run the level content import first."
            ),
        }

    session, items = _create_group_from_words(
        conn,
        words=words,
        user_id=user_id,
        session_date=session_date,
        accent=accent,
        group_index=group_index,
        group_type="normal",
        learner_level=settings.learner_level,
        focus_phonemes=settings.focus_phonemes,
    )

    return _build_response(
        session=session,
        items=items,
        daily_word_count=daily_word_count,
        conn=conn,
        accent=accent,
        origin="normal_start",
        source_scope="normal_current",
        focus_phonemes=settings.focus_phonemes,
        action_label=f"Start {learner_level_label(session.learner_level)} Group {session.group_index}",
    )


def build_next_normal_group_response(
    conn,
    *,
    user_id: str = "default",
    accent: str = "US",
) -> dict:
    """Resume the active normal group or create the next normal same-day group."""
    response = build_today_response(conn, user_id=user_id, accent=accent)
    if "error" in response:
        return response
    if response.get("origin") == "normal_start":
        response["origin"] = "normal_next"
    response["source_scope"] = "normal_next"
    if response.get("origin") == "normal_next":
        response["action_label"] = (
            f"Start {learner_level_label(response.get('learner_level'))} "
            f"Group {response['group_index']}"
        )
    return response


def build_recent_mistake_review_response(
    conn,
    *,
    user_id: str = "default",
    accent: str = "US",
    limit: int = 10,
) -> dict:
    """Create or resume a same-day review group from recent wrong attempts."""
    session_date = _today_date_str()
    settings = get_settings(conn, user_id)
    if settings is None:
        return {
            "error": "CONTENT_NOT_READY",
            "detail": "Settings not initialised. Run import_words.py first.",
        }

    existing = get_active_session_for_date(
        conn,
        user_id,
        session_date,
        accent,
        "mistake_review",
        source_scope="recent_global",
    )
    if existing is not None:
        items = get_session_items(conn, existing.id)
        return _build_response(
            session=existing,
            items=items,
            daily_word_count=settings.daily_word_count,
            conn=conn,
            accent=accent,
            origin="recent_review_resume",
            source_scope="recent_global",
            action_label=f"Resume Review Group {existing.group_index}",
        )

    sources = get_recent_incorrect_attempt_sources(
        conn,
        user_id=user_id,
        primary_accent=accent,
        limit=min(max(limit, 1), settings.daily_word_count),
    )
    if not sources:
        return {
            "group_type": "mistake_review",
            "status": "empty",
            "items": [],
            "source_count": 0,
            "origin": "recent_review_empty",
            "source_scope": "recent_global",
            "detail": "No recent incorrect attempts are available for review.",
        }

    words = []
    source_item_ids = []
    for source in sources:
        word = get_word_by_id(conn, source["word_id"])
        if word is not None:
            words.append(word)
            source_item_ids.append(source["session_item_id"])

    if not words:
        return {
            "group_type": "mistake_review",
            "status": "empty",
            "items": [],
            "source_count": 0,
            "origin": "recent_review_empty",
            "source_scope": "recent_global",
            "detail": "No reviewable words are available for recent mistakes.",
        }

    group_index = get_next_session_group_index(conn, user_id, session_date, accent)
    session, items = _create_group_from_words(
        conn,
        words=words,
        user_id=user_id,
        session_date=session_date,
        accent=accent,
        group_index=group_index,
        group_type="mistake_review",
        learner_level=settings.learner_level,
        source_session_item_ids=source_item_ids,
        source_scope="recent_global",
    )
    response = _build_response(
        session=session,
        items=items,
        daily_word_count=settings.daily_word_count,
        conn=conn,
        accent=accent,
        origin="recent_review_start",
        source_scope="recent_global",
        action_label=f"Start Recent Review Group {session.group_index}",
    )
    response["source_count"] = len(source_item_ids)
    return response


def build_current_group_review_response(
    conn,
    *,
    source_group_id: str,
    user_id: str = "default",
    accent: str = "US",
    limit: int = 10,
) -> dict:
    """Create a review group from wrong answers in one source group."""
    session_date = _today_date_str()
    settings = get_settings(conn, user_id)
    if settings is None:
        return {
            "error": "CONTENT_NOT_READY",
            "detail": "Settings not initialised. Run import_words.py first.",
        }

    source_session = get_session_by_id(conn, source_group_id)
    if source_session is None:
        return {
            "error": "GROUP_NOT_FOUND",
            "detail": f"No practice group found for {source_group_id}.",
        }

    sources = get_session_incorrect_attempt_sources(
        conn,
        user_id=user_id,
        primary_accent=accent,
        session_id=source_group_id,
        limit=min(max(limit, 1), settings.daily_word_count),
    )
    if not sources:
        return {
            "group_type": "mistake_review",
            "status": "empty",
            "items": [],
            "source_count": 0,
            "origin": "current_group_review_empty",
            "source_scope": "current_group",
            "source_group_id": source_group_id,
            "detail": "No incorrect answers are available for this group.",
        }

    words = []
    source_item_ids = []
    for source in sources:
        word = get_word_by_id(conn, source["word_id"])
        if word is not None:
            words.append(word)
            source_item_ids.append(source["session_item_id"])

    if not words:
        return {
            "group_type": "mistake_review",
            "status": "empty",
            "items": [],
            "source_count": 0,
            "origin": "current_group_review_empty",
            "source_scope": "current_group",
            "source_group_id": source_group_id,
            "detail": "No reviewable words are available for this group.",
        }

    group_index = get_next_session_group_index(conn, user_id, session_date, accent)
    existing = get_active_session_for_date(
        conn,
        user_id,
        session_date,
        accent,
        "mistake_review",
        source_scope="current_group",
        source_group_id=source_group_id,
    )
    if existing is not None:
        items = get_session_items(conn, existing.id)
        response = _build_response(
            session=existing,
            items=items,
            daily_word_count=settings.daily_word_count,
            conn=conn,
            accent=accent,
            origin="current_group_review_resume",
            source_scope="current_group",
            source_group_id=source_group_id,
            action_label=f"Resume Group {source_session.group_index} review",
        )
        response["source_count"] = len(existing.source_session_item_ids)
        return response

    session, items = _create_group_from_words(
        conn,
        words=words,
        user_id=user_id,
        session_date=session_date,
        accent=accent,
        group_index=group_index,
        group_type="mistake_review",
        learner_level=source_session.learner_level,
        source_session_item_ids=source_item_ids,
        source_scope="current_group",
        source_group_id=source_group_id,
    )
    response = _build_response(
        session=session,
        items=items,
        daily_word_count=settings.daily_word_count,
        conn=conn,
        accent=accent,
        origin="current_group_review_start",
        source_scope="current_group",
        source_group_id=source_group_id,
        action_label=f"Review Group {source_session.group_index} misses",
    )
    response["source_count"] = len(source_item_ids)
    return response


def build_focused_group_response(
    conn,
    *,
    focus_phonemes: List[str],
    user_id: str = "default",
    accent: str = "US",
) -> dict:
    """Save focus selection and create/resume a weak-focus practice group."""
    session_date = _today_date_str()
    settings = get_settings(conn, user_id)
    if settings is None:
        return {
            "error": "CONTENT_NOT_READY",
            "detail": "Settings not initialised. Run import_words.py first.",
        }
    settings.focus_phonemes = focus_phonemes
    settings.updated_at = _now_iso()
    upsert_settings(conn, settings)

    existing = get_active_session_for_date(
        conn,
        user_id,
        session_date,
        accent,
        "weak_focus",
        source_scope="focus_selection",
        focus_phonemes=focus_phonemes,
        learner_level=settings.learner_level,
    )
    if existing is not None:
        items = get_session_items(conn, existing.id)
        return _build_response(
            session=existing,
            items=items,
            daily_word_count=settings.daily_word_count,
            conn=conn,
            accent=accent,
            origin="focus_resume",
            source_scope="focus_selection",
            focus_phonemes=focus_phonemes,
            action_label=f"Resume {learner_level_label(existing.learner_level)} Focus Group {existing.group_index}",
        )

    group_index = get_next_session_group_index(conn, user_id, session_date, accent)
    seed = _seed_from_group(session_date, group_index, "weak_focus")
    words = select_daily_words(
        conn,
        settings.daily_word_count,
        accent,
        seed=seed,
        user_id=user_id,
        review_strength=settings.review_strength,
        learner_level=settings.learner_level,
        focus_phonemes=focus_phonemes,
    )
    if not words:
        return {
            "error": "CONTENT_NOT_READY",
            "detail": (
                f"No usable {learner_level_label(settings.learner_level)} words found. "
                "Run the level content import first."
            ),
        }

    session, items = _create_group_from_words(
        conn,
        words=words,
        user_id=user_id,
        session_date=session_date,
        accent=accent,
        group_index=group_index,
        group_type="weak_focus",
        learner_level=settings.learner_level,
        source_scope="focus_selection",
        focus_phonemes=focus_phonemes,
    )
    return _build_response(
        session=session,
        items=items,
        daily_word_count=settings.daily_word_count,
        conn=conn,
        accent=accent,
        origin="focus_start",
        source_scope="focus_selection",
        focus_phonemes=focus_phonemes,
        action_label=f"Start {learner_level_label(session.learner_level)} Focus Group {session.group_index}",
    )


def build_clear_focus_response(
    conn,
    *,
    user_id: str = "default",
    accent: str = "US",
) -> dict:
    """Clear focus selection and return the current normal practice group."""
    settings = get_settings(conn, user_id)
    if settings is None:
        return {
            "error": "CONTENT_NOT_READY",
            "detail": "Settings not initialised. Run import_words.py first.",
        }
    settings.focus_phonemes = []
    settings.updated_at = _now_iso()
    upsert_settings(conn, settings)

    response = build_today_response(conn, user_id=user_id, accent=accent)
    if "error" not in response:
        response["origin"] = "focus_clear"
        response["source_scope"] = "normal_current"
        response["focus_phonemes"] = []
        response["detail"] = "Focus selection cleared."
    return response


def _create_group_from_words(
    conn,
    *,
    words,
    user_id: str,
    session_date: str,
    accent: str,
    group_index: int,
    group_type: str,
    learner_level: str,
    source_session_item_ids: Optional[List[str]] = None,
    source_scope: Optional[str] = None,
    source_group_id: Optional[str] = None,
    focus_phonemes: Optional[List[str]] = None,
) -> tuple[DailySession, List[SessionItem]]:
    session_id = f"{session_date}-{user_id}-g{group_index:03d}-{group_type}"
    session = DailySession(
        id=session_id,
        user_id=user_id,
        session_date=session_date,
        primary_accent=accent,
        status="in_progress",
        created_at=_now_iso(),
        completed_at=None,
        group_index=group_index,
        group_type=group_type,
        learner_level=learner_level,
        source_session_item_ids=source_session_item_ids or [],
        source_scope=source_scope,
        source_group_id=source_group_id,
        focus_phonemes=focus_phonemes or [],
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
            target_phonemes=(
                word.phoneme_tags_us if accent == "US" else (word.phoneme_tags_uk or [])
            ),
            question_type="choose_ipa",
            status="pending",
        )
        create_session_item(conn, item)
        items.append(item)
    return session, items


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


def learner_level_label(learner_level: Optional[str]) -> str:
    return _LEARNER_LEVEL_LABELS.get(learner_level or "entry", "Entry")


def _build_response(
    *,
    session: DailySession,
    items: List[SessionItem],
    daily_word_count: int,
    conn,
    accent: str,
    origin: Optional[str] = None,
    source_scope: Optional[str] = None,
    source_group_id: Optional[str] = None,
    focus_phonemes: Optional[List[str]] = None,
    action_label: Optional[str] = None,
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

    response = {
        "session_id": session.id,
        "group_id": session.id,
        "group_index": session.group_index,
        "group_type": session.group_type,
        "learner_level": session.learner_level,
        "learner_level_label": learner_level_label(session.learner_level),
        "date": session.session_date,
        "primary_accent": session.primary_accent,
        "daily_word_count": daily_word_count,
        "word_count": len(item_dicts),
        "status": session.status,
        "source_session_item_ids": session.source_session_item_ids,
        "items": item_dicts,
    }
    if origin is not None:
        response["origin"] = origin
    response_source_scope = source_scope if source_scope is not None else session.source_scope
    response_source_group_id = (
        source_group_id if source_group_id is not None else session.source_group_id
    )
    response_focus_phonemes = focus_phonemes
    if response_focus_phonemes is None and session.focus_phonemes:
        response_focus_phonemes = session.focus_phonemes
    if response_source_scope is not None:
        response["source_scope"] = response_source_scope
    if response_source_group_id is not None:
        response["source_group_id"] = response_source_group_id
    if response_focus_phonemes is not None:
        response["focus_phonemes"] = response_focus_phonemes
    if action_label is not None:
        response["action_label"] = action_label
    return response
