from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy" / "jingyun" / "p1a-backup.py"
DEPLOYMENT_PLAN = ROOT / "docs" / "15-m14-jingyun-candidate-deployment-plan.md"
SPEC = importlib.util.spec_from_file_location("p1a_backup", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _initialise_from_document(state: Path, database: Path) -> subprocess.CompletedProcess[str]:
    plan = DEPLOYMENT_PLAN.read_text(encoding="utf-8")
    body = plan.split("# P1A_INIT_DB_PYTHON_BEGIN", 1)[1].split(
        "# P1A_INIT_DB_PYTHON_END", 1
    )[0].strip()
    return subprocess.run(
        [sys.executable, "-I", "-B", "-", str(ROOT / "backend"), str(state), str(database)],
        input=body,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _database(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            "CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT);"
            "INSERT INTO sample(value) VALUES ('synthetic');"
            "CREATE TABLE \"odd\"\"name\"(value TEXT);"
            "INSERT INTO \"odd\"\"name\" VALUES ('synthetic');"
        )
        conn.commit()
    finally:
        conn.close()


def _roots(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    state = tmp_path / "state"
    backups = tmp_path / "backups"
    restores = state / "restore-candidates"
    state.mkdir()
    backups.mkdir()
    restores.mkdir()
    source = state / "tiny ipa?#.sqlite"
    _database(source)
    return state, backups, restores, source


def _backup(tmp_path: Path, snapshot_id: str = "trial-1"):
    state, backups, restores, source = _roots(tmp_path)
    report = MODULE.create_backup(
        source=str(source), state_root=str(state), destination_root=str(backups),
        snapshot_id=snapshot_id, release_id="release-1", max_bytes=104857600,
        retention_limit=7,
    )
    return state, backups, restores, report


def test_online_backup_and_separate_restore_preserve_schema_and_content(tmp_path: Path) -> None:
    _, backups, restores, backup = _backup(tmp_path)
    artifact = backups / backup["snapshot_id"] / backup["artifact"]
    restored = MODULE.verify_restore(
        backup_file=str(artifact), backup_root=str(backups), restore_root=str(restores),
        trial_id="restore-1", expected_sha256=backup["sha256"],
    )
    assert backup["status"] == "complete"
    assert backup["verification"]["table_counts"] == {"odd\"name": 1, "sample": 1}
    assert restored["status"] == "verified"
    assert restored["verification"] == backup["verification"]
    assert Path(restored["restore"]) != artifact


def test_documented_first_install_initializes_backup_and_restore_source(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    backups = tmp_path / "backups"
    restores = state / "restore-candidates"
    state.mkdir()
    backups.mkdir()
    restores.mkdir()
    source = state / "tiny-ipa.sqlite"

    initialized = _initialise_from_document(state, source)
    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout) == {
        "auth_sessions": 0,
        "integrity": "ok",
        "mode": "600",
        "status": "initialized",
        "tables": 9,
        "users": 0,
    }
    with sqlite3.connect(source) as connection:
        expected_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        expected_counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in expected_tables
        }
    assert expected_tables == {
        "attempts",
        "auth_sessions",
        "daily_sessions",
        "phoneme_stats",
        "phonemes",
        "session_items",
        "settings",
        "users",
        "words",
    }
    assert set(expected_counts.values()) == {0}
    assert source.stat().st_mode & 0o777 == 0o600

    backup = MODULE.create_backup(
        source=str(source),
        state_root=str(state),
        destination_root=str(backups),
        snapshot_id="first-install",
        release_id="release-1",
        max_bytes=104857600,
        retention_limit=7,
    )
    artifact = backups / "first-install" / backup["artifact"]
    restored = MODULE.verify_restore(
        backup_file=str(artifact),
        backup_root=str(backups),
        restore_root=str(restores),
        trial_id="first-restore",
        expected_sha256=backup["sha256"],
    )
    assert backup["verification"]["table_counts"] == expected_counts
    assert restored["verification"]["table_counts"] == expected_counts
    assert set(restored["verification"]["table_counts"]) == expected_tables


def test_documented_first_install_refuses_database_and_namespace_collisions(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    database = state / "tiny-ipa.sqlite"
    database.write_bytes(b"existing")
    before = database.read_bytes()
    collision = _initialise_from_document(state, database)
    assert collision.returncode != 0
    assert database.read_bytes() == before

    database.unlink()
    outside = tmp_path / "outside.sqlite"
    outside.write_bytes(b"outside")
    database.symlink_to(outside)
    symlink = _initialise_from_document(state, database)
    assert symlink.returncode != 0
    assert database.is_symlink()
    assert outside.read_bytes() == b"outside"

    database.unlink()
    sidecar = Path(str(database) + "-wal")
    sidecar.write_bytes(b"existing-sidecar")
    sidecar_collision = _initialise_from_document(state, database)
    assert sidecar_collision.returncode != 0
    assert not database.exists()
    assert sidecar.read_bytes() == b"existing-sidecar"

    real_state = tmp_path / "real-state"
    real_state.mkdir()
    linked_state = tmp_path / "linked-state"
    linked_state.symlink_to(real_state, target_is_directory=True)
    linked_parent = _initialise_from_document(
        linked_state, linked_state / "tiny-ipa.sqlite"
    )
    assert linked_parent.returncode != 0
    assert not (real_state / "tiny-ipa.sqlite").exists()


def test_requires_explicit_cli_parameters() -> None:
    with pytest.raises(SystemExit):
        MODULE.build_parser().parse_args(["backup"])


@pytest.mark.parametrize("bad", ["../escape", "/absolute", "has space"])
def test_rejects_unsafe_snapshot_ids(tmp_path: Path, bad: str) -> None:
    state, backups, _, source = _roots(tmp_path)
    with pytest.raises(MODULE.OperationError, match="safe identifier"):
        MODULE.create_backup(
            source=str(source), state_root=str(state), destination_root=str(backups),
            snapshot_id=bad, release_id="release-1", max_bytes=104857600,
            retention_limit=7,
        )


def test_rejects_source_outside_declared_root(tmp_path: Path) -> None:
    state, backups, _, _ = _roots(tmp_path)
    outside = tmp_path / "outside.sqlite"
    _database(outside)
    with pytest.raises(MODULE.OperationError, match="below its declared root"):
        MODULE.create_backup(
            source=str(outside), state_root=str(state), destination_root=str(backups),
            snapshot_id="trial-1", release_id="release-1", max_bytes=104857600,
            retention_limit=7,
        )


def test_rejects_parent_traversal_for_backup_and_restore(tmp_path: Path) -> None:
    state, backups, restores, _ = _roots(tmp_path)
    outside = tmp_path / "outside.sqlite"
    _database(outside)
    with pytest.raises(MODULE.OperationError, match="parent traversal"):
        MODULE.create_backup(
            source=str(state / ".." / "outside.sqlite"), state_root=str(state),
            destination_root=str(backups), snapshot_id="trial-1",
            release_id="release-1", max_bytes=104857600, retention_limit=7,
        )
    with pytest.raises(MODULE.OperationError, match="parent traversal"):
        MODULE.verify_restore(
            backup_file=str(backups / ".." / "outside.sqlite"),
            backup_root=str(backups), restore_root=str(restores),
            trial_id="restore-1", expected_sha256="0" * 64,
        )


def test_rejects_symlink_source_and_snapshot_collision(tmp_path: Path) -> None:
    state, backups, _, source = _roots(tmp_path)
    link = state / "linked.sqlite"
    link.symlink_to(source)
    with pytest.raises(MODULE.OperationError, match="symlink"):
        MODULE.create_backup(
            source=str(link), state_root=str(state), destination_root=str(backups),
            snapshot_id="trial-1", release_id="release-1", max_bytes=104857600,
            retention_limit=7,
        )
    MODULE.create_backup(
        source=str(source), state_root=str(state), destination_root=str(backups),
        snapshot_id="trial-1", release_id="release-1", max_bytes=104857600,
        retention_limit=7,
    )
    with pytest.raises(MODULE.OperationError, match="collision"):
        MODULE.create_backup(
            source=str(source), state_root=str(state), destination_root=str(backups),
            snapshot_id="trial-1", release_id="release-1", max_bytes=104857600,
            retention_limit=7,
        )


def test_rejects_symlink_operation_roots(tmp_path: Path) -> None:
    state, backups, restores, source = _roots(tmp_path)
    backup_link = tmp_path / "backup-link"
    restore_link = tmp_path / "restore-link"
    backup_link.symlink_to(backups, target_is_directory=True)
    restore_link.symlink_to(restores, target_is_directory=True)
    with pytest.raises(MODULE.OperationError, match="symlink"):
        MODULE.create_backup(
            source=str(source), state_root=str(state),
            destination_root=str(backup_link), snapshot_id="trial-1",
            release_id="release-1", max_bytes=104857600, retention_limit=7,
        )
    with pytest.raises(MODULE.OperationError, match="symlink"):
        MODULE.verify_restore(
            backup_file=str(source), backup_root=str(state),
            restore_root=str(restore_link), trial_id="restore-1",
            expected_sha256=MODULE._sha256(source),
        )
def test_retention_cap_fails_without_deleting_snapshots(tmp_path: Path) -> None:
    state, backups, _, source = _roots(tmp_path)
    for index in range(2):
        MODULE.create_backup(
            source=str(source), state_root=str(state), destination_root=str(backups),
            snapshot_id=f"trial-{index}", release_id="release-1", max_bytes=104857600,
            retention_limit=2,
        )
    before = sorted(path.name for path in backups.iterdir())
    with pytest.raises(MODULE.OperationError, match="no snapshot was deleted"):
        MODULE.create_backup(
            source=str(source), state_root=str(state), destination_root=str(backups),
            snapshot_id="trial-2", release_id="release-1", max_bytes=104857600,
            retention_limit=2,
        )
    assert sorted(path.name for path in backups.iterdir()) == before


def test_external_manifest_symlink_does_not_count_as_snapshot(tmp_path: Path) -> None:
    _, backups, _, _ = _roots(tmp_path)
    outside = tmp_path / "manifest.json"
    outside.write_text('{"status":"complete"}')
    fake = backups / "fake"
    fake.mkdir()
    (fake / "manifest.json").symlink_to(outside)
    assert MODULE._valid_snapshots(backups) == []


def test_size_precheck_failure_writes_no_artifact(tmp_path: Path) -> None:
    state, backups, _, source = _roots(tmp_path)
    with pytest.raises(MODULE.OperationError, match="size cap"):
        MODULE.create_backup(
            source=str(source), state_root=str(state), destination_root=str(backups),
            snapshot_id="too-large", release_id="release-1", max_bytes=1,
            retention_limit=7,
        )
    assert not (backups / "too-large").exists()
    assert not (backups / ".incomplete-too-large").exists()
    assert MODULE._valid_snapshots(backups) == []


def test_low_free_space_fails_before_writing(tmp_path: Path, monkeypatch) -> None:
    state, backups, _, source = _roots(tmp_path)
    usage = MODULE.shutil._ntuple_diskusage(total=10, used=9, free=1)
    monkeypatch.setattr(MODULE.shutil, "disk_usage", lambda _: usage)
    with pytest.raises(MODULE.OperationError, match="enough free space"):
        MODULE.create_backup(
            source=str(source), state_root=str(state), destination_root=str(backups),
            snapshot_id="no-space", release_id="release-1", max_bytes=104857600,
            retention_limit=7,
        )
    assert list(backups.iterdir()) == []


def test_copy_growth_failure_stays_incomplete_and_bounded(
    tmp_path: Path, monkeypatch,
) -> None:
    state, backups, _, source = _roots(tmp_path)
    monkeypatch.setattr(MODULE, "_database_bytes", lambda _: 0)
    limit = MODULE.METADATA_RESERVE_BYTES + 1
    with pytest.raises(MODULE.OperationError, match="grew beyond"):
        MODULE.create_backup(
            source=str(source), state_root=str(state), destination_root=str(backups),
            snapshot_id="grew", release_id="release-1", max_bytes=limit,
            retention_limit=7,
        )
    incomplete = backups / ".incomplete-grew"
    assert (incomplete / "FAILED").is_file()
    assert sum(path.stat().st_size for path in incomplete.iterdir()) <= limit
    assert MODULE._valid_snapshots(backups) == []


def test_restore_rejects_checksum_mismatch_and_collision(tmp_path: Path) -> None:
    _, backups, restores, backup = _backup(tmp_path)
    artifact = backups / backup["snapshot_id"] / backup["artifact"]
    with pytest.raises(MODULE.OperationError, match="checksum mismatch"):
        MODULE.verify_restore(
            backup_file=str(artifact), backup_root=str(backups), restore_root=str(restores),
            trial_id="restore-1", expected_sha256="0" * 64,
        )
    MODULE.verify_restore(
        backup_file=str(artifact), backup_root=str(backups), restore_root=str(restores),
        trial_id="restore-1", expected_sha256=backup["sha256"],
    )
    with pytest.raises(MODULE.OperationError, match="collision"):
        MODULE.verify_restore(
            backup_file=str(artifact), backup_root=str(backups), restore_root=str(restores),
            trial_id="restore-1", expected_sha256=backup["sha256"],
        )


def test_candidate_units_are_bounded_and_nonpersistent() -> None:
    service = (ROOT / "deploy/jingyun/tiny-ipa-backup.service.candidate").read_text()
    timer = (ROOT / "deploy/jingyun/tiny-ipa-backup.timer.candidate").read_text()
    assert "User=tiny-ipa" in service
    assert "EnvironmentFile=" not in service
    assert "--release-id <APPROVED_RELEASE_ID>" in service
    assert "--max-bytes 104857600 --retention-limit 7" in service
    assert "ReadOnlyPaths=/var/lib/tiny-ipa" in service
    assert "ReadWritePaths=/var/backups/tiny-ipa" in service
    assert "OnCalendar=*-*-* 03:20:00 UTC" in timer
    assert "Persistent=false" in timer
    assert "RandomizedDelaySec" not in timer
