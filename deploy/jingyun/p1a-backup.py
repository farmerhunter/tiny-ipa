#!/usr/bin/env python3
"""Bounded SQLite backup and separate restore verification for Tiny IPA P1a."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_MAX_BYTES = 100 * 1024 * 1024
DEFAULT_RETENTION_LIMIT = 7
METADATA_RESERVE_BYTES = 64 * 1024
STORAGE_BUDGET_BYTES = 1024 * 1024 * 1024
MIN_FREE_BYTES = 512 * 1024 * 1024
ROLLING_POLICY = "fixed2-rolling2-v1"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class OperationError(RuntimeError):
    pass


def _path_without_symlinks(path: Path, label: str) -> Path:
    expanded = path.expanduser()
    if ".." in expanded.parts:
        raise OperationError(f"{label} must not contain parent traversal")
    absolute = expanded.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.exists() and current.is_symlink():
            raise OperationError(f"{label} contains a symlink: {current}")
    return absolute


def _existing_directory(path: str, label: str) -> Path:
    candidate = _path_without_symlinks(Path(path), label)
    if not candidate.is_dir():
        raise OperationError(f"{label} must be an existing directory")
    return candidate.resolve(strict=True)


def _child_file(path: str, root: Path, label: str, *, must_exist: bool) -> Path:
    candidate = _path_without_symlinks(Path(path), label).resolve(strict=must_exist)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise OperationError(f"{label} must be below its declared root") from exc
    if must_exist and not candidate.is_file():
        raise OperationError(f"{label} must be an existing regular file")
    if not must_exist and candidate.exists():
        raise OperationError(f"{label} must not already exist")
    return candidate


def _safe_id(value: str, label: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise OperationError(f"{label} is not a safe identifier")
    return value


@contextmanager
def _validated_wal_shm(path: str, source: Path):
    candidate = _path_without_symlinks(Path(path), "WAL coordination file")
    expected = Path(f"{source}-shm")
    if candidate != expected:
        raise OperationError("WAL coordination file must match the source database")
    try:
        candidate_stat = candidate.lstat()
    except FileNotFoundError as exc:
        raise OperationError("WAL coordination file must already exist") from exc
    if not stat.S_ISREG(candidate_stat.st_mode):
        raise OperationError("WAL coordination file must be a regular file")
    source_stat = source.stat()
    if (candidate_stat.st_uid, candidate_stat.st_gid) != (
        source_stat.st_uid,
        source_stat.st_gid,
    ):
        raise OperationError("WAL coordination file owner must match the source database")
    try:
        descriptor = os.open(candidate, os.O_RDWR | os.O_NOFOLLOW)
    except OSError as exc:
        raise OperationError("WAL coordination file must be writable") from exc
    try:
        opened_stat = os.fstat(descriptor)
        if (opened_stat.st_dev, opened_stat.st_ino) != (
            candidate_stat.st_dev,
            candidate_stat.st_ino,
        ):
            raise OperationError("WAL coordination file changed during validation")
        if not stat.S_ISREG(opened_stat.st_mode) or (
            opened_stat.st_uid,
            opened_stat.st_gid,
        ) != (source_stat.st_uid, source_stat.st_gid):
            raise OperationError("WAL coordination file changed during validation")
        yield
    finally:
        os.close(descriptor)


def _quoted_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _snapshot(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        quick_check = [row[0] for row in conn.execute("PRAGMA quick_check")]
        if quick_check != ["ok"]:
            raise OperationError("SQLite quick_check failed")
        schema_rows = list(
            conn.execute(
                "SELECT name, COALESCE(sql, '') FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        )
        schema_hash = hashlib.sha256(
            json.dumps(schema_rows, separators=(",", ":")).encode()
        ).hexdigest()
        table_counts = {
            name: conn.execute(
                f"SELECT COUNT(*) FROM {_quoted_identifier(name)}"
            ).fetchone()[0]
            for name, _ in schema_rows
        }
    finally:
        conn.close()
    return {"quick_check": "ok", "schema_sha256": schema_hash, "table_counts": table_counts}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_sqlite(source: Path, destination: Path, *, max_bytes: int | None = None) -> None:
    source_conn = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
    destination_conn = sqlite3.connect(destination)
    try:
        page_size = source_conn.execute("PRAGMA page_size").fetchone()[0]

        def enforce_limit(status: int, remaining: int, total: int) -> None:
            del status, remaining
            if max_bytes is not None and total * page_size + METADATA_RESERVE_BYTES > max_bytes:
                raise OperationError("backup grew beyond the approved size cap")

        source_conn.backup(destination_conn, pages=16, progress=enforce_limit)
    finally:
        destination_conn.close()
        source_conn.close()


def _database_bytes(path: Path) -> int:
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    finally:
        conn.close()
    return page_count * page_size


def _valid_snapshots(root: Path) -> list[Path]:
    valid = []
    for child in root.iterdir():
        manifest = child / "manifest.json"
        if (
            not child.is_symlink()
            and child.is_dir()
            and not manifest.is_symlink()
            and manifest.is_file()
        ):
            try:
                record = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if record.get("status") == "complete":
                valid.append(child)
    return valid


def _create_backup_artifact(
    *, source: str, state_root: str, destination_root: str, snapshot_id: str,
    release_id: str, max_bytes: int, retention_limit: int,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = _existing_directory(state_root, "state root")
    destination = _existing_directory(destination_root, "destination root")
    source_path = _child_file(source, state, "source database", must_exist=True)
    snapshot = _safe_id(snapshot_id, "snapshot id")
    release = _safe_id(release_id, "release id")
    if max_bytes <= 0 or max_bytes > DEFAULT_MAX_BYTES:
        raise OperationError("max bytes must be between 1 and 104857600")
    if len(_valid_snapshots(destination)) >= retention_limit:
        raise OperationError("retention cap reached; no snapshot was deleted")

    expected_bytes = _database_bytes(source_path)
    if expected_bytes + METADATA_RESERVE_BYTES > max_bytes:
        raise OperationError("source database cannot fit inside the approved size cap")
    if shutil.disk_usage(destination).free < expected_bytes + METADATA_RESERVE_BYTES:
        raise OperationError("destination does not have enough free space")

    final_dir = destination / snapshot
    incomplete_dir = destination / f".incomplete-{snapshot}"
    if final_dir.exists() or incomplete_dir.exists():
        raise OperationError("snapshot collision")
    incomplete_dir.mkdir(mode=0o700)
    backup = incomplete_dir / "tiny-ipa.sqlite.backup"
    try:
        if metadata:
            (incomplete_dir / "ROLLING").touch(mode=0o600)
        source_snapshot = _snapshot(source_path)
        _copy_sqlite(source_path, backup, max_bytes=max_bytes)
        size = backup.stat().st_size
        if size + METADATA_RESERVE_BYTES > max_bytes:
            raise OperationError("backup exceeds the approved size cap")
        backup_snapshot = _snapshot(backup)
        if backup_snapshot != source_snapshot:
            raise OperationError("backup verification differs from source")
        checksum = _sha256(backup)
        manifest = {
            "status": "complete",
            "snapshot_id": snapshot,
            "release_id": release,
            "source": str(source_path),
            "artifact": "tiny-ipa.sqlite.backup",
            "bytes": size,
            "sha256": checksum,
            "verification": backup_snapshot,
        }
        manifest.update(metadata or {})
        manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        if len(manifest_text.encode()) >= METADATA_RESERVE_BYTES:
            raise OperationError("backup manifest exceeds the reserved metadata cap")
        (incomplete_dir / "manifest.json").write_text(manifest_text, encoding="utf-8")
        if metadata:
            (incomplete_dir / "ROLLING").unlink()
        os.replace(incomplete_dir, final_dir)
        return manifest
    except Exception as exc:
        (incomplete_dir / "FAILED").write_text(type(exc).__name__ + "\n", encoding="utf-8")
        raise



@contextmanager
def _backup_lock(root: Path):
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OperationError("another backup operation holds the destination lock") from exc
        yield
    finally:
        os.close(descriptor)


def create_backup(
    *, source: str, state_root: str, destination_root: str, snapshot_id: str,
    release_id: str, max_bytes: int, retention_limit: int,
) -> dict[str, Any]:
    if retention_limit <= 0 or retention_limit > DEFAULT_RETENTION_LIMIT:
        raise OperationError("retention limit must be between 1 and 7")
    destination = _existing_directory(destination_root, "destination root")
    with _backup_lock(destination):
        return _create_backup_artifact(
            source=source, state_root=state_root, destination_root=destination_root,
            snapshot_id=snapshot_id, release_id=release_id, max_bytes=max_bytes,
            retention_limit=retention_limit,
        )


def _tree_bytes(root: Path) -> int:
    total = 0
    for child in root.iterdir():
        info = child.lstat()
        if stat.S_ISDIR(info.st_mode):
            total += info.st_size + _tree_bytes(child)
        elif stat.S_ISREG(info.st_mode):
            total += info.st_size
        else:
            raise OperationError("storage roots contain a symlink or special file")
    return total


def _bounded_storage(backups: Path, restores: Path, required: int) -> None:
    if backups == restores or backups in restores.parents or restores in backups.parents:
        raise OperationError("backup and restore roots must not overlap")
    if _tree_bytes(backups) + _tree_bytes(restores) + required > STORAGE_BUDGET_BYTES:
        raise OperationError("combined backup and restore storage budget exceeded")
    for root in (backups, restores):
        if shutil.disk_usage(root).free < MIN_FREE_BYTES + required:
            raise OperationError("storage must retain at least 512 MiB free after copying")


def _checked_snapshots(root: Path) -> dict[str, dict[str, Any]]:
    snapshots = {}
    for child in root.iterdir():
        if child.is_symlink() or not child.is_dir():
            raise OperationError("unknown object in backup root")
        if child.name.startswith(".incomplete-"):
            _safe_id(child.name[len(".incomplete-"):], "incomplete snapshot id")
            if (child / "ROLLING").exists() or (child / "manifest.json").exists():
                raise OperationError("incomplete rolling backup requires maintenance")
            continue
        _safe_id(child.name, "snapshot id")
        if {p.name for p in child.iterdir()} != {"manifest.json", "tiny-ipa.sqlite.backup"}:
            raise OperationError("unknown files in snapshot directory")
        manifest_path = _child_file(str(child / "manifest.json"), child,
                                    "manifest", must_exist=True)
        artifact = _child_file(str(child / "tiny-ipa.sqlite.backup"), child,
                               "backup artifact", must_exist=True)
        if manifest_path.stat().st_size >= METADATA_RESERVE_BYTES:
            raise OperationError("snapshot manifest exceeds metadata cap")
        try:
            record = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise OperationError("invalid snapshot manifest") from exc
        if not isinstance(record, dict) or (
            record.get("status") != "complete"
            or record.get("snapshot_id") != child.name
            or record.get("artifact") != artifact.name
            or record.get("bytes") != artifact.stat().st_size
            or record.get("sha256") != _sha256(artifact)
        ):
            raise OperationError("snapshot manifest or checksum mismatch")
        snapshots[child.name] = record
    return snapshots


def _managed_time(record: dict[str, Any]) -> datetime:
    if record.get("retention_policy") != ROLLING_POLICY:
        raise OperationError("unmanaged snapshot requires explicit migration cleanup")
    try:
        created = datetime.strptime(record["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
    except (KeyError, ValueError, TypeError) as exc:
        raise OperationError("invalid managed snapshot creation time") from exc
    return created.replace(tzinfo=timezone.utc)


def _remove_snapshot(root: Path, snapshot_id: str, expected: dict[str, Any]) -> None:
    current = _checked_snapshots(root)
    if current.get(snapshot_id) != expected:
        raise OperationError("snapshot changed before cleanup")
    directory = root / snapshot_id
    (directory / "tiny-ipa.sqlite.backup").unlink()
    (directory / "manifest.json").unlink()
    directory.rmdir()


def rolling_backup(
    *, source: str, state_root: str, destination_root: str, restore_root: str,
    snapshot_id: str, release_id: str, protected: list[str], bootstrap: bool = False,
) -> dict[str, Any]:
    state = _existing_directory(state_root, "state root")
    destination = _existing_directory(destination_root, "destination root")
    restores = _existing_directory(restore_root, "restore root")
    source_path = _child_file(source, state, "source database", must_exist=True)
    if destination == state or destination in state.parents or state in destination.parents:
        raise OperationError("backup root must be separate from state root")
    if state not in restores.parents or restores in source_path.parents:
        raise OperationError("restore root must be below state root and exclude the source")
    pins = {_safe_id(value, "protected snapshot id") for value in protected}
    if len(pins) != 2 or len(protected) != 2:
        raise OperationError("exactly two distinct protected snapshots are required")
    with _backup_lock(destination):
        records = _checked_snapshots(destination)
        if any(record.get("source") != str(source_path) for record in records.values()):
            raise OperationError("snapshot belongs to a different source database")
        if not pins <= records.keys():
            raise OperationError("a protected snapshot is missing")
        if bootstrap:
            if len(records) != 7 or any("retention_policy" in r for r in records.values()):
                raise OperationError("bootstrap requires exactly seven legacy snapshots")
        else:
            if len(records) > 4:
                raise OperationError("maintenance required before another rolling backup")
            for name, record in records.items():
                if name not in pins:
                    _managed_time(record)
        required = _database_bytes(source_path) + METADATA_RESERVE_BYTES
        if required > DEFAULT_MAX_BYTES:
            raise OperationError("source database cannot fit inside the approved size cap")
        # Reserve the copy cap, since the live database can grow after sizing.
        _bounded_storage(destination, restores, DEFAULT_MAX_BYTES * (2 if bootstrap else 1))
        created = datetime.now(timezone.utc)
        if not bootstrap and any(
            _managed_time(record) >= created
            for name, record in records.items() if name not in pins
        ):
            raise OperationError("clock has not advanced beyond existing rolling snapshots")
        report = _create_backup_artifact(
            source=source, state_root=state_root, destination_root=destination_root,
            snapshot_id=snapshot_id, release_id=release_id, max_bytes=DEFAULT_MAX_BYTES,
            retention_limit=8 if bootstrap else 5,
            metadata={"retention_policy": ROLLING_POLICY,
                      "created_at": created.strftime("%Y-%m-%dT%H:%M:%S.%fZ")},
        )
        _bounded_storage(destination, restores, 0)
        if bootstrap:
            return {**report, "cleanup": "disabled; independent restore and Human review required"}
        records = _checked_snapshots(destination)
        candidates = sorted(
            (name for name in records if name not in pins),
            key=lambda name: (_managed_time(records[name]), name),
        )
        deleted = []
        try:
            for name in candidates[:-2]:
                if name == snapshot_id:
                    raise OperationError("new snapshot must never be a cleanup target")
                _remove_snapshot(destination, name, records[name])
                deleted.append(name)
        except (OSError, OperationError) as exc:
            raise OperationError(
                "cleanup failed; new backup retained; maintenance required"
            ) from exc
        return {**report, "deleted_snapshots": deleted}


def _verify_restore_artifact(
    *, backup_file: str, backup_root: str, restore_root: str, trial_id: str,
    expected_sha256: str, bounded_storage: bool = False,
) -> dict[str, Any]:
    backups = _existing_directory(backup_root, "backup root")
    restores = _existing_directory(restore_root, "restore root")
    backup = _child_file(backup_file, backups, "backup file", must_exist=True)
    trial = _safe_id(trial_id, "trial id")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise OperationError("expected sha256 must be an explicit lowercase digest")
    if _sha256(backup) != expected_sha256:
        raise OperationError("backup checksum mismatch")
    if shutil.disk_usage(restores).free < backup.stat().st_size + METADATA_RESERVE_BYTES:
        raise OperationError("restore root does not have enough free space")
    if bounded_storage:
        if backup.stat().st_size + METADATA_RESERVE_BYTES > DEFAULT_MAX_BYTES:
            raise OperationError("restore source exceeds the approved size cap")
        _bounded_storage(backups, restores, DEFAULT_MAX_BYTES)
    trial_dir = restores / trial
    restore = trial_dir / "tiny-ipa.sqlite"
    if trial_dir.exists():
        raise OperationError("restore trial collision")
    trial_dir.mkdir(mode=0o700)
    _copy_sqlite(backup, restore, max_bytes=DEFAULT_MAX_BYTES if bounded_storage else None)
    backup_snapshot = _snapshot(backup)
    restore_snapshot = _snapshot(restore)
    if restore_snapshot != backup_snapshot:
        raise OperationError("restored database differs from backup")
    return {
        "status": "verified",
        "trial_id": trial,
        "restore": str(restore),
        "sha256": expected_sha256,
        "verification": restore_snapshot,
    }



def verify_restore(
    *, backup_file: str, backup_root: str, restore_root: str, trial_id: str,
    expected_sha256: str, bounded_storage: bool = False,
) -> dict[str, Any]:
    backups = _existing_directory(backup_root, "backup root")
    with _backup_lock(backups) if bounded_storage else nullcontext():
        return _verify_restore_artifact(
            backup_file=backup_file, backup_root=backup_root, restore_root=restore_root,
            trial_id=trial_id, expected_sha256=expected_sha256, bounded_storage=bounded_storage,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--source", required=True)
    backup.add_argument("--state-root", required=True)
    backup.add_argument("--destination-root", required=True)
    backup.add_argument("--snapshot-id", required=True)
    backup.add_argument("--release-id", required=True)
    backup.add_argument("--max-bytes", required=True, type=int)
    backup.add_argument("--retention-limit", required=True, type=int)
    backup.add_argument("--writable-wal-shm")
    for command in ("rolling-backup", "bootstrap-backup"):
        rolling = commands.add_parser(command)
        for option in ("source", "state-root", "destination-root", "restore-root",
                       "snapshot-id", "release-id"):
            rolling.add_argument(f"--{option}", required=True)
        rolling.add_argument("--protect", action="append", required=True)
        rolling.add_argument("--writable-wal-shm")
    restore = commands.add_parser("verify-restore")
    restore.add_argument("--backup-file", required=True)
    restore.add_argument("--backup-root", required=True)
    restore.add_argument("--restore-root", required=True)
    restore.add_argument("--trial-id", required=True)
    restore.add_argument("--expected-sha256", required=True)
    restore.add_argument("--bounded-storage", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in ("backup", "rolling-backup", "bootstrap-backup"):
            snapshot_id = args.snapshot_id
            if snapshot_id == "utc-now":
                snapshot_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            coordination = nullcontext()
            if args.writable_wal_shm is not None:
                state = _existing_directory(args.state_root, "state root")
                source = _child_file(
                    args.source, state, "source database", must_exist=True
                )
                coordination = _validated_wal_shm(args.writable_wal_shm, source)
            with coordination:
                common = dict(
                    source=args.source, state_root=args.state_root,
                    destination_root=args.destination_root, snapshot_id=snapshot_id,
                    release_id=args.release_id,
                )
                if args.command == "backup":
                    report = create_backup(**common, max_bytes=args.max_bytes,
                                           retention_limit=args.retention_limit)
                else:
                    report = rolling_backup(
                        **common, restore_root=args.restore_root, protected=args.protect,
                        bootstrap=args.command == "bootstrap-backup",
                    )
        else:
            report = verify_restore(
                backup_file=args.backup_file, backup_root=args.backup_root,
                restore_root=args.restore_root, trial_id=args.trial_id,
                expected_sha256=args.expected_sha256, bounded_storage=args.bounded_storage,
            )
    except (OperationError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
