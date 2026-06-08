"""Tiny IPA FastAPI application."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.health import router as health_router
from app.routes.practice import router as practice_router
from app.routes.attempts import router as attempts_router

app = FastAPI(title="Tiny IPA", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(practice_router, prefix="/api")
app.include_router(attempts_router, prefix="/api")

# Mount static audio directory for local dev. In production Nginx serves /audio/.
_AUDIO_DIR = os.getenv("TINY_IPA_AUDIO_DIR", str(Path(__file__).resolve().parent.parent.parent / "audio"))
if os.path.isdir(_AUDIO_DIR):
    app.mount("/audio", StaticFiles(directory=_AUDIO_DIR), name="audio")
