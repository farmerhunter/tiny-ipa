#!/usr/bin/env python3
"""Create and verify a temporary-only SQLite backup/restore dry run.

Every path must be below the operating system temporary directory. This tool is
deliberately unsuitable for production databases and never restores in place.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterable, Optional, Union

REQUIRED_TABLES = (
    "users",
    "auth_sessions",
    "words",
    "phonemes",
    "settings",
    "daily_sessions",
    "session_items",
    "attempts",
    "phoneme_stats",
)


class DryRunPathError(ValueError):
    """Raised when a path could escape the temporary-only dry-run boundary."""


class BackupVerificationError(RuntimeError):
    """Raised when SQLite integrity or runtime-data verification fails."""


def _temp_root() -> Path:
    return Path(tempfile.gettempdir()).resolve()


def _resolved_temp_path(path: Union[str, Path], *, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    try:
        resolved.relative_to(_temp_root())
    except ValueError as exc:
        raise DryRunPathError(f"{label} must be under the system temporary directory") from exc
    return resolved


def _require_source(path: Union[str, Path]) -> Path:
    source = _resolved_temp_path(path, label="source database")
    if not source.is_file():
        raise DryRunPathError("source database must be an existing temporary SQLite file")
    return source


def _require_new_target(path: Union[str, Path], *, label: str) -> Path:
    target = _resolved_temp_path(path, label=label)
    if not target.parent.is_dir():
        raise DryRunPathError(f"{label} parent directory must already exist")
    if target.exists():
        raise DryRunPathError(f"{label} must not already exist")
    return target


def _readonly_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _table_fingerprint(conn: sqlite3.Connection, table: str) -> str:
    digest = hashlib.sha256()
    for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
        digest.update(repr(tuple(row)).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _schema_fingerprint(conn: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for name, sql in conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        digest.update(name.encode("utf-8"))
        digest.update(b"\n")
        digest.update((sql or "").encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def snapshot_database(path: Union[str, Path]) -> dict[str, Any]:
    """Return integrity and non-secret comparison data for a temporary database."""
    database = _resolved_temp_path(path, label="database")
    conn = _readonly_connection(database)
    try:
        quick_check = [row[0] for row in conn.execute("PRAGMA quick_check")]
        if quick_check != ["ok"]:
            raise BackupVerificationError("SQLite quick_check failed")

        missing_tables = set(REQUIRED_TABLES) - _table_names(conn)
        if missing_tables:
            missing = ", ".join(sorted(missing_tables))
            raise BackupVerificationError(f"required tables are missing: {missing}")

        tables = {
            table: {
                "count": conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
                "fingerprint": _table_fingerprint(conn, table),
            }
            for table in REQUIRED_TABLES
        }
        schema_fingerprint = _schema_fingerprint(conn)
    finally:
        conn.close()

    return {
        "quick_check": quick_check,
        "schema_fingerprint": schema_fingerprint,
        "tables": tables,
    }


def _copy_database(source: Path, target: Path) -> None:
    source_conn = _readonly_connection(source)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()


def run_backup_restore_dry_run(
    source_path: Union[str, Path],
    backup_path: Union[str, Path],
    restore_path: Union[str, Path],
) -> dict[str, Any]:
    """Copy a temporary SQLite fixture to backup and separate restore targets."""
    source = _require_source(source_path)
    backup = _require_new_target(backup_path, label="backup artifact")
    restore = _require_new_target(restore_path, label="restore target")

    if len({source, backup, restore}) != 3:
        raise DryRunPathError("source, backup artifact, and restore target must differ")

    source_snapshot = snapshot_database(source)
    _copy_database(source, backup)
    backup_snapshot = snapshot_database(backup)
    _copy_database(backup, restore)
    restore_snapshot = snapshot_database(restore)

    if source_snapshot != backup_snapshot or source_snapshot != restore_snapshot:
        raise BackupVerificationError("backup or restore snapshot differs from source")

    return {
        "temporary_only": True,
        "source": str(source),
        "backup": str(backup),
        "restore": str(restore),
        "verification": source_snapshot,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Existing temporary SQLite fixture")
    parser.add_argument("--backup", required=True, help="New temporary backup artifact")
    parser.add_argument("--restore", required=True, help="New temporary restored SQLite file")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_backup_restore_dry_run(args.source, args.backup, args.restore)
    except (DryRunPathError, BackupVerificationError) as exc:
        print(f"dry-run failed: {exc}")
        return 2

    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
