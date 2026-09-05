"""Health-check endpoint."""

from fastapi import APIRouter, Response

from app import config

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "content_version": config.CONTENT_VERSION,
        "db_ready": config.DB_READY,
    }


@router.get("/version")
def version(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": "ok",
        "release_id": config.RELEASE_ID,
        "commit": config.RELEASE_COMMIT,
        "tag": config.RELEASE_TAG or None,
    }
