from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy" / "jingyun"
MANIFEST = DEPLOY / "p1b-content-audio.manifest.json"
VERIFIER = DEPLOY / "verify-p1b-assets.py"
NGINX = DEPLOY / "ipa.jingyun.bj.cn.nginx.candidate"
README = DEPLOY / "CANDIDATE-README.md"
ROADMAP = ROOT / "docs" / "06-epic-roadmap.md"
DEPLOYMENT_PLAN = ROOT / "docs" / "15-m14-jingyun-candidate-deployment-plan.md"
BACKUP_PLAN = ROOT / "docs" / "16-m14-jingyun-production-backup-restore-plan.md"
BOOTSTRAP = ROOT / "backend" / "scripts" / "bootstrap_auth.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ready_manifest(tmp_path: Path) -> tuple[Path, Path]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audio_root = tmp_path / "audio"
    assets = []
    for word_id in value["audio"]["required_word_ids"]:
        relative = Path("us") / f"{word_id}.mp3"
        path = audio_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ID3" + word_id.encode("ascii"))
        assets.append({
            "word_id": word_id,
            "path": relative.as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
            "source": "fixture source",
            "license": "fixture license",
        })
    value["status"] = "ready"
    value["audio"]["assets"] = assets
    value["audio"]["source"] = "fixture source"
    value["audio"]["license"] = "fixture license"
    value["blocking_reasons"] = []
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(value), encoding="utf-8")
    return manifest, audio_root


def _run(manifest: Path, audio_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--manifest",
            str(manifest),
            "--repo-root",
            str(ROOT),
            "--audio-root",
            str(audio_root),
        ],
        capture_output=True,
        text=True,
    )


def test_p1b_checked_in_manifest_truthfully_blocks_missing_audio(tmp_path: Path) -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert value["status"] == "blocked_missing_approved_audio"
    assert value["audio"]["assets"] == []
    assert value["audio"]["source"] is None
    assert value["audio"]["license"] is None
    assert set(value["blocking_reasons"]) == {
        "approved_audio_assets_missing",
        "audio_source_and_license_missing",
    }

    result = _run(MANIFEST, tmp_path)
    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "status": "blocked",
        "reason": "manifest status is blocked_missing_approved_audio",
    }


def test_p1b_manifest_binds_current_content_and_required_audio_urls() -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    content = value["content"]
    assert _sha256(ROOT / content["path"]) == content["sha256"]
    assert _sha256(ROOT / content["phonemes_path"]) == content["phonemes_sha256"]
    words = json.loads((ROOT / content["path"]).read_text(encoding="utf-8"))["words"]
    by_id = {word["word_id"]: word for word in words}
    assert len(words) == content["word_count"] == 100
    for word_id in value["audio"]["required_word_ids"]:
        assert by_id[word_id]["audio_us"] == f"/audio/us/{word_id}.mp3"


def test_p1b_asset_verifier_accepts_complete_licensed_mp3_set(tmp_path: Path) -> None:
    manifest, audio_root = _ready_manifest(tmp_path)
    result = _run(manifest, audio_root)
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "verified"
    assert payload["word_count"] == 100
    assert payload["audio_count"] == 10
    assert payload["audio_bytes"] > 0


@pytest.mark.parametrize("failure", ["checksum", "symlink", "license", "payload"])
def test_p1b_asset_verifier_fails_closed(tmp_path: Path, failure: str) -> None:
    manifest, audio_root = _ready_manifest(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    first = value["audio"]["assets"][0]
    path = audio_root / first["path"]
    if failure == "checksum":
        first["sha256"] = "0" * 64
    elif failure == "symlink":
        target = tmp_path / "outside.mp3"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
    elif failure == "license":
        first["license"] = ""
    else:
        path.write_bytes(b"not-mp3")
        first["bytes"] = path.stat().st_size
        first["sha256"] = _sha256(path)
    manifest.write_text(json.dumps(value), encoding="utf-8")

    result = _run(manifest, audio_root)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "blocked"


def test_p1b_nginx_candidate_is_scoped_and_requires_test_before_reload() -> None:
    nginx = NGINX.read_text(encoding="utf-8")
    assert "limit_req_zone $binary_remote_addr zone=tiny_ipa_login:10m rate=6r/m;" in nginx
    assert nginx.count("server_name ipa.jingyun.bj.cn;") == 2
    assert "listen 80;" in nginx
    assert "listen 443 ssl;" in nginx
    assert "location ^~ /.well-known/acme-challenge/" in nginx
    assert "root /var/lib/tiny-ipa/acme-webroot;" in nginx
    assert "return 308 https://ipa.jingyun.bj.cn$request_uri;" in nginx
    assert "ssl_certificate /etc/letsencrypt/live/ipa.jingyun.bj.cn/fullchain.pem;" in nginx
    assert "ssl_certificate_key /etc/letsencrypt/live/ipa.jingyun.bj.cn/privkey.pem;" in nginx
    assert "location = /api/auth/login" in nginx
    assert "limit_req zone=tiny_ipa_login burst=5 nodelay;" in nginx
    assert "proxy_pass http://127.0.0.1:18110/api/auth/login;" in nginx
    assert "alias /var/lib/tiny-ipa/audio/;" in nginx
    assert "disable_symlinks if_not_owner from=/var/lib/tiny-ipa/audio;" in nginx
    assert "default_server" not in nginx
    assert "xuetuzhiban" not in nginx.lower()

    readme = README.read_text(encoding="utf-8")
    assert "Host discovery, certificate issuance, installation, nginx -t, reload" in nginx
    assert "blocked_missing_approved_audio" in readme


def test_p1b_bootstrap_and_roadmap_record_current_contract() -> None:
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")
    assert bootstrap.count('add_argument("--password-stdin", action="store_true")') == 2
    assert "password stdin must contain exactly one non-empty line" in bootstrap
    assert "P1a is accepted and merged to main" in roadmap
    assert "#304 [P1b] HTTPS phone trial and non-empty recovery package - active" in roadmap


def test_p1b_discovery_is_read_only_and_apply_stays_human_gated() -> None:
    plan = DEPLOYMENT_PLAN.read_text(encoding="utf-8")
    discovery = plan.split("# P1B_READONLY_DISCOVERY_BEGIN", 1)[1].split(
        "# P1B_READONLY_DISCOVERY_END", 1
    )[0]
    for forbidden in (
        "systemctl start",
        "systemctl stop",
        "systemctl restart",
        "systemctl enable",
        "systemctl disable",
        "nginx -t",
        "certbot certonly",
        " install ",
        " rm ",
        " mv ",
        " cp ",
        "> /",
    ):
        assert forbidden not in discovery
    for required in (
        "This block is a candidate, not present authority to SSH",
        "One later Human decision",
        "VITE_API_BASE=/api",
        "--password-stdin",
        "real-phone login",
        "natural timer occurrence",
        "protected XueTuZhiBan checks",
    ):
        assert required in plan

    backup = BACKUP_PLAN.read_text(encoding="utf-8")
    assert "P1b non-empty trial and natural schedule gate" in backup
    assert "never changes the active DB pointer" in backup
    assert "API and timer remain disabled at boot" in backup
    assert "Automatic pruning" in backup
