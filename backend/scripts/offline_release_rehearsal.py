#!/usr/bin/env python3
"""Rehearse a source revision in a new retained temporary root without host access."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINS = ["20260916T095935Z", "20260917T010641Z"]


def tree_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())


def new_root(path: Path) -> Path:
    temporary = Path(tempfile.gettempdir()).resolve()
    if ".." in path.parts or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError("rehearsal path must not contain symlinks or traversal")
    resolved = path.absolute().resolve()
    if temporary not in resolved.parents or not resolved.parent.is_dir():
        raise ValueError("rehearsal root must be new and under the system temporary root")
    if resolved.exists():
        raise ValueError("refusing an existing rehearsal root")
    resolved.mkdir(mode=0o700)
    (resolved / ".tiny-ipa-offline-rehearsal").write_text("synthetic-only/v1\n")
    return resolved


def run(command: list[str], *, cwd: Path, env: dict | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"local command failed: {command[0]}\n{result.stderr[-2500:]}")
    return result.stdout


def rehearse(revision: str, output_root: Path, *, repo: Path = ROOT) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("source revision must be an exact full commit")
    if run(["git", "rev-parse", f"{revision}^{{commit}}"], cwd=repo).strip() != revision:
        raise ValueError("source commit differs")
    root = new_root(output_root)
    archive, release = root / "source.tar", root / "release"
    subprocess.run(
        ["git", "archive", "--format=tar", f"--output={archive}", revision], cwd=repo, check=True
    )
    release.mkdir()
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            if (
                member.issym()
                or member.islnk()
                or not (member.isfile() or member.isdir())
                or release.resolve() not in (release / member.name).resolve().parents
            ):
                raise ValueError("unsafe package archive entry")
        bundle.extractall(release, filter="data")
    required = [
        "backend/app/main.py",
        "backend/app/services/sound_compare.py",
        "backend/pyproject.toml",
        "backend/uv.lock",
        "frontend/package.json",
        "frontend/pnpm-lock.yaml",
        "content/sound_compare_pairs_candidate.json",
        "deploy/jingyun/p1a-backup.py",
    ]
    for name in required:
        if not (release / name).is_file():
            raise ValueError(f"required package input missing: {name}")
    unpacked_bytes = tree_bytes(release)
    env = {
        **os.environ,
        "UV_OFFLINE": "true",
        "npm_config_offline": "true",
        "VITE_API_BASE": "/api",
    }
    frontend = release / "frontend"
    run(["pnpm", "install", "--offline", "--frozen-lockfile"], cwd=frontend, env=env)
    run(["pnpm", "build"], cwd=frontend, env=env)
    assets = re.findall(r'(?:src|href)="([^"]+)"', (frontend / "dist/index.html").read_text())
    if not assets or any(not (frontend / "dist" / asset.lstrip("/")).is_file() for asset in assets):
        raise ValueError("built frontend references an omitted asset")
    fixture_spec = importlib.util.spec_from_file_location(
        "rehearsal_media_fixture", release / "frontend/tests/e2e/support/prepare_core100_real_db.py"
    )
    fixture_module = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture_module)
    media_manifest = release / "deploy/jingyun/core100-content-audio.manifest.json"
    media_cache = root / "media-cache"
    fixture_module.seed_audio_cache(
        release / "frontend/tests/fixtures/core100-media.zip",
        json.loads(media_manifest.read_text()),
        media_cache,
    )
    media = fixture_module.prepare(
        media_manifest,
        release,
        release / "audio/core100-package",
        media_cache,
    )
    (release / "REVISION").write_text(revision + "\n")
    runtime_archive = root / "candidate-release.tar"
    runtime = root / "runtime"
    runtime.mkdir()
    with tarfile.open(runtime_archive, "w") as bundle:
        for name in [
            "REVISION",
            "backend/app",
            "backend/scripts",
            "backend/pyproject.toml",
            "backend/uv.lock",
            "frontend/dist",
            "frontend/package.json",
            "frontend/pnpm-lock.yaml",
            "content",
            "audio",
            "deploy/jingyun",
        ]:
            bundle.add(
                release / name,
                arcname=name,
                filter=lambda item: (
                    None
                    if "__pycache__" in Path(item.name).parts or item.name.endswith(".pyc")
                    else item
                ),
            )
    with tarfile.open(runtime_archive) as bundle:
        bundle.extractall(runtime, filter="data")
    env.update(
        TINY_IPA_ENV="development",
        TINY_IPA_ENABLE_LISTENING_PREVIEW="false",
        TINY_IPA_SESSION_SECRET="local-rehearsal-synthetic-only",
        TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH="",
        TINY_IPA_AUDIO_DIR=str(runtime / "audio/core100-package"),
        TINY_IPA_REQUIRE_PACKAGED_AUDIO="false",
    )
    stdout = run(
        [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--worker", str(root)],
        cwd=runtime / "backend",
        env=env,
    )
    fixture = json.loads(stdout.strip().splitlines()[-1])
    report = {
        "status": "offline-rehearsal-verified",
        "temporary_only": True,
        "source_revision": revision,
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "root": str(root),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "package": {
            "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "archive_bytes": archive.stat().st_size,
            "unpacked_source_bytes": unpacked_bytes,
            "runtime_archive_bytes": runtime_archive.stat().st_size,
            "runtime_archive_sha256": hashlib.sha256(runtime_archive.read_bytes()).hexdigest(),
            "runtime_unpacked_bytes": tree_bytes(runtime),
            "media_count": media["audio_count"],
            "media_activation": "asset integrity only; no ordinary fixture audio-field changes",
            "frontend_dist_bytes": tree_bytes(frontend / "dist"),
            "local_node_modules_bytes": tree_bytes(frontend / "node_modules"),
            "evidence_asset": "content/sound_compare_pairs_candidate.json",
            "default_evidence_binding": "unset",
            "backend_dependencies": (
                "existing local Python environment; no wheel bundle or Linux installation proof"
            ),
            "frontend_assets_resolve": True,
        },
        "fixture": fixture,
        "space": {
            "per_copy_cap_bytes": 100 * 1024 * 1024,
            "backup_restore_budget_bytes": 1024**3,
            "required_remaining_bytes": 512 * 1024 * 1024,
            "measured_new_release_bytes": tree_bytes(runtime),
            "retained_build_workspace_bytes": tree_bytes(release),
            "media_cache_bytes": tree_bytes(media_cache),
            "candidate_runtime_peak_bytes": tree_bytes(runtime)
            + runtime_archive.stat().st_size
            + fixture["source_bytes"] * 2,
            "host_peak_formula": (
                "old release + new release + staging archive/cache + "
                "one new backup + independent restore + growth reserve"
            ),
            "host_old_release_bytes": None,
            "host_free_bytes": None,
        },
        "online_effects": {
            "authority": "proposal only; exact current host identities and Human approval required",
            "code": (
                "separate versioned staging and release switch; "
                "retain old release; no schema migration"
            ),
            "tags": (
                "separate fresh reviewed Core100 tag plan; no blanket reimport; skip if corrected"
            ),
            "pairs": (
                "HOLD pending separate activation approval; "
                "evidence env binding separately explicit"
            ),
            "listening": "HOLD; remain disabled",
            "deletion": "none",
            "rollback": (
                "code pointer only after old binary/data compatibility; "
                "DB restore separately decided because newer learner writes can be lost"
            ),
            "unknown_host_facts": [
                "active release and data",
                "free space",
                "installed backup policy/tool",
                "fixed recovery point identities",
                "Linux dependency cache",
            ],
        },
    }
    (root / "receipt.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def worker(root: Path) -> dict:
    if sys.flags.optimize:
        raise ValueError("verification requires Python assertions enabled")
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError("worker path must not contain symlinks")
    root = root.resolve(strict=True)
    if (root / ".tiny-ipa-offline-rehearsal").is_symlink():
        raise ValueError("worker marker must not be a symlink")
    if any((root / name).exists() for name in ("state", "backups")):
        raise ValueError("worker fixture directories must not already exist")
    if (root / "runtime").is_symlink() or any(
        p.is_symlink() for p in (root / "runtime").rglob("*")
    ):
        raise ValueError("worker runtime must not contain symlinks")
    if (
        Path(tempfile.gettempdir()).resolve() not in root.parents
        or (root / ".tiny-ipa-offline-rehearsal").read_text() != "synthetic-only/v1\n"
    ):
        raise ValueError("worker requires its newly marked temporary root")
    release = root / "runtime"
    sys.path[:0] = [str(release / "backend"), str(release / "backend/scripts")]
    from backup_restore_dry_run import run_backup_restore_dry_run, snapshot_database
    from correct_core100_tags import apply as apply_tags
    from correct_core100_tags import load_corrections
    from correct_core100_tags import plan as plan_tags
    from fastapi.testclient import TestClient
    from import_words import import_words
    from prepare_sound_compare import load_pairs

    import app
    import app.db as db_mod
    from app.db import get_connection
    from app.models import User
    from app.services.auth import hash_password
    from app.services.db_store import create_user

    if release not in Path(app.__file__).resolve().parents:
        raise ValueError("runtime borrowed code outside the package")
    state, backups = root / "state", root / "backups"
    state.mkdir()
    backups.mkdir()
    restores = state / "restore-candidates"
    restores.mkdir()
    source = state / "tiny-ipa.sqlite"
    imported = import_words(
        release / "content/core_100_words.json", release / "content/phonemes.json", str(source)
    )
    if not imported["committed"] or imported["errors"]:
        raise ValueError("fixture import failed")
    db_mod.DEFAULT_DB_PATH = str(source)
    os.environ["TINY_IPA_DB_PATH"] = str(source)
    with get_connection(str(source)) as conn:
        create_user(
            conn,
            User(
                "default",
                "rehearsal-owner",
                hash_password("synthetic-rehearsal-only"),
                True,
                True,
                "fixture",
                "fixture",
            ),
        )
        conn.execute(
            "UPDATE settings SET daily_word_count=4, practice_mode='choose_ipa', "
            "ui_language='en-US' WHERE user_id='default'"
        )
        conn.commit()
    from app.main import app as runtime

    client = TestClient(runtime)
    assert client.get("/api/health").status_code == 200
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "rehearsal-owner", "password": "synthetic-rehearsal-only"},
        ).status_code
        == 200
    )
    group = client.post("/api/practice/next-normal").json()
    item = group["items"][0]
    assert client.post(
        "/api/attempt",
        json={"session_item_id": item["session_item_id"], "selected_answer": item["display_ipa"]},
    ).json()["is_correct"]
    assert client.get("/api/listening/current").json() == {"enabled": False, "lesson": None}
    assert client.post("/api/listening/lessons").status_code == 404
    before = snapshot_database(source)
    assert before["tables"]["attempts"]["count"] == 1
    with get_connection(str(source)) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            conn.execute("SELECT count(*) FROM session_items WHERE status='pending'").fetchone()[0]
            == 3
        )
    spec = importlib.util.spec_from_file_location(
        "rehearsal_backup", release / "deploy/jingyun/p1a-backup.py"
    )
    backup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backup)
    common = {
        "source": str(source),
        "state_root": str(state),
        "destination_root": str(backups),
        "release_id": "synthetic-rehearsal",
    }
    for pin in PINS:
        backup.create_backup(
            **common, snapshot_id=pin, max_bytes=backup.DEFAULT_MAX_BYTES, retention_limit=7
        )
    pins_before = {
        pin: hashlib.sha256((backups / pin / "manifest.json").read_bytes()).hexdigest()
        for pin in PINS
    }
    rolling = backup.rolling_backup(
        **common, restore_root=str(restores), snapshot_id="synthetic-rolling-1", protected=PINS
    )
    assert (
        rolling["deleted_snapshots"] == [] and rolling["retention_policy"] == "fixed2-rolling2-v1"
    )
    restored = backup.verify_restore(
        backup_file=str(backups / rolling["snapshot_id"] / rolling["artifact"]),
        backup_root=str(backups),
        restore_root=str(restores),
        trial_id="independent-before",
        expected_sha256=rolling["sha256"],
        bounded_storage=True,
    )
    assert snapshot_database(restored["restore"]) == before and snapshot_database(source) == before
    _, patch = load_corrections(release)
    with get_connection(str(source)) as conn:
        plan = plan_tags(conn, patch)
        assert plan["change_count"] == 13
        applied = apply_tags(conn, patch, plan["plan_sha256"])
        post = snapshot_database(source)
        assert all(
            post["tables"][t] == before["tables"][t] for t in before["tables"] if t != "words"
        )
        try:
            apply_tags(conn, patch, plan["plan_sha256"])
        except ValueError:
            pass
        else:
            raise ValueError("stale data plan was accepted")
        assert snapshot_database(source) == post
        with sqlite3.connect(restored["restore"]) as prior:
            old_words = prior.execute("SELECT * FROM words ORDER BY id").fetchall()
        new_words = conn.execute("SELECT * FROM words ORDER BY id").fetchall()
        tag_index = [r[1] for r in conn.execute("PRAGMA table_info(words)")].index(
            "phoneme_tags_us"
        )
        assert all(
            tuple(v for i, v in enumerate(a) if i != tag_index)
            == tuple(v for i, v in enumerate(b) if i != tag_index)
            for a, b in zip(old_words, new_words)
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM words WHERE minimal_pair_group IS NOT NULL"
            ).fetchone()[0]
            == 0
        )
    assert client.get("/api/progress").json()["total_attempts"] == 1
    assert client.get("/api/today").json()["group_id"] == group["group_id"]
    post_readback = snapshot_database(source)
    patched = run_backup_restore_dry_run(
        source, root / "patched-backup.sqlite", root / "patched-restored.sqlite"
    )
    assert patched["verification"] == post_readback
    pair_db = state / "opt-in-pairs.sqlite"
    with sqlite3.connect(source) as src, sqlite3.connect(pair_db) as dst:
        src.backup(dst)
    evidence = load_pairs(release)
    member_count = sum(len(pair["members"]) for pair in evidence["pairs"])
    with get_connection(str(pair_db)) as conn:
        for pair in evidence["pairs"]:
            for member in pair["members"]:
                assert tuple(
                    conn.execute(
                        "SELECT ipa_us, minimal_pair_group FROM words WHERE id=?",
                        (member["word_id"],),
                    ).fetchone()
                ) == (member["ipa_us"], None)
        for pair in evidence["pairs"]:
            for member in pair["members"]:
                conn.execute(
                    "UPDATE words SET minimal_pair_group=? WHERE id=?",
                    (pair["group"], member["word_id"]),
                )
        conn.commit()
        assert (
            conn.execute(
                "SELECT count(*) FROM words WHERE minimal_pair_group IS NOT NULL"
            ).fetchone()[0]
            == member_count
        )
    db_mod.DEFAULT_DB_PATH = str(pair_db)
    os.environ["TINY_IPA_DB_PATH"] = str(pair_db)
    os.environ["TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH"] = str(
        release / "content/sound_compare_pairs_candidate.json"
    )
    pairs = client.post("/api/practice/minimal-pairs").json()
    assert len(pairs["items"]) == 4
    pair_item = pairs["items"][0]
    payload = {
        "session_item_id": pair_item["session_item_id"],
        "selected_answer": pair_item["display_ipa"],
    }
    feedback = client.post("/api/attempt", json=payload).json()
    assert feedback["sound_compare"]["status"] == "available"
    assert client.post("/api/attempt", json=payload).json()["replayed"]
    paired = run_backup_restore_dry_run(
        pair_db, root / "pair-backup.sqlite", root / "pair-restored.sqlite"
    )
    with sqlite3.connect(paired["restore"]) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            conn.execute(
                "SELECT count(*) FROM words WHERE minimal_pair_group IS NOT NULL"
            ).fetchone()[0]
            == member_count
        )
        assert conn.execute("SELECT count(*) FROM attempts").fetchone()[0] == 2
    assert all(
        hashlib.sha256((backups / pin / "manifest.json").read_bytes()).hexdigest()
        == pins_before[pin]
        for pin in PINS
    )
    assert snapshot_database(restored["restore"]) == before
    return {
        "package_runtime_path": str(Path(app.__file__).resolve()),
        "synthetic_only": True,
        "before_counts": {t: v["count"] for t, v in before["tables"].items()},
        "pending_items": 3,
        "tag_patch_updated": applied["updated"],
        "stale_plan_refused": True,
        "non_tag_fields_and_learner_history_preserved": True,
        "policy": rolling["retention_policy"],
        "synthetic_protected_ids": PINS,
        "deleted_snapshots": rolling["deleted_snapshots"],
        "independent_before_restore": restored["restore"],
        "patched_roundtrip": patched["restore"],
        "pair_roundtrip": paired["restore"],
        "pair_changes": member_count,
        "pair_feedback": feedback["sound_compare"],
        "default_pairs_unchanged": True,
        "listening_start_http_status": 404,
        "source_bytes": source.stat().st_size,
        "backup_restore_bytes": tree_bytes(backups) + tree_bytes(restores),
        "code_rollback": "not claimed; old deployed binary identity unknown",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker), sort_keys=True))
        return
    if not args.source_revision:
        parser.error("--source-revision is required")
    root = (
        args.output_root
        or Path(tempfile.gettempdir()).resolve() / f"tiny-ipa-offline-{uuid.uuid4().hex}"
    )
    print(json.dumps(rehearse(args.source_revision, root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
