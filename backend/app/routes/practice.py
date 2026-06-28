"""Practice endpoints — daily session and action-specific group starts."""

from fastapi import APIRouter, HTTPException, Request

from app.db import get_db
from app.services.sessions import (
    build_abandon_current_and_next_response,
    build_clear_focus_response,
    build_current_group_review_response,
    build_focused_group_response,
    build_minimal_pair_group_response,
    build_next_normal_group_response,
    build_recent_mistake_review_response,
    build_today_response,
)

router = APIRouter()


@router.get("/today")
def today():
    """Return today's practice hub state without creating a new group.

    Refresh-safe: repeated calls on the same date return the active normal group
    if one exists, otherwise a no-active hub response.
    """
    with get_db() as conn:
        return build_today_response(conn)


@router.post("/practice/next-normal")
def next_normal_group():
    """Resume active normal group or explicitly create the first/next normal group."""
    with get_db() as conn:
        return build_next_normal_group_response(conn)


@router.post("/practice/abandon-current-and-next")
def abandon_current_and_next_group():
    """Abandon active normal group and create the next selected-level group."""
    with get_db() as conn:
        return build_abandon_current_and_next_response(conn)


@router.post("/review/recent-mistakes")
def recent_mistake_review():
    """Create or resume a review group from recent wrong answers."""
    with get_db() as conn:
        return build_recent_mistake_review_response(conn)


@router.post("/practice/minimal-pairs")
def minimal_pair_group():
    """Create or resume a confusing-sound comparison specialty group."""
    with get_db() as conn:
        return build_minimal_pair_group_response(conn)


@router.post("/review/current-group")
async def current_group_review(request: Request):
    """Create a review group from wrong answers in one completed/current group."""
    body = await request.json()
    group_id = body.get("group_id") or body.get("source_group_id")
    if not isinstance(group_id, str) or not group_id.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_REVIEW_SOURCE",
                "detail": "group_id is required for current-group review.",
            },
        )
    with get_db() as conn:
        response = build_current_group_review_response(
            conn, source_group_id=group_id.strip()
        )
    if response.get("error") == "GROUP_NOT_FOUND":
        raise HTTPException(status_code=404, detail=response)
    return response


@router.post("/practice/focus")
async def focused_group(request: Request):
    """Select focus phonemes and start or resume focused practice."""
    body = await request.json()
    focus_phonemes = body.get("focus_phonemes")
    if (
        not isinstance(focus_phonemes, list)
        or not focus_phonemes
        or any(
            not isinstance(item, str) or not item.strip()
            for item in focus_phonemes
        )
    ):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_FOCUS",
                "detail": "focus_phonemes must be a list of non-empty strings.",
            },
        )
    with get_db() as conn:
        return build_focused_group_response(
            conn,
            focus_phonemes=[item.strip() for item in focus_phonemes],
        )


@router.post("/practice/clear-focus")
def clear_focus():
    """Clear focus phonemes and return normal practice state."""
    with get_db() as conn:
        return build_clear_focus_response(conn)
