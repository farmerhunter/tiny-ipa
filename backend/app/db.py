"""Database connection helper.

Uses stdlib sqlite3. No ORM — models are plain dataclasses and repositories
write their own queries. Connection details come from environment variables
with sensible local-development defaults.

The module-level `get_connection` is the primary entry point. Callers should
use it as a context manager or close the returned connection explicitly.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional
from urllib.parse import quote

DEFAULT_DB_PATH = os.getenv(
    "TINY_IPA_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "tiny_ipa.sqlite"),
)


def _configure_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a sqlite3.Connection with WAL mode, foreign keys, and Row factory.

    Args:
        db_path: Path to the SQLite database file. Falls back to
                 ``TINY_IPA_DB_PATH`` env var or ``backend/tiny_ipa.sqlite``.
    """
    path = db_path or DEFAULT_DB_PATH
    return _configure_connection(sqlite3.connect(path, timeout=10.0))


def wal_anchor_enabled() -> bool:
    value = os.getenv("TINY_IPA_KEEP_WAL_ANCHOR", "false").strip().lower()
    if value not in {"true", "false"}:
        raise ValueError("TINY_IPA_KEEP_WAL_ANCHOR must be true or false")
    return value == "true"


@contextmanager
def keep_wal_anchor(
    db_path: Optional[str] = None,
) -> Generator[sqlite3.Connection, None, None]:
    path = str(Path(db_path or DEFAULT_DB_PATH).resolve())
    uri = f"file:{quote(path, safe='/')}?mode=rw"
    conn = _configure_connection(sqlite3.connect(uri, uri=True, timeout=10.0))
    try:
        conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
        if conn.in_transaction:
            raise RuntimeError("WAL anchor must not keep a transaction open")
        yield conn
    finally:
        conn.close()


@contextmanager
def get_db(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context-managed database connection (auto-commit / close)."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
