"""Practice endpoints — daily session and attempt submission."""

from fastapi import APIRouter

from app.db import get_db
from app.services.sessions import build_today_response

router = APIRouter()


@router.get("/today")
def today():
    """Return today's practice session, creating it if needed.

    Refresh-safe: repeated calls on the same date return the same session
    and items. Session and item rows are persisted in SQLite.
    """
    with get_db() as conn:
        return build_today_response(conn)
