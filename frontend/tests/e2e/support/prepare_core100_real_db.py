from __future__ import annotations
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend/scripts"))
from activate_core100_audio import apply, plan  # noqa: E402
from correct_core100_tags import apply as apply_tags  # noqa: E402
from correct_core100_tags import load_corrections, plan as plan_tags  # noqa: E402
from app.db import get_connection  # noqa: E402
from app.models import Settings, User  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.services.db_store import create_user, upsert_settings  # noqa: E402
from import_words import import_words  # noqa: E402
from prepare_sound_compare import load_pairs  # noqa: E402
from prepare_core100_audio import _write, prepare  # noqa: E402


def seed_audio_cache(archive: Path, manifest: dict, cache: Path) -> None:
    assets = manifest["audio"]["assets"]
    credits = manifest["audio"]["credits"]
    expected = {asset["path"]: asset for asset in assets}
    expected[credits["path"]] = credits
    if len(expected) != len(assets) + 1:
        raise ValueError("duplicate fixture paths")
    with zipfile.ZipFile(archive) as fixture:
        if len(fixture.namelist()) != len(expected) or set(fixture.namelist()) != set(
            expected
        ):
            raise ValueError("fixture members differ from the reviewed manifest")
        payloads = {}
        for name, asset in expected.items():
            checksum = asset["sha256"]
            if not re.fullmatch(r"[0-9a-f]{64}", checksum):
                raise ValueError("invalid fixture checksum")
            info = fixture.getinfo(name)
            if not 0 < info.file_size <= 10 * 1024 * 1024:
                raise ValueError("invalid fixture size")
            data = fixture.read(name)
            if hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError(f"fixture checksum mismatch: {name}")
            if "bytes" in asset and len(data) != asset["bytes"]:
                raise ValueError(f"fixture byte size mismatch: {name}")
            payloads[checksum] = data
    cache.mkdir()
    for asset in assets:
        with (cache / f"{asset['sha256']}.mp3").open("xb") as stream:
            stream.write(payloads[asset["sha256"]])


def prepare_core300(database: Path, audio_root: Path) -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    learner = TestClient(app)
    assert (
        learner.post(
            "/api/auth/login",
            json={
                "username": "workflow-owner",
                "password": "local-only-workflow",
            },
        ).status_code
        == 200
    )
    group = learner.post("/api/practice/next-normal").json()
    item = group["items"][0]
    assert learner.post(
        "/api/attempt",
        json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        },
    ).json()["is_correct"]
    owner = TestClient(app)
    assert (
        owner.post(
            "/api/auth/login",
            json={
                "username": "core100-owner",
                "password": "local-only-core100",
            },
        ).status_code
        == 200
    )
    previous_ids = set()
    for count in (50, 49):
        assert owner.put("/api/settings", json={"daily_word_count": count}).status_code == 200
        old_group = owner.post("/api/practice/next-normal").json()
        assert len(old_group["items"]) == count
        for old_item in old_group["items"]:
            previous_ids.add(old_item["word_id"])
            assert owner.post(
                "/api/attempt",
                json={
                    "session_item_id": old_item["session_item_id"],
                    "selected_answer": old_item["display_ipa"],
                },
            ).json()["is_correct"]
    assert len(previous_ids) == 99
    assert owner.put("/api/settings", json={"daily_word_count": 12}).status_code == 200
    tables = (
        "users",
        "auth_sessions",
        "settings",
        "daily_sessions",
        "session_items",
        "attempts",
        "phoneme_stats",
    )
    with get_connection(str(database)) as conn:
        before = {
            t: [tuple(r) for r in conn.execute(f'SELECT * FROM "{t}" ORDER BY rowid')]
            for t in tables
        }
    manifest_path = ROOT / "deploy/jingyun/core300-content-audio.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    new_ids = set(manifest["build"]["new_word_ids"])
    with tempfile.TemporaryDirectory(prefix="tiny-ipa-core300-ci-") as directory:
        old_cache, cache = Path(directory).resolve() / "old-cache", Path(directory).resolve() / "cache"
        seed_audio_cache(
            ROOT / "frontend/tests/fixtures/core100-media.zip",
            json.loads((ROOT / "deploy/jingyun/core100-content-audio.manifest.json").read_text()),
            old_cache,
        )
        extra_manifest = {
            "audio": {
                "assets": [a for a in manifest["audio"]["assets"] if a["word_id"] in new_ids],
                "credits": manifest["audio"]["credits"],
            }
        }
        seed_audio_cache(
            ROOT / "frontend/tests/fixtures/core300-extra-media.zip", extra_manifest, cache
        )
        for path in old_cache.iterdir():
            _write(cache / path.name, path.read_bytes(), path.stem)
        result = prepare(manifest_path, ROOT, audio_root, cache, pack_size=300)
    imported = import_words(
        ROOT / manifest["content"]["path"], ROOT / "content/phonemes.json", str(database)
    )
    if imported["errors"] or not imported["committed"]:
        raise ValueError("Core300 disposable import failed")
    with get_connection(str(database)) as conn:
        after = {
            t: [tuple(r) for r in conn.execute(f'SELECT * FROM "{t}" ORDER BY rowid')]
            for t in tables
        }
        assert before == after
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT count(*) FROM words").fetchone()[0] == 300
        assert (
            conn.execute("SELECT count(*) FROM words WHERE audio_us IS NOT NULL").fetchone()[0]
            == 111
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM words WHERE content_status='disabled' AND audio_us IS NOT NULL"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute("SELECT count(*) FROM attempts WHERE user_id='workflow'").fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "SELECT daily_word_count FROM settings WHERE user_id='default'"
            ).fetchone()[0]
            == 12
        )
        assert (
            conn.execute("SELECT count(*) FROM attempts WHERE user_id='default'").fetchone()[0]
            == 99
        )
    assert result["audio_count"] == 111


def main():
    database = Path(os.environ["CORE100_REAL_DB_PATH"])
    temporary_roots = (Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve())
    if (
        not any(root in database.resolve().parents for root in temporary_roots)
        or database.is_symlink()
    ):
        raise SystemExit(
            "test database must be a new path under the temporary directory"
        )
    if any(Path(str(database) + suffix).exists() for suffix in ("", "-wal", "-shm")):
        raise SystemExit("refusing to reuse a test database or sidecars")
    manifest_path = ROOT / "deploy/jingyun/core100-content-audio.manifest.json"
    with tempfile.TemporaryDirectory(prefix="tiny-ipa-core100-ci-") as directory:
        cache = Path(directory).resolve() / "cache"
        seed_audio_cache(
            ROOT / "frontend/tests/fixtures/core100-media.zip",
            json.loads(manifest_path.read_text()),
            cache,
        )
        audio_root = Path(
            os.environ.get(
                "CORE100_REAL_AUDIO_DIR", str(ROOT / "audio/core100-candidate")
            )
        )
        report = prepare(manifest_path, ROOT, audio_root, cache)
    imported = import_words(
        source_path=ROOT / "content/core_100_words.json",
        phonemes_path=ROOT / "content/phonemes.json",
        db_path=str(database),
    )
    if imported.get("errors"):
        raise SystemExit("candidate content import failed")
    with get_connection(str(database)) as conn:
        create_user(
            conn,
            User(
                id="default",
                username="core100-owner",
                password_hash=hash_password("local-only-core100"),
                is_owner=True,
                is_active=True,
                created_at="2026-10-27T00:00:00Z",
                updated_at="2026-10-27T00:00:00Z",
            ),
        )
        create_user(
            conn,
            User(
                id="workflow",
                username="workflow-owner",
                password_hash=hash_password("local-only-workflow"),
                is_owner=False,
                is_active=True,
                created_at="2026-10-28T00:00:00Z",
                updated_at="2026-10-28T00:00:00Z",
            ),
        )
        upsert_settings(conn, Settings(user_id="workflow"))
        conn.execute(
            "UPDATE settings SET daily_word_count=1, learner_level='entry', "
            "ui_language='en-US', review_strength='quick' WHERE user_id='workflow'"
        )
        conn.execute(
            "INSERT INTO phoneme_stats (user_id, primary_accent, phoneme_id, "
            "attempt_count, correct_count, last_attempt_at, last_wrong_at, mastery_status) "
            "VALUES ('workflow', 'US', '/ʃ/', 8, 0, '2026-10-27T00:00:00Z', "
            "'2026-10-27T00:00:00Z', 'weak')"
        )
        conn.execute(
            "UPDATE settings SET daily_word_count=12, learner_level='entry', "
            "ui_language='en-US', review_strength='quick' WHERE user_id='default'"
        )
        conn.commit()
        content = json.loads(
            (ROOT / "content/generated/core_100_audio_candidate.json").read_text()
        )
        manifest_sha = hashlib.sha256(
            (ROOT / "deploy/jingyun/core100-content-audio.manifest.json").read_bytes()
        ).hexdigest()
        activation = plan(conn, content, manifest_sha)
        assert activation["change_count"] == 89
        assert (
            apply(conn, content, manifest_sha, activation["plan_sha256"])["updated"]
            == 89
        )
        _, corrections = load_corrections()
        tag_plan = plan_tags(conn, corrections)
        assert apply_tags(conn, corrections, tag_plan["plan_sha256"])["updated"] == 13
        if os.environ.get("CORE100_REAL_PAIR_CANDIDATE") == "true":
            pairs = load_pairs()
            members = [
                (pair["group"], member)
                for pair in pairs["pairs"]
                for member in pair["members"]
            ]
            for _, member in members:
                row = conn.execute(
                    "SELECT ipa_us, minimal_pair_group FROM words WHERE id=?",
                    (member["word_id"],),
                ).fetchone()
                if row is None or row[0] != member["ipa_us"] or row[1] is not None:
                    raise ValueError("comparison fixture preimage differs")
            for group, member in members:
                conn.execute(
                    "UPDATE words SET minimal_pair_group=? WHERE id=?",
                    (group, member["word_id"]),
                )
            conn.commit()
        assert (
            conn.execute(
                "SELECT daily_word_count FROM settings WHERE user_id='default'"
            ).fetchone()[0]
            == 12
        )
        assert conn.execute("SELECT count(*) FROM words").fetchone()[0] == 100
        assert (
            conn.execute(
                "SELECT count(*) FROM words WHERE audio_us IS NOT NULL"
            ).fetchone()[0]
            == report["audio_count"]
        )
    if os.environ.get("CORE300_REAL_CANDIDATE") == "true":
        prepare_core300(database, audio_root)
    if os.environ.get("CORE100_REAL_LEVEL_ACCOUNTS") == "true":
        imported_mid = import_words(
            ROOT / "content/core_1000_words.json",
            ROOT / "content/phonemes.json",
            str(database),
            content_level="mid",
        )
        if imported_mid.get("errors") or not imported_mid["committed"]:
            raise SystemExit("Mid fixture import failed")
        with get_connection(str(database)) as conn:
            for suffix in ("a", "b"):
                uid = f"levels-{suffix}"
                create_user(
                    conn,
                    User(
                        id=uid,
                        username=f"level-{suffix}",
                        password_hash=hash_password(f"local-only-level-{suffix}"),
                        is_owner=False,
                        is_active=True,
                        created_at="2026-10-28T00:00:00Z",
                        updated_at="2026-10-28T00:00:00Z",
                    ),
                )
                upsert_settings(
                    conn,
                    Settings(
                        user_id=uid,
                        daily_word_count=2,
                        review_strength="quick",
                        ui_language="en-US",
                    ),
                )
            assert (
                conn.execute(
                    "SELECT count(*) FROM words WHERE level='intermediate'"
                ).fetchone()[0]
                == 1000
            )
            assert (
                conn.execute(
                    "SELECT count(*) FROM words WHERE level='intermediate' AND audio_us IS NOT NULL"
                ).fetchone()[0]
                == 0
            )
            conn.commit()
    print(
        json.dumps(
            {"status": "disposable-fixture-ready", "audio_count": report["audio_count"]}
        )
    )


if __name__ == "__main__":
    main()
