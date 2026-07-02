"""FastAPI auth dependency helpers for M12."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Cookie, HTTPException

from app.db import get_db
from app.models import User
from app.services.auth import (
    DEPLOYED_ENVIRONMENTS,
    AuthSecretRequiredError,
    ResolvedSession,
    require_session_secret,
    resolve_auth_session,
)

AUTH_COOKIE_NAME = "tiny_ipa_session"
AUTH_COOKIE_PATH = "/"
AUTH_COOKIE_SAMESITE = "lax"


def is_deployed_environment() -> bool:
    return os.getenv("TINY_IPA_ENV", "local").strip().lower() in DEPLOYED_ENVIRONMENTS


def auth_cookie_secure() -> bool:
    return is_deployed_environment()


def auth_error(error: str, detail: str, *, status_code: int = 401) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": error, "detail": detail},
    )


def ensure_auth_configured() -> None:
    try:
        require_session_secret()
    except AuthSecretRequiredError as exc:
        raise auth_error(
            "AUTH_CONFIG_INVALID",
            str(exc),
            status_code=500,
        ) from exc


def resolve_current_session(token: Optional[str]) -> Optional[ResolvedSession]:
    ensure_auth_configured()
    if not token:
        return None
    with get_db() as conn:
        return resolve_auth_session(conn, token=token)


def get_optional_current_user(
    tiny_ipa_session: Optional[str] = Cookie(default=None, alias=AUTH_COOKIE_NAME),
) -> Optional[User]:
    resolved = resolve_current_session(tiny_ipa_session)
    return resolved.user if resolved is not None else None


def require_current_user(
    tiny_ipa_session: Optional[str] = Cookie(default=None, alias=AUTH_COOKIE_NAME),
) -> User:
    resolved = resolve_current_session(tiny_ipa_session)
    if resolved is None:
        raise auth_error("AUTH_REQUIRED", "Sign in required.")
    return resolved.user
