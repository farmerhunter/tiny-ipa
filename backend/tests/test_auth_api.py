from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth_dependencies import AUTH_COOKIE_NAME, require_current_user
from app.db import get_connection
from app.main import app
from app.services.auth import bootstrap_owner, issue_auth_session
from app.services.db_schema import init_db


@pytest.fixture(name="auth_db")
def auth_db_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    db_path = str(tmp_path / "auth_api.sqlite")
    conn = get_connection(db_path)
    init_db(conn)
    bootstrap_owner(conn, username="owner", password="correct horse battery staple")
    conn.commit()
    conn.close()

    import app.db as db_mod

    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setenv("TINY_IPA_ENV", "local")
    monkeypatch.delenv("TINY_IPA_SESSION_SECRET", raising=False)
    return db_path


@pytest.fixture(name="client")
def client_fixture(auth_db: str) -> TestClient:
    return TestClient(app)


def test_login_sets_http_only_lax_session_cookie(client: TestClient):
    resp = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "correct horse battery staple"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is True
    assert data["user"]["username"] == "owner"
    assert data["user"]["is_owner"] is True
    assert "password" not in data["user"]

    cookie = resp.headers["set-cookie"]
    assert f"{AUTH_COOKIE_NAME}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Secure" not in cookie


def test_login_rejects_invalid_credentials(client: TestClient):
    resp = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "wrong password"},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "INVALID_CREDENTIALS"
    assert AUTH_COOKIE_NAME not in resp.cookies


def test_me_reports_anonymous_then_authenticated_user(client: TestClient):
    anon = client.get("/api/auth/me")
    assert anon.status_code == 200
    assert anon.json() == {"authenticated": False, "user": None}

    client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "correct horse battery staple"},
    )

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is True
    assert me.json()["user"]["username"] == "owner"


def test_logout_invalidates_session_and_clears_cookie(client: TestClient):
    client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "correct horse battery staple"},
    )

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"ok": True}
    assert f"{AUTH_COOKIE_NAME}=" in logout.headers["set-cookie"]
    assert "Max-Age=0" in logout.headers["set-cookie"]

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"authenticated": False, "user": None}


def test_me_treats_expired_session_as_anonymous(
    auth_db: str,
    client: TestClient,
):
    conn = get_connection(auth_db)
    user_id = conn.execute("SELECT id FROM users WHERE username = 'owner'").fetchone()["id"]
    issued = issue_auth_session(
        conn,
        user_id=user_id,
        now=datetime.now(timezone.utc) - timedelta(hours=2),
        ttl=timedelta(minutes=1),
    )
    conn.commit()
    conn.close()

    client.cookies.set(AUTH_COOKIE_NAME, issued.token)
    resp = client.get("/api/auth/me")

    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False, "user": None}


def test_current_user_dependency_returns_auth_required_when_anonymous(
    auth_db: str,
):
    protected = FastAPI()

    @protected.get("/protected")
    def protected_route(_user=Depends(require_current_user)):
        return {"ok": True}

    client = TestClient(protected)
    resp = client.get("/protected")

    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "AUTH_REQUIRED"


def test_current_user_dependency_resolves_authenticated_cookie(
    auth_db: str,
):
    protected = FastAPI()

    @protected.get("/protected")
    def protected_route(user=Depends(require_current_user)):
        return {"user_id": user.id, "username": user.username}

    conn = get_connection(auth_db)
    user_id = conn.execute("SELECT id FROM users WHERE username = 'owner'").fetchone()["id"]
    issued = issue_auth_session(conn, user_id=user_id)
    conn.commit()
    conn.close()

    client = TestClient(protected)
    client.cookies.set(AUTH_COOKIE_NAME, issued.token)
    resp = client.get("/protected")

    assert resp.status_code == 200
    assert resp.json() == {"user_id": user_id, "username": "owner"}


def test_production_auth_fails_closed_without_session_secret(
    auth_db: str,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TINY_IPA_ENV", "production")
    monkeypatch.delenv("TINY_IPA_SESSION_SECRET", raising=False)

    client = TestClient(app)
    resp = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "correct horse battery staple"},
    )

    assert resp.status_code == 500
    assert resp.json()["detail"]["error"] == "AUTH_CONFIG_INVALID"


def test_production_cookie_is_secure_when_secret_is_configured(
    auth_db: str,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("TINY_IPA_ENV", "production")
    monkeypatch.setenv("TINY_IPA_SESSION_SECRET", "test-only-secret")

    client = TestClient(app)
    resp = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "correct horse battery staple"},
    )

    assert resp.status_code == 200
    assert "Secure" in resp.headers["set-cookie"]
