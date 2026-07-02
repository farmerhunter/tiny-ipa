"""Auth endpoints for M12 minimal personal-VPS sessions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.auth_dependencies import (
    AUTH_COOKIE_NAME,
    AUTH_COOKIE_PATH,
    AUTH_COOKIE_SAMESITE,
    auth_cookie_secure,
    auth_error,
    ensure_auth_configured,
    get_optional_current_user,
)
from app.db import get_db
from app.models import User
from app.services.auth import authenticate_user, issue_auth_session, revoke_session

router = APIRouter(prefix="/auth")


def _public_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "is_owner": user.is_owner,
    }


@router.post("/login")
async def login(request: Request, response: Response):
    ensure_auth_configured()
    body = await request.json()
    username = body.get("username")
    password = body.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        raise auth_error("INVALID_CREDENTIALS", "Invalid username or password.")

    with get_db() as conn:
        authenticated = authenticate_user(conn, username=username, password=password)
        if authenticated is None:
            raise auth_error("INVALID_CREDENTIALS", "Invalid username or password.")
        issued = issue_auth_session(conn, user_id=authenticated.user.id)

    response.set_cookie(
        AUTH_COOKIE_NAME,
        issued.token,
        httponly=True,
        secure=auth_cookie_secure(),
        samesite=AUTH_COOKIE_SAMESITE,
        path=AUTH_COOKIE_PATH,
    )
    return {
        "authenticated": True,
        "user": _public_user(authenticated.user),
    }


@router.post("/logout")
def logout(request: Request, response: Response):
    ensure_auth_configured()
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        with get_db() as conn:
            revoke_session(conn, token=token)
    response.delete_cookie(
        AUTH_COOKIE_NAME,
        path=AUTH_COOKIE_PATH,
        secure=auth_cookie_secure(),
        httponly=True,
        samesite=AUTH_COOKIE_SAMESITE,
    )
    return {"ok": True}


@router.get("/me")
def me(current_user: User | None = Depends(get_optional_current_user)):
    if current_user is None:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": _public_user(current_user)}
