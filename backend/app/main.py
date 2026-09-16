"""Tiny IPA FastAPI application."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth_dependencies import (
    AuthConfigurationError,
    auth_runtime_config,
    request_origin_is_allowed,
)
from app.routes.attempts import router as attempts_router
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router
from app.routes.practice import router as practice_router
from app.routes.progress import router as progress_router
from app.routes.settings import router as settings_router


def create_app() -> FastAPI:
    config = auth_runtime_config()
    app = FastAPI(title="Tiny IPA", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def require_allowed_origin_for_unsafe_requests(request, call_next):
        try:
            current_config = auth_runtime_config()
        except AuthConfigurationError as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": {"error": "AUTH_CONFIG_INVALID", "detail": str(exc)}},
            )
        if not request_origin_is_allowed(
            current_config,
            method=request.method,
            origin=request.headers.get("origin"),
            referer=request.headers.get("referer"),
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": {
                        "error": "ORIGIN_FORBIDDEN",
                        "detail": "Unsafe requests require an allowed Origin or Referer.",
                    }
                },
            )
        return await call_next(request)

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(practice_router, prefix="/api")
    app.include_router(attempts_router, prefix="/api")
    app.include_router(progress_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")

    # Mount static audio directory for local dev. In production Nginx serves /audio/.
    audio_dir = os.getenv(
        "TINY_IPA_AUDIO_DIR",
        str(Path(__file__).resolve().parent.parent.parent / "audio"),
    )
    if os.path.isdir(audio_dir):
        app.mount("/audio", StaticFiles(directory=audio_dir), name="audio")
    return app


app = create_app()
