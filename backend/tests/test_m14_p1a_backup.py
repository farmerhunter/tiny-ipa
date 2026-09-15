from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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
    assert service.count("TimeoutStartSec=30s") == 1
    assert service.count("TimeoutStopSec=10s") == 1
    assert "TimeoutStartSec=infinity" not in service
    assert "ReadOnlyPaths=/var/lib/tiny-ipa" in service
    assert "ReadWritePaths=/var/backups/tiny-ipa" in service
    assert "--writable-wal-shm /var/lib/tiny-ipa/tiny-ipa.sqlite-shm" in service
    assert "/opt/tiny-ipa/ops/<APPROVED_TOOL_REVISION>/p1a-backup.py" in service
    assert "/opt/tiny-ipa/current/deploy/jingyun/p1a-backup.py" not in service
    assert "ReadWritePaths=/var/lib/tiny-ipa/tiny-ipa.sqlite-shm" in service
    assert "ReadWritePaths=/var/lib/tiny-ipa\n" not in service
    assert "ReadWritePaths=-/var/lib/tiny-ipa/tiny-ipa.sqlite-shm" not in service
    assert "ConditionPathIsReadWrite=/var/lib/tiny-ipa/tiny-ipa.sqlite-shm" not in service
    assert "OnCalendar=*-*-* 03:20:00 UTC" in timer
    assert "Persistent=false" in timer
    assert "RandomizedDelaySec" not in timer


def test_wal_coordination_file_is_validated_in_backup_entrypoint(tmp_path: Path) -> None:
    state, backups, _, source = _roots(tmp_path)
    connection = sqlite3.connect(source)
    try:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        connection.execute("INSERT INTO sample(value) VALUES ('live-writer')")
        connection.commit()
        shm = Path(f"{source}-shm")
        assert shm.is_file()
        result = MODULE.main([
            "backup", "--source", str(source), "--state-root", str(state),
            "--destination-root", str(backups), "--snapshot-id", "with-shm",
            "--release-id", "release-1", "--max-bytes", "104857600",
            "--retention-limit", "7", "--writable-wal-shm", str(shm),
        ])
    finally:
        connection.close()
    assert result == 0
    report = json.loads((backups / "with-shm" / "manifest.json").read_text())
    assert report["status"] == "complete"
    assert report["verification"]["table_counts"]["sample"] == 2


@pytest.mark.parametrize("unexpected_type", ["missing", "directory", "symlink"])
def test_wal_coordination_file_fails_before_backup_artifact(
    tmp_path: Path, unexpected_type: str,
) -> None:
    state, backups, _, source = _roots(tmp_path)
    shm = Path(f"{source}-shm")
    if unexpected_type == "directory":
        shm.mkdir()
    elif unexpected_type == "symlink":
        target = state / "outside-shm"
        target.write_bytes(b"")
        shm.symlink_to(target)
    result = MODULE.main([
        "backup", "--source", str(source), "--state-root", str(state),
        "--destination-root", str(backups), "--snapshot-id", "invalid-shm",
        "--release-id", "release-1", "--max-bytes", "104857600",
        "--retention-limit", "7", "--writable-wal-shm", str(shm),
    ])
    assert result == 2
    assert list(backups.iterdir()) == []


def test_wal_coordination_file_rejects_different_owner(
    tmp_path: Path, monkeypatch,
) -> None:
    state, backups, _, source = _roots(tmp_path)
    connection = sqlite3.connect(source)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("INSERT INTO sample(value) VALUES ('owner-check')")
        connection.commit()
        shm = Path(f"{source}-shm")
        actual_lstat = Path.lstat

        def mismatched_owner(path: Path):
            result = actual_lstat(path)
            if path == shm:
                return SimpleNamespace(
                    st_mode=result.st_mode, st_uid=result.st_uid + 1,
                    st_gid=result.st_gid, st_dev=result.st_dev, st_ino=result.st_ino,
                )
            return result

        monkeypatch.setattr(Path, "lstat", mismatched_owner)
        with pytest.raises(MODULE.OperationError, match="owner must match"):
            with MODULE._validated_wal_shm(str(shm), source):
                MODULE.create_backup(
                    source=str(source), state_root=str(state),
                    destination_root=str(backups), snapshot_id="owner-mismatch",
                    release_id="release-1", max_bytes=104857600,
                    retention_limit=7,
                )
    finally:
        connection.close()
    assert list(backups.iterdir()) == []


def test_h2_records_bounded_steps_and_filters_unit_failure_summary() -> None:
    plan = (ROOT / "docs/15-m14-jingyun-candidate-deployment-plan.md").read_text()
    required = (
        'printf \'{"r2_step":"%s","rc":%s}\\n\'',
        "r2_run start-backup /usr/bin/timeout 60s",
        "r2_finish backup-result",
        "r2_finish timer-active",
        "r2_finish timer-disabled",
        '"r2_unit_summary":"unavailable"',
        '"r2_unit_summary": values',
        "--property=ExecMainStatus",
        "--property=InvocationID",
        "tool-source-sha",
        "unit-template-source-sha",
        "tool-dir-absent",
        "verify-tool-sha",
        "verify-unit-template-sha",
        "ops-root-metadata",
        "tool-install-metadata",
        "direct-backup",
        "direct-restore",
    )
    for value in required:
        assert value in plan
    assert "journalctl" not in plan
    assert "/opt/tiny-ipa/current/deploy/jingyun/tiny-ipa-backup.service.candidate" not in plan
    assert plan.index("tool-dir-absent") < plan.index("start-backup")
    assert plan.index("verify-unit-template-sha") < plan.index("start-backup")
    assert plan.index("install-tool") < plan.index("direct-backup")
    assert plan.index("direct-restore") < plan.index("start-backup")


@pytest.mark.parametrize(
    "failure", ["missing", "hash-mismatch", "collision", "success"]
)
def test_h2_tool_materialization_fixture(
    tmp_path: Path, failure: str,
) -> None:
    plan = DEPLOYMENT_PLAN.read_text()
    block = plan.split("```sh\nset -u\nrelease_id=", 1)[1].split("\n```", 1)[0]
    block = "set -u\nrelease_id=" + block
    revision = "a" * 40
    stage = tmp_path / "stage"
    ops = tmp_path / "ops"
    stage.mkdir()
    tool = stage / f"p1a-backup-{revision}.py"
    unit = stage / f"tiny-ipa-backup-{revision}.service.candidate"
    if failure != "missing":
        tool.write_text("tool\n")
        unit.write_text("<APPROVED_TOOL_REVISION>\n")
    tool_sha = hashlib.sha256(tool.read_bytes()).hexdigest() if tool.exists() else "0" * 64
    unit_sha = hashlib.sha256(unit.read_bytes()).hexdigest() if unit.exists() else "0" * 64
    if failure == "hash-mismatch":
        tool_sha = "f" * 64
    target = ops / revision
    if failure == "collision":
        target.mkdir(parents=True)
        (target / "sentinel").write_text("preserve\n")
    replacements = {
        "<APPROVED_RELEASE_ID>": "release-1",
        "<APPROVED_TOOL_REVISION>": revision,
        "<APPROVED_TOOL_SHA256>": tool_sha,
        "<APPROVED_UNIT_TEMPLATE_SHA256>": unit_sha,
        "<UNIQUE_UTC_SNAPSHOT_ID>": "snapshot-1",
        "<UNIQUE_RESTORE_ID>": "restore-1",
        "/tmp/tiny-ipa-p1a": str(stage),
        "/opt/tiny-ipa/ops": str(ops),
        "/usr/bin/sha256sum": shutil.which("sha256sum") or "sha256sum",
        "(0, 0)": f"({os.getuid()}, {os.getgid()})",
        "sudo -n install -d -o root -g root -m": "install -d -m",
        "sudo -n install -o root -g root -m": "install -m",
        "sudo -n chmod": "chmod",
        "sudo -n /usr/bin/python3": "/usr/bin/python3",
        "sudo -n test": "test",
    }
    for old, new in replacements.items():
        block = block.replace(old, new)
    block = re.sub(
        r"r2_summary\(\) \{.*?\n\}\nr2_finish",
        "r2_summary() { :; }\nr2_finish",
        block,
        flags=re.DOTALL,
    )
    block = block.split("# P1A_TOOL_MATERIALIZATION_END", 1)[0]
    completed = subprocess.run(
        ["/bin/bash"], input=block, text=True, capture_output=True, timeout=10,
    )
    if failure == "success":
        assert completed.returncode == 0, completed.stderr
        assert (target / "p1a-backup.py").read_text() == "tool\n"
        assert (target / "tiny-ipa-backup.service.candidate").read_text() == (
            "<APPROVED_TOOL_REVISION>\n"
        )
        assert target.stat().st_mode & 0o777 == 0o555
        assert (target / "p1a-backup.py").stat().st_mode & 0o777 == 0o555
        assert (
            target / "tiny-ipa-backup.service.candidate"
        ).stat().st_mode & 0o777 == 0o444
    elif failure == "collision":
        assert completed.returncode != 0
        assert '"r2_step":"tool-dir-absent","rc":1' in completed.stdout
        assert (target / "sentinel").read_text() == "preserve\n"
        assert sorted(path.name for path in target.iterdir()) == ["sentinel"]
    else:
        assert completed.returncode != 0
        expected_step = "tool-source-type" if failure == "missing" else "tool-source-sha"
        assert f'"r2_step":"{expected_step}","rc":1' in completed.stdout
        assert not target.exists()


def test_h2_unit_summary_executes_and_rejects_extra_fields() -> None:
    plan = DEPLOYMENT_PLAN.read_text()
    parser = plan.split("# P1A_R2_SUMMARY_PYTHON_BEGIN", 1)[1].split(
        "# P1A_R2_SUMMARY_PYTHON_END", 1
    )[0].strip()
    valid = "\n".join(
        (
            "ActiveState=failed",
            "SubState=failed",
            "Result=timeout",
            "ExecMainCode=1",
            "ExecMainStatus=15",
            "NRestarts=0",
            f"InvocationID={'a' * 32}",
        )
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", parser],
        input=valid,
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["r2_unit_summary"]["Result"] == "timeout"

    secret = "SECRET_MUST_NOT_LEAK"
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", parser],
        input=f"{valid}\nEnvironment={secret}\n",
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == '{"r2_unit_summary":"invalid"}'
    assert secret not in result.stdout
