#!/usr/bin/env python3
"""Dry-run report for future default-user owner claim."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.db import DEFAULT_DB_PATH  # noqa: E402

DEFAULT_USER_ID = "default"


def _db_path(raw: str) -> str:
    if raw.startswith("sqlite:///"):
        return raw[len("sqlite:///"):]
    return raw


def _read_only_connection(db_path: str) -> sqlite3.Connection:
    path = Path(db_path).expanduser().resolve()
    uri = f"file:{quote(str(path), safe='/:')}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _count(
    conn: sqlite3.Connection,
    table: str,
    where: str = "",
    params: tuple[Any, ...] = (),
) -> int:
    if not _has_table(conn, table):
        return 0
    sql = f"SELECT COUNT(*) AS cnt FROM {table}"
    if where:
        sql += f" WHERE {where}"
    row = conn.execute(sql, params).fetchone()
    return int(row["cnt"]) if row else 0


def _group_count(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
) -> dict[str, int]:
    return {
        str(row["key"]): int(row["cnt"])
        for row in conn.execute(sql, params).fetchall()
    }


def build_default_owner_claim_report(
    conn: sqlite3.Connection,
    *,
    db_path: str,
    default_user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    daily_sessions_by_status: dict[str, int] = {}
    daily_sessions_by_group_type: dict[str, int] = {}
    session_items_by_session_status: dict[str, int] = {}
    session_items_by_group_type: dict[str, int] = {}

    if _has_table(conn, "daily_sessions"):
        daily_sessions_by_status = _group_count(
            conn,
            """
            SELECT status AS key, COUNT(*) AS cnt
            FROM daily_sessions
            WHERE user_id = ?
            GROUP BY status
            ORDER BY status
            """,
            (default_user_id,),
        )
        daily_sessions_by_group_type = _group_count(
            conn,
            """
            SELECT group_type AS key, COUNT(*) AS cnt
            FROM daily_sessions
            WHERE user_id = ?
            GROUP BY group_type
            ORDER BY group_type
            """,
            (default_user_id,),
        )

    if _has_table(conn, "session_items") and _has_table(conn, "daily_sessions"):
        session_items_by_session_status = _group_count(
            conn,
            """
            SELECT daily_sessions.status AS key, COUNT(session_items.id) AS cnt
            FROM session_items
            JOIN daily_sessions ON daily_sessions.id = session_items.session_id
            WHERE daily_sessions.user_id = ?
            GROUP BY daily_sessions.status
            ORDER BY daily_sessions.status
            """,
            (default_user_id,),
        )
        session_items_by_group_type = _group_count(
            conn,
            """
            SELECT daily_sessions.group_type AS key, COUNT(session_items.id) AS cnt
            FROM session_items
            JOIN daily_sessions ON daily_sessions.id = session_items.session_id
            WHERE daily_sessions.user_id = ?
            GROUP BY daily_sessions.group_type
            ORDER BY daily_sessions.group_type
            """,
            (default_user_id,),
        )

    attempts_on_default_session_items = (
        _count(
            conn,
            "attempts",
            """
            session_item_id IN (
                SELECT session_items.id
                FROM session_items
                JOIN daily_sessions ON daily_sessions.id = session_items.session_id
                WHERE daily_sessions.user_id = ?
            )
            """,
            (default_user_id,),
        )
        if _has_table(conn, "attempts")
        and _has_table(conn, "session_items")
        and _has_table(conn, "daily_sessions")
        else 0
    )

    return {
        "dry_run": True,
        "mutation_authorized": False,
        "apply_mode_available": False,
        "db_path": db_path,
        "default_user_id": default_user_id,
        "row_counts": {
            "users_default": _count(conn, "users", "id = ?", (default_user_id,)),
            "settings_default": _count(conn, "settings", "user_id = ?", (default_user_id,)),
            "daily_sessions_default": _count(
                conn,
                "daily_sessions",
                "user_id = ?",
                (default_user_id,),
            ),
            "session_items_owned_by_default_sessions": sum(
                session_items_by_session_status.values(),
            ),
            "attempts_default_user": _count(conn, "attempts", "user_id = ?", (default_user_id,)),
            "attempts_on_default_session_items": attempts_on_default_session_items,
            "phoneme_stats_default": _count(
                conn,
                "phoneme_stats",
                "user_id = ?",
                (default_user_id,),
            ),
            "auth_sessions_default": _count(
                conn,
                "auth_sessions",
                "user_id = ?",
                (default_user_id,),
            ),
        },
        "breakdown": {
            "daily_sessions_by_status": daily_sessions_by_status,
            "daily_sessions_by_group_type": daily_sessions_by_group_type,
            "session_items_by_session_status": session_items_by_session_status,
            "session_items_by_group_type": session_items_by_group_type,
        },
        "backup_guidance": [
            "Stop the Tiny IPA backend before any future real owner-claim apply operation.",
            (
                "Copy the SQLite database file and any sibling -wal and -shm files "
                "to a timestamped backup path."
            ),
            (
                "Run this dry-run report against the backup and the source database; "
                "compare row counts before applying any future migration."
            ),
            (
                "Keep the backup until login, settings, Today, Progress, attempts, "
                "and review/focus flows are verified for the claimed owner."
            ),
        ],
        "owner_claim_strategy": {
            "temp_db_safe_sequence": [
                "Create or choose the target owner user in a temp database.",
                "Verify the dry-run row counts for default-owned runtime data.",
                (
                    "In a future Human-gated apply mode only, update default runtime "
                    "owner fields to the target user id in one transaction."
                ),
                "Re-run auth/isolation and real-backend walkthroughs against the temp database.",
            ],
            "future_real_apply_requires_human_decision_contract": True,
            "no_real_db_mutation_in_this_tool": True,
        },
    }


def default_owner_claim(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report default-user runtime rows for future owner-claim planning.",
    )
    parser.add_argument(
        "--db-url",
        default=DEFAULT_DB_PATH,
        help="SQLite database path or sqlite:/// URI.",
    )
    parser.add_argument(
        "--default-user-id",
        default=DEFAULT_USER_ID,
        help="Legacy user id to inspect; defaults to 'default'.",
    )
    args = parser.parse_args(argv)

    db_path = _db_path(args.db_url)
    with _read_only_connection(db_path) as conn:
        report = build_default_owner_claim_report(
            conn,
            db_path=db_path,
            default_user_id=args.default_user_id,
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(default_owner_claim())
