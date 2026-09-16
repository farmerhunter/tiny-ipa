from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.db import get_connection
from app.services.db_schema import init_db

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from backup_restore_dry_run import (  # noqa: E402
    DryRunPathError,
    run_backup_restore_dry_run,
)


def _fixture_database(path: Path) -> None:
    conn = get_connection(str(path))
    try:
        init_db(conn)
        conn.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "fixture-user",
                "fixture-owner",
                "fixture-password-hash",
                1,
                1,
                "created",
                "updated",
            ),
        )
        conn.execute(
            "INSERT INTO auth_sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "fixture-session",
                "fixture-user",
                "fixture-token-hash",
                "created",
                "seen",
                "expires",
                None,
            ),
        )
        conn.execute(
            "INSERT INTO words VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "ship",
                "ship",
                "entry",
                "/ʃɪp/",
                None,
                '["/ʃ/"]',
                None,
                "船",
                "/audio/us/ship.mp3",
                None,
                "[]",
                None,
                "core_selected",
            ),
        )
        conn.execute(
            "INSERT INTO phonemes VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("/ʃ/", "/ʃ/", "both", "consonant", 1, "ship", "卷舌"),
        )
        conn.execute(
            "INSERT INTO settings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "fixture-user",
                "US",
                1,
                1,
                0,
                "ipa_first",
                "normal",
                "entry",
                "zh-CN",
                '["/ʃ/"]',
                "updated",
            ),
        )
        conn.execute(
            "INSERT INTO daily_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "fixture-group",
                "fixture-user",
                "2026-07-14",
                "US",
                "completed",
                "created",
                "completed",
                1,
                "normal",
                "entry",
                "[]",
                "normal_next",
                None,
                "[]",
            ),
        )
        conn.execute(
            "INSERT INTO session_items VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("fixture-item", "fixture-group", "ship", 0, '["/ʃ/"]', "choose_ipa", "completed"),
        )
        conn.execute(
            "INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "fixture-attempt",
                "fixture-user",
                "fixture-item",
                "ship",
                "US",
                "choose_ipa",
                "/ʃ/",
                "/ʃɪp/",
                "/ʃɪp/",
                1,
                "created",
            ),
        )
        conn.execute(
            "INSERT INTO phoneme_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("fixture-user", "US", "/ʃ/", 1, 1, "created", None, "learning"),
        )
        conn.commit()
    finally:
        conn.close()


def test_temp_backup_restore_round_trip_preserves_runtime_and_shared_data(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite"
    _fixture_database(source)

    report = run_backup_restore_dry_run(
        source,
        tmp_path / "backup.sqlite",
        tmp_path / "restored.sqlite",
    )

    assert report["temporary_only"] is True
    assert report["verification"]["quick_check"] == ["ok"]
    assert report["verification"]["schema_fingerprint"]
    assert report["verification"]["tables"]["users"]["count"] == 1
    assert report["verification"]["tables"]["auth_sessions"]["count"] == 1
    assert report["verification"]["tables"]["settings"]["count"] == 1
    assert report["verification"]["tables"]["daily_sessions"]["count"] == 1
    assert report["verification"]["tables"]["session_items"]["count"] == 1
    assert report["verification"]["tables"]["attempts"]["count"] == 1
    assert report["verification"]["tables"]["phoneme_stats"]["count"] == 1
    assert report["verification"]["tables"]["words"]["count"] == 1
    assert report["verification"]["tables"]["phonemes"]["count"] == 1


def test_dry_run_rejects_repo_database_path_before_reading_it(tmp_path: Path) -> None:
    repo_database = Path(__file__).resolve().parents[1] / "tiny_ipa.sqlite"

    with pytest.raises(DryRunPathError, match="system temporary directory"):
        run_backup_restore_dry_run(
            repo_database,
            tmp_path / "backup.sqlite",
            tmp_path / "restored.sqlite",
        )


def test_dry_run_rejects_existing_restore_target(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite"
    restore = tmp_path / "restored.sqlite"
    _fixture_database(source)
    restore.touch()

    with pytest.raises(DryRunPathError, match="restore target must not already exist"):
        run_backup_restore_dry_run(source, tmp_path / "backup.sqlite", restore)


def test_cli_runs_a_temporary_only_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite"
    _fixture_database(source)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "backup_restore_dry_run.py"),
            "--source",
            str(source),
            "--backup",
            str(tmp_path / "backup.sqlite"),
            "--restore",
            str(tmp_path / "restored.sqlite"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["temporary_only"] is True
