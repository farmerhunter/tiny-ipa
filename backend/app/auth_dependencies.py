"""FastAPI auth dependency helpers for M12."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

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
_LOCAL_DEV_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5182",
    "http://localhost:5182",
)
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuthConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthRuntimeConfig:
    deployed: bool
    allowed_origins: tuple[str, ...]
    cookie_secure: bool
    cookie_samesite: str


def is_deployed_environment() -> bool:
    return os.getenv("TINY_IPA_ENV", "local").strip().lower() in DEPLOYED_ENVIRONMENTS


def auth_cookie_secure() -> bool:
    return auth_runtime_config().cookie_secure


def auth_cookie_samesite() -> str:
    return auth_runtime_config().cookie_samesite


def auth_runtime_config() -> AuthRuntimeConfig:
    deployed = is_deployed_environment()
    allowed_origins = _configured_origins(deployed=deployed)
    cookie_secure = _cookie_secure(deployed=deployed)
    cookie_samesite = _cookie_samesite(deployed=deployed)

    if deployed:
        try:
            require_session_secret()
        except AuthSecretRequiredError as exc:
            raise AuthConfigurationError(str(exc)) from exc

    return AuthRuntimeConfig(
        deployed=deployed,
        allowed_origins=allowed_origins,
        cookie_secure=cookie_secure,
        cookie_samesite=cookie_samesite,
    )


def request_origin_is_allowed(
    config: AuthRuntimeConfig,
    *,
    method: str,
    origin: Optional[str],
    referer: Optional[str],
) -> bool:
    if not config.deployed or method.upper() not in _UNSAFE_METHODS:
        return True
    if origin:
        return origin in config.allowed_origins
    if referer:
        return _referer_origin(referer) in config.allowed_origins
    return False


def auth_error(error: str, detail: str, *, status_code: int = 401) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": error, "detail": detail},
    )


def ensure_auth_configured() -> None:
    try:
        auth_runtime_config()
    except AuthConfigurationError as exc:
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


def _configured_origins(*, deployed: bool) -> tuple[str, ...]:
    raw = os.getenv("TINY_IPA_ALLOWED_ORIGINS")
    if raw is not None:
        origins = tuple(
            dict.fromkeys(origin.strip() for origin in raw.split(",") if origin.strip())
        )
    elif deployed:
        raise AuthConfigurationError("TINY_IPA_ALLOWED_ORIGINS is required in deployed mode")
    else:
        legacy = os.getenv("TINY_IPA_CORS_ORIGINS")
        origins = tuple(
            dict.fromkeys(origin.strip() for origin in legacy.split(",") if origin.strip())
        ) if legacy else _LOCAL_DEV_ORIGINS

    if not origins:
        raise AuthConfigurationError("at least one allowed origin is required")
    if deployed:
        for origin in origins:
            if not _is_exact_https_origin(origin):
                raise AuthConfigurationError(
                    "TINY_IPA_ALLOWED_ORIGINS must contain exact HTTPS origins in deployed mode"
                )
    return origins


def _cookie_secure(*, deployed: bool) -> bool:
    raw = os.getenv("TINY_IPA_COOKIE_SECURE")
    if raw is None:
        return deployed
    enabled = raw.strip().lower() == "true"
    if deployed and not enabled:
        raise AuthConfigurationError("TINY_IPA_COOKIE_SECURE must be true in deployed mode")
    return enabled


def _cookie_samesite(*, deployed: bool) -> str:
    value = os.getenv("TINY_IPA_COOKIE_SAMESITE", "lax").strip().lower()
    if value not in {"lax", "strict", "none"}:
        raise AuthConfigurationError("TINY_IPA_COOKIE_SAMESITE must be lax, strict, or none")
    if deployed and value == "none":
        raise AuthConfigurationError(
            "TINY_IPA_COOKIE_SAMESITE must be lax or strict in deployed mode"
        )
    return value


def _is_exact_https_origin(origin: str) -> bool:
    parsed = urlsplit(origin)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and not parsed.username
        and not parsed.password
        and parsed.path == ""
        and not parsed.query
        and not parsed.fragment
    )


def _referer_origin(referer: str) -> str:
    parsed = urlsplit(referer)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"
