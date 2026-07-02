"""Auth persistence foundation for M12.

This module intentionally stops short of FastAPI route behavior. It owns the
user/session storage primitives that later auth endpoints can call.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.models import AuthSession, Settings, User
from app.services.db_schema import init_db
from app.services.db_store import (
    count_owner_users,
    create_auth_session,
    create_user,
    get_auth_session_by_token_hash,
    get_user_by_id,
    get_user_by_username,
    revoke_auth_session_by_token_hash,
    touch_auth_session,
    upsert_settings,
)

SESSION_TOKEN_BYTES = 32
DEFAULT_SESSION_TTL_HOURS = 24 * 14
LOCAL_DEV_ENVIRONMENTS = {"", "local", "development", "dev", "test"}
DEPLOYED_ENVIRONMENTS = {"production", "prod", "deployed", "deploy"}
DEFAULT_LOCAL_DEV_USERNAME = "local-dev"

_PASSWORD_HASHER = PasswordHasher()


class AuthBootstrapError(ValueError):
    pass


class OwnerAlreadyExistsError(AuthBootstrapError):
    pass


class ProductionBootstrapDisabledError(AuthBootstrapError):
    pass


class AuthSecretRequiredError(AuthBootstrapError):
    pass


@dataclass(frozen=True)
class BootstrapResult:
    user: User
    created: bool


@dataclass(frozen=True)
class IssuedSession:
    token: str
    session: AuthSession


@dataclass(frozen=True)
class ResolvedSession:
    session: AuthSession
    user: User


@dataclass(frozen=True)
class AuthenticatedUser:
    user: User
    password_needs_rehash: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def hash_password(password: str) -> str:
    """Hash a password with Argon2 through argon2-cffi's high-level API."""
    _validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def password_hash_needs_rehash(password_hash: str) -> bool:
    return _PASSWORD_HASHER.check_needs_rehash(password_hash)


def authenticate_user(
    conn: sqlite3.Connection,
    *,
    username: str,
    password: str,
) -> Optional[AuthenticatedUser]:
    username = _normalize_username(username)
    user = get_user_by_username(conn, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return AuthenticatedUser(
        user=user,
        password_needs_rehash=password_hash_needs_rehash(user.password_hash),
    )


def bootstrap_owner(
    conn: sqlite3.Connection,
    *,
    username: str,
    password: str,
    now: Optional[datetime] = None,
) -> BootstrapResult:
    """Create the first owner account, failing closed if any owner exists."""
    init_db(conn)
    username = _normalize_username(username)
    if username == "default":
        raise AuthBootstrapError("default is reserved for explicit owner-claim work")
    if count_owner_users(conn) > 0:
        raise OwnerAlreadyExistsError("owner account already exists")
    if get_user_by_username(conn, username) is not None:
        raise AuthBootstrapError("username already exists")

    timestamp = _iso(now or _now())
    user = User(
        id=f"user_{uuid.uuid4().hex}",
        username=username,
        password_hash=hash_password(password),
        is_owner=True,
        is_active=True,
        created_at=timestamp,
        updated_at=timestamp,
    )
    create_user(conn, user)
    upsert_settings(conn, _default_settings(user.id, timestamp))
    return BootstrapResult(user=user, created=True)


def bootstrap_local_dev_user(
    conn: sqlite3.Connection,
    *,
    password: str,
    username: str = DEFAULT_LOCAL_DEV_USERNAME,
    enabled: bool,
    environment: Optional[str] = None,
    now: Optional[datetime] = None,
) -> BootstrapResult:
    """Create or return a local dev user only when explicitly enabled."""
    env = _normalize_environment(environment)
    if env in DEPLOYED_ENVIRONMENTS:
        raise ProductionBootstrapDisabledError("local dev bootstrap is disabled in deployed mode")
    if not enabled:
        raise AuthBootstrapError("local dev bootstrap requires an explicit enable flag")

    init_db(conn)
    username = _normalize_username(username)
    existing = get_user_by_username(conn, username)
    if existing is not None:
        return BootstrapResult(user=existing, created=False)

    timestamp = _iso(now or _now())
    user = User(
        id=f"user_{uuid.uuid4().hex}",
        username=username,
        password_hash=hash_password(password),
        is_owner=False,
        is_active=True,
        created_at=timestamp,
        updated_at=timestamp,
    )
    create_user(conn, user)
    upsert_settings(conn, _default_settings(user.id, timestamp))
    return BootstrapResult(user=user, created=True)


def require_session_secret(
    *,
    environment: Optional[str] = None,
    session_secret: Optional[str] = None,
) -> Optional[str]:
    """Fail closed for deployed auth when the session secret is missing."""
    env = _normalize_environment(environment)
    secret = session_secret if session_secret is not None else os.getenv("TINY_IPA_SESSION_SECRET")
    if env in DEPLOYED_ENVIRONMENTS and not secret:
        raise AuthSecretRequiredError("TINY_IPA_SESSION_SECRET is required in deployed mode")
    return secret


def issue_auth_session(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    now: Optional[datetime] = None,
    ttl: Optional[timedelta] = None,
) -> IssuedSession:
    init_db(conn)
    user = get_user_by_id(conn, user_id)
    if user is None or not user.is_active:
        raise AuthBootstrapError("active user is required for session issuance")

    issued_at = now or _now()
    expires_at = issued_at + (ttl or timedelta(hours=DEFAULT_SESSION_TTL_HOURS))
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    session = AuthSession(
        id=f"sess_{uuid.uuid4().hex}",
        user_id=user.id,
        token_hash=hash_session_token(token),
        created_at=_iso(issued_at),
        last_seen_at=_iso(issued_at),
        expires_at=_iso(expires_at),
        revoked_at=None,
    )
    create_auth_session(conn, session)
    return IssuedSession(token=token, session=session)


def resolve_auth_session(
    conn: sqlite3.Connection,
    *,
    token: str,
    now: Optional[datetime] = None,
    touch: bool = True,
) -> Optional[ResolvedSession]:
    if not token:
        return None
    session = get_auth_session_by_token_hash(conn, hash_session_token(token))
    if session is None or session.revoked_at is not None:
        return None
    if _parse_iso(session.expires_at) <= (now or _now()):
        return None
    user = get_user_by_id(conn, session.user_id)
    if user is None or not user.is_active:
        return None
    if touch:
        last_seen_at = _iso(now or _now())
        touch_auth_session(conn, session.id, last_seen_at)
        session = AuthSession(
            id=session.id,
            user_id=session.user_id,
            token_hash=session.token_hash,
            created_at=session.created_at,
            last_seen_at=last_seen_at,
            expires_at=session.expires_at,
            revoked_at=session.revoked_at,
        )
    return ResolvedSession(session=session, user=user)


def revoke_session(conn: sqlite3.Connection, *, token: str, now: Optional[datetime] = None) -> None:
    if not token:
        return
    revoke_auth_session_by_token_hash(conn, hash_session_token(token), _iso(now or _now()))


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_username(username: str) -> str:
    normalized = username.strip()
    if not normalized:
        raise AuthBootstrapError("username is required")
    return normalized


def _normalize_environment(environment: Optional[str]) -> str:
    raw = environment if environment is not None else os.getenv("TINY_IPA_ENV", "local")
    return raw.strip().lower()


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise AuthBootstrapError("password must be at least 8 characters")


def _default_settings(user_id: str, timestamp: str) -> Settings:
    return Settings(
        user_id=user_id,
        primary_accent="US",
        daily_word_count=10,
        show_translation=True,
        show_accent_compare=False,
        practice_mode="ipa_first",
        review_strength="normal",
        updated_at=timestamp,
    )
