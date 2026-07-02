from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import get_connection
from app.models import User
from app.services.auth import hash_password
from app.services.db_store import create_user, get_user_by_id

OWNER_USERNAME = "owner"
OWNER_PASSWORD = "correct horse battery staple"


def bootstrap_owner_user(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        if get_user_by_id(conn, "default") is None:
            create_user(
                conn,
                User(
                    id="default",
                    username=OWNER_USERNAME,
                    password_hash=hash_password(OWNER_PASSWORD),
                    is_owner=True,
                    is_active=True,
                    created_at="2026-07-02T00:00:00+00:00",
                    updated_at="2026-07-02T00:00:00+00:00",
                ),
            )
        conn.commit()
    finally:
        conn.close()


def authenticated_client(client: TestClient) -> TestClient:
    resp = client.post(
        "/api/auth/login",
        json={"username": OWNER_USERNAME, "password": OWNER_PASSWORD},
    )
    assert resp.status_code == 200, resp.json()
    return client
