"""Attempt submission endpoint — POST /api/attempt."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.db import get_db
from app.models import Attempt
from app.services.db_store import (
    all_session_items_attempted,
    create_attempt,
    get_session_by_id,
    get_session_items,
    get_word_by_id,
    mark_session_completed,
    mark_session_item_complete,
)
from app.services.grading import determine_correct_answer, grade_attempt
from app.services.progress import update_phoneme_stats

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/attempt")
async def attempt(request: Request):
    """Submit a practice attempt for grading.

    Expects JSON body::

        {"session_item_id": "...", "selected_answer": "..."}

    The correct answer is determined server-side. Client must not
    submit ``correct_answer`` — it is ignored if present.
    """
    body = await request.json()
    session_item_id = body.get("session_item_id", "")
    selected_answer = body.get("selected_answer", "")

    if not session_item_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_ATTEMPT", "detail": "Missing session_item_id"},
        )

    with get_db() as conn:
        # Resolve session from the session_item_id prefix.
        # Items have ids like "2026-06-06-default_item_001".
        # The session_id is the prefix before the last "_item_".
        parts = session_item_id.rsplit("_item_", 1)
        if len(parts) != 2:
            raise HTTPException(
                status_code=404,
                detail={"error": "ITEM_NOT_FOUND", "detail": f"Invalid item id: {session_item_id}"},
            )

        # Find the matching session item across all sessions. Since the
        # item id is globally unique (session prefix embedded), we look
        # it up directly via the session it belongs to.
        session_id = parts[0]
        items = get_session_items(conn, session_id)
        item = next((it for it in items if it.id == session_item_id), None)
        if item is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "ITEM_NOT_FOUND", "detail": session_item_id},
            )

        # Check session status.
        session = get_session_by_id(conn, session_id)

        if session is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "SESSION_NOT_FOUND", "detail": session_id},
            )
        if session.status == "completed":
            raise HTTPException(
                status_code=400,
                detail={"error": "SESSION_ALREADY_COMPLETED", "detail": session_id},
            )

        # Get the word for grading.
        word = get_word_by_id(conn, item.word_id)
        if word is None:
            raise HTTPException(
                status_code=400,
                detail={"error": "CONTENT_NOT_READY", "detail": f"Word not found: {item.word_id}"},
            )

        # Server-side grading.
        correct_answer = determine_correct_answer(item, word, session.primary_accent)
        is_correct = grade_attempt(selected_answer, correct_answer)

        # Persist attempt.
        timestamp = _now_iso()
        attempt_row = Attempt(
            id=str(uuid.uuid4()),
            user_id="default",
            session_item_id=session_item_id,
            word_id=item.word_id,
            primary_accent=session.primary_accent,
            question_type=item.question_type,
            correct_answer=correct_answer,
            is_correct=is_correct,
            created_at=timestamp,
            selected_answer=selected_answer,
            target_phoneme=item.target_phonemes[0] if item.target_phonemes else None,
        )
        create_attempt(conn, attempt_row)
        mark_session_item_complete(conn, session_item_id)

        # Update phoneme stats.
        updated_phonemes = update_phoneme_stats(
            conn,
            user_id="default",
            primary_accent=session.primary_accent,
            target_phonemes=item.target_phonemes,
            is_correct=is_correct,
            timestamp=timestamp,
        )

        # Determine next_action.
        next_action = "next_item"
        if all_session_items_attempted(conn, session_id):
            mark_session_completed(conn, session_id, timestamp)
            next_action = "group_complete"

        return {
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "updated_phonemes": updated_phonemes,
            "next_action": next_action,
        }
