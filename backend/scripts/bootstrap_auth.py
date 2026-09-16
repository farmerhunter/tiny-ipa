#!/usr/bin/env python3
"""Bootstrap Tiny IPA auth users for owner setup or local development."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.db import DEFAULT_DB_PATH, get_db  # noqa: E402
from app.services.auth import (  # noqa: E402
    DEFAULT_LOCAL_DEV_USERNAME,
    AuthBootstrapError,
    bootstrap_local_dev_user,
    bootstrap_owner,
)


def _db_path(raw: str) -> str:
    if raw.startswith("sqlite:///"):
        return raw[len("sqlite:///"):]
    return raw


def _password(args: argparse.Namespace) -> str:
    if args.password is not None:
        return args.password
    value = sys.stdin.read(4097)
    if len(value) > 4096:
        raise AuthBootstrapError("password stdin exceeds 4096 characters")
    if value.endswith("\n"):
        value = value[:-1]
        if value.endswith("\r"):
            value = value[:-1]
    if not value or "\n" in value or "\r" in value or "\x00" in value:
        raise AuthBootstrapError("password stdin must contain exactly one non-empty line")
    return value


def bootstrap_auth(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Tiny IPA auth users.")
    parser.add_argument(
        "--db-url",
        default=DEFAULT_DB_PATH,
        help="SQLite database path or sqlite:/// URI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    owner = subparsers.add_parser("owner", help="Create the first owner user.")
    owner.add_argument("--username", required=True)
    owner_password = owner.add_mutually_exclusive_group(required=True)
    owner_password.add_argument("--password")
    owner_password.add_argument("--password-stdin", action="store_true")

    dev = subparsers.add_parser("dev-user", help="Create an explicit local dev user.")
    dev.add_argument("--username", default=DEFAULT_LOCAL_DEV_USERNAME)
    dev_password = dev.add_mutually_exclusive_group(required=True)
    dev_password.add_argument("--password")
    dev_password.add_argument("--password-stdin", action="store_true")
    dev.add_argument(
        "--enable-local-dev",
        action="store_true",
        help="Required guard: local dev bootstrap is never implicit.",
    )
    dev.add_argument(
        "--environment",
        default=None,
        help="Runtime environment guard; production/prod/deployed refuse dev bootstrap.",
    )

    args = parser.parse_args(argv)

    try:
        password = _password(args)
        with get_db(_db_path(args.db_url)) as conn:
            if args.command == "owner":
                result = bootstrap_owner(
                    conn,
                    username=args.username,
                    password=password,
                )
            else:
                result = bootstrap_local_dev_user(
                    conn,
                    username=args.username,
                    password=password,
                    enabled=args.enable_local_dev,
                    environment=args.environment,
                )
        print(json.dumps({
            "created": result.created,
            "user_id": result.user.id,
            "username": result.user.username,
            "is_owner": result.user.is_owner,
        }))
        return 0
    except AuthBootstrapError as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(bootstrap_auth())
