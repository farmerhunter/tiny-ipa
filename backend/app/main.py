"""Tiny IPA FastAPI application."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.attempts import router as attempts_router
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router
from app.routes.practice import router as practice_router
from app.routes.progress import router as progress_router
from app.routes.settings import router as settings_router

app = FastAPI(title="Tiny IPA", version="0.1.0")


def _cors_origins() -> list[str]:
    raw = os.getenv("TINY_IPA_CORS_ORIGINS")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5182",
        "http://localhost:5182",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(practice_router, prefix="/api")
app.include_router(attempts_router, prefix="/api")
app.include_router(progress_router, prefix="/api")
app.include_router(settings_router, prefix="/api")

# Mount static audio directory for local dev. In production Nginx serves /audio/.
_AUDIO_DIR = os.getenv(
    "TINY_IPA_AUDIO_DIR",
    str(Path(__file__).resolve().parent.parent.parent / "audio"),
)
if os.path.isdir(_AUDIO_DIR):
    app.mount("/audio", StaticFiles(directory=_AUDIO_DIR), name="audio")
