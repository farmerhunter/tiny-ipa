"""Progress endpoint — GET /api/progress."""

from fastapi import APIRouter, Depends

from app.auth_dependencies import require_current_user
from app.db import get_db
from app.models import User
from app.services.progress import build_progress_response

router = APIRouter()


@router.get("/progress")
def progress(current_user: User = Depends(require_current_user)):
    """Return a domain summary of learner progress.

    Includes today's status, streak, total attempts/sessions, and
    weak/strong phoneme lists derived from phoneme_stats.
    """
    with get_db() as conn:
        return build_progress_response(conn, user_id=current_user.id)
