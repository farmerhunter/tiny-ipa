"""Progress endpoint — GET /api/progress."""

from fastapi import APIRouter

from app.db import get_db
from app.services.progress import build_progress_response

router = APIRouter()


@router.get("/progress")
def progress():
    """Return a domain summary of learner progress.

    Includes today's status, streak, total attempts/sessions, and
    weak/strong phoneme lists derived from phoneme_stats.
    """
    with get_db() as conn:
        return build_progress_response(conn)
