from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))
from offline_release_rehearsal import new_root, worker  # noqa: E402


def test_new_root_refuses_outside_existing_and_symlink_paths_before_writes(tmp_path):
    outside = ROOT / "must-not-be-created-rehearsal"
    with pytest.raises(ValueError, match="temporary root"):
        new_root(outside)
    assert not outside.exists()
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "sentinel").write_text("unchanged")
    with pytest.raises(ValueError, match="existing"):
        new_root(existing)
    assert (existing / "sentinel").read_text() == "unchanged"
    linked = tmp_path / "linked"
    linked.symlink_to(existing, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        new_root(linked / "child")
    assert not (existing / "child").exists()


def test_worker_refuses_collisions_and_external_runtime_before_loading(tmp_path):
    root = new_root(tmp_path / "run")
    (root / "runtime").symlink_to(ROOT, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        worker(root)
    assert not (root / "state").exists()
    collision = new_root(tmp_path / "collision")
    (collision / "state").mkdir()
    with pytest.raises(ValueError, match="already exist"):
        worker(collision)
    assert not (collision / "backups").exists()


def test_packaged_backend_runs_real_tag_backup_pair_restore_route(tmp_path):
    root = new_root(tmp_path / "packaged")
    archive = root / "source.tar"
    subprocess.run(
        ["git", "archive", "--format=tar", f"--output={archive}", "HEAD"], cwd=ROOT, check=True
    )
    runtime = root / "runtime"
    runtime.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(runtime, filter="data")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(SCRIPTS / "offline_release_rehearsal.py"),
            "--worker",
            str(root),
        ],
        cwd=runtime / "backend",
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "TINY_IPA_ENV": "development",
            "TINY_IPA_REQUIRE_PACKAGED_AUDIO": "false",
            "TINY_IPA_ENABLE_LISTENING_PREVIEW": "false",
            "TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH": "",
            "TINY_IPA_SESSION_SECRET": "local-synthetic-rehearsal-test",
        },
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    assert receipt["synthetic_only"]
    assert receipt["tag_patch_updated"] == 13
    assert receipt["stale_plan_refused"]
    assert receipt["non_tag_fields_and_learner_history_preserved"]
    assert receipt["deleted_snapshots"] == []
    assert receipt["policy"] == "fixed2-rolling2-v1"
    assert receipt["pair_changes"] == 4
    assert receipt["pair_feedback"]["status"] == "available"
    assert receipt["pending_items"] == 3
    assert receipt["listening_start_http_status"] == 404
    assert Path(receipt["package_runtime_path"]).is_relative_to(runtime)
    with pytest.raises(ValueError, match="already exist"):
        worker(root)
