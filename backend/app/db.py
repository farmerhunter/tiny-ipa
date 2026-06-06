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

DEFAULT_DB_PATH = os.getenv(
    "TINY_IPA_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "tiny_ipa.sqlite"),
)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a sqlite3.Connection with WAL mode, foreign keys, and Row factory.

    Args:
        db_path: Path to the SQLite database file. Falls back to
                 ``TINY_IPA_DB_PATH`` env var or ``backend/tiny_ipa.sqlite``.
    """
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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
