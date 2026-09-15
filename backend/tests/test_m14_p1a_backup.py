from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy" / "jingyun" / "p1a-backup.py"
SPEC = importlib.util.spec_from_file_location("p1a_backup", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


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
    source = state / "tiny-ipa.sqlite"
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


def test_size_failure_remains_incomplete(tmp_path: Path) -> None:
    state, backups, _, source = _roots(tmp_path)
    with pytest.raises(MODULE.OperationError, match="size cap"):
        MODULE.create_backup(
            source=str(source), state_root=str(state), destination_root=str(backups),
            snapshot_id="too-large", release_id="release-1", max_bytes=1,
            retention_limit=7,
        )
    assert not (backups / "too-large").exists()
    assert (backups / ".incomplete-too-large" / "FAILED").is_file()
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
