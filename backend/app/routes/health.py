"""Health-check endpoint."""

from fastapi import APIRouter

from app.config import CONTENT_VERSION, DB_READY

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "content_version": CONTENT_VERSION,
        "db_ready": DB_READY,
    }
