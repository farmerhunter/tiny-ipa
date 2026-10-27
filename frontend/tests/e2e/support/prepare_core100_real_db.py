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
from app.models import User  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.services.db_store import create_user  # noqa: E402
from import_words import import_words  # noqa: E402
from prepare_core100_audio import prepare  # noqa: E402


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
        report = prepare(manifest_path, ROOT, ROOT / "audio/core100-candidate", cache)
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
    print(
        json.dumps(
            {"status": "disposable-fixture-ready", "audio_count": report["audio_count"]}
        )
    )


if __name__ == "__main__":
    main()
