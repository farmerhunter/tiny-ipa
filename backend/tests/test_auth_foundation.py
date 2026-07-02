from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.db import get_connection
from app.services.auth import (
    AuthBootstrapError,
    AuthSecretRequiredError,
    OwnerAlreadyExistsError,
    ProductionBootstrapDisabledError,
    bootstrap_local_dev_user,
    bootstrap_owner,
    hash_session_token,
    issue_auth_session,
    require_session_secret,
    resolve_auth_session,
    revoke_session,
    verify_password,
)
from app.services.db_schema import init_db, table_names
from app.services.db_store import count_owner_users, get_settings


@pytest.fixture(name="conn")
def conn_fixture(tmp_path: Path):
    db_path = str(tmp_path / "auth.sqlite")
    connection = get_connection(db_path)
    init_db(connection)
    yield connection
    connection.close()


class TestAuthSchema:
    def test_init_creates_user_and_session_tables(self, conn):
        names = table_names(conn)

        assert "users" in names
        assert "auth_sessions" in names

        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        session_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(auth_sessions)")
        }

        assert {
            "id",
            "username",
            "password_hash",
            "is_owner",
            "is_active",
            "created_at",
            "updated_at",
        }.issubset(user_columns)
        assert {
            "id",
            "user_id",
            "token_hash",
            "created_at",
            "last_seen_at",
            "expires_at",
            "revoked_at",
        }.issubset(session_columns)

    def test_schema_init_is_idempotent(self, conn):
        before = table_names(conn)
        init_db(conn)
        after = table_names(conn)

        assert before == after


class TestOwnerBootstrap:
    def test_owner_bootstrap_creates_one_owner_and_settings(self, conn):
        result = bootstrap_owner(
            conn,
            username="owner",
            password="correct horse battery staple",
            now=datetime(2026, 7, 2, tzinfo=timezone.utc),
        )

        assert result.created is True
        assert result.user.username == "owner"
        assert result.user.is_owner is True
        assert result.user.is_active is True
        assert result.user.password_hash != "correct horse battery staple"
        assert result.user.password_hash.startswith("$argon2")
        assert verify_password("correct horse battery staple", result.user.password_hash)
        assert not verify_password("wrong password", result.user.password_hash)
        assert count_owner_users(conn) == 1

        settings = get_settings(conn, result.user.id)
        assert settings is not None
        assert settings.primary_accent == "US"

    def test_owner_bootstrap_fails_closed_when_owner_exists(self, conn):
        bootstrap_owner(conn, username="owner", password="correct horse battery staple")

        with pytest.raises(OwnerAlreadyExistsError):
            bootstrap_owner(conn, username="second", password="another safe password")

    def test_owner_bootstrap_does_not_claim_default_user(self, conn):
        with pytest.raises(AuthBootstrapError):
            bootstrap_owner(conn, username="default", password="correct horse battery staple")


class TestLocalDevBootstrap:
    def test_local_dev_bootstrap_requires_explicit_enable(self, conn):
        with pytest.raises(AuthBootstrapError):
            bootstrap_local_dev_user(
                conn,
                username="local-dev",
                password="local dev password",
                enabled=False,
                environment="local",
            )

    def test_local_dev_bootstrap_refuses_deployed_mode(self, conn):
        with pytest.raises(ProductionBootstrapDisabledError):
            bootstrap_local_dev_user(
                conn,
                username="local-dev",
                password="local dev password",
                enabled=True,
                environment="production",
            )

    def test_local_dev_bootstrap_is_explicit_and_idempotent(self, conn):
        first = bootstrap_local_dev_user(
            conn,
            username="local-dev",
            password="local dev password",
            enabled=True,
            environment="development",
        )
        second = bootstrap_local_dev_user(
            conn,
            username="local-dev",
            password="local dev password",
            enabled=True,
            environment="development",
        )

        assert first.created is True
        assert second.created is False
        assert second.user.id == first.user.id
        assert first.user.is_owner is False
        assert verify_password("local dev password", first.user.password_hash)

    def test_deployed_secret_fails_closed_when_missing(self, monkeypatch):
        monkeypatch.delenv("TINY_IPA_SESSION_SECRET", raising=False)

        with pytest.raises(AuthSecretRequiredError):
            require_session_secret(environment="production")

    def test_local_secret_can_be_missing_without_enabling_prod_bypass(self, monkeypatch):
        monkeypatch.delenv("TINY_IPA_SESSION_SECRET", raising=False)

        assert require_session_secret(environment="local") is None


class TestSessionStorage:
    def test_session_storage_hashes_token_and_resolves_active_user(self, conn):
        owner = bootstrap_owner(conn, username="owner", password="correct horse battery staple")
        now = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)

        issued = issue_auth_session(
            conn,
            user_id=owner.user.id,
            now=now,
            ttl=timedelta(hours=1),
        )
        stored = conn.execute(
            "SELECT * FROM auth_sessions WHERE id = ?",
            (issued.session.id,),
        ).fetchone()

        assert stored["token_hash"] == hash_session_token(issued.token)
        assert stored["token_hash"] != issued.token
        assert len(stored["token_hash"]) == 64

        resolved = resolve_auth_session(
            conn,
            token=issued.token,
            now=now + timedelta(minutes=5),
        )

        assert resolved is not None
        assert resolved.user.id == owner.user.id
        assert resolved.session.last_seen_at == "2026-07-02T12:05:00+00:00"

    def test_session_resolution_rejects_expired_or_revoked_tokens(self, conn):
        owner = bootstrap_owner(conn, username="owner", password="correct horse battery staple")
        now = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
        issued = issue_auth_session(
            conn,
            user_id=owner.user.id,
            now=now,
            ttl=timedelta(minutes=10),
        )

        assert (
            resolve_auth_session(conn, token=issued.token, now=now + timedelta(minutes=11))
            is None
        )

        active = issue_auth_session(
            conn,
            user_id=owner.user.id,
            now=now,
            ttl=timedelta(hours=1),
        )
        revoke_session(conn, token=active.token, now=now + timedelta(minutes=1))

        assert (
            resolve_auth_session(conn, token=active.token, now=now + timedelta(minutes=2))
            is None
        )

    def test_session_issuance_requires_active_existing_user(self, conn):
        with pytest.raises(AuthBootstrapError):
            issue_auth_session(conn, user_id="missing-user")


class TestBootstrapCli:
    def test_local_dev_bootstrap_cli_smoke(self, tmp_path: Path):
        db_path = tmp_path / "cli.sqlite"
        script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_auth.py"

        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--db-url",
                str(db_path),
                "dev-user",
                "--enable-local-dev",
                "--environment",
                "development",
                "--username",
                "local-dev",
                "--password",
                "local dev password",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        assert payload["created"] is True
        assert payload["username"] == "local-dev"
        assert payload["is_owner"] is False

        conn = get_connection(str(db_path))
        try:
            row = conn.execute(
                "SELECT username, password_hash FROM users WHERE username = 'local-dev'"
            ).fetchone()
        finally:
            conn.close()

        assert row is not None
        assert row["password_hash"] != "local dev password"
