from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth_dependencies import require_current_user
from app.db import get_db
from app.models import User
from app.services import listening

router = APIRouter()


def require_preview():
    if not listening.enabled():
        raise HTTPException(404, detail={"error": "LISTENING_PREVIEW_DISABLED"})


@router.get("/listening/current")
def current(user: User = Depends(require_current_user)):
    if not listening.enabled():
        return {"enabled": False, "lesson": None}
    with get_db() as conn:
        return {"enabled": True, "lesson": listening.current(conn, user.id)}


@router.post("/listening/lessons", dependencies=[Depends(require_preview)])
def start(user: User = Depends(require_current_user)):
    with get_db() as conn:
        return listening.start(conn, user.id)


@router.post("/listening/lessons/{lesson_id}/actions", dependencies=[Depends(require_preview)])
async def action(lesson_id: str, request: Request, user: User = Depends(require_current_user)):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, detail={"error": "LISTENING_INVALID_ACTION"})
    with get_db() as conn:
        return listening.act(conn, user.id, lesson_id, body)
