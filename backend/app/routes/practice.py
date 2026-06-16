"""Practice endpoints — daily session and attempt submission."""

from fastapi import APIRouter

from app.db import get_db
from app.services.sessions import build_recent_mistake_review_response, build_today_response

router = APIRouter()


@router.get("/today")
def today():
    """Return today's practice session, creating it if needed.

    Refresh-safe: repeated calls on the same date return the same session
    and items. Session and item rows are persisted in SQLite.
    """
    with get_db() as conn:
        return build_today_response(conn)


@router.post("/review/recent-mistakes")
def recent_mistake_review():
    """Create or resume a review group from recent wrong answers."""
    with get_db() as conn:
        return build_recent_mistake_review_response(conn)
