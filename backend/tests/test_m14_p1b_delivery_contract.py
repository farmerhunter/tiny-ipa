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
ACME_BOOTSTRAP = DEPLOY / "ipa.jingyun.bj.cn.acme-bootstrap.nginx.candidate"
DISCOVERY = DEPLOY / "p1b-readonly-discovery.sh"
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
        path.write_bytes(f"package fixture for {word_id}".encode())
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


def _run(
    manifest: Path, audio_root: Path, repo_root: Path = ROOT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo_root),
            "--audio-root",
            str(audio_root),
        ],
        capture_output=True,
        text=True,
    )


def _fake_discovery_command(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text("#!/bin/bash\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _run_discovery(tmp_path: Path, **environment: str) -> subprocess.CompletedProcess[str]:
    fake = tmp_path / "bin"
    fake.mkdir()
    commands = {
        "timeout": 'shift\nexec "$@"',
        "whoami": "printf 'ubuntu\\n'",
        "hostname": "printf 'VM-0-7-ubuntu\\n'",
        "uname": "printf 'x86_64\\n'",
        "ss": 'printf \'%s\' "${FAKE_SS_OUTPUT:-}"\nexit "${FAKE_SS_RC:-0}"',
        "systemctl": (
            "printf 'LoadState=loaded\\nActiveState=inactive\\n"
            "SubState=dead\\nUnitFileState=disabled\\n'"
        ),
        "sudo": 'shift\nexec "$@"',
        "df": (
            "printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\\n"
            "/dev/fake 1000 1 999 1%% /\\n'"
        ),
        "python3": (
            "body=$(/bin/cat)\n"
            "if [[ $body == *getaddrinfo* ]]; then\n"
            "  printf '{\"dns_ipv4\":[\"203.0.113.10\"]}\\n'\n"
            "else\n"
            "  test \"${FAKE_METADATA_RC:-0}\" -eq 0 || exit \"$FAKE_METADATA_RC\"\n"
            "  printf '{\"path_metadata\":[]}\\n'\n"
            "fi"
        ),
    }
    paths = {name: _fake_discovery_command(fake, name, body) for name, body in commands.items()}
    script = DISCOVERY.read_text(encoding="utf-8")
    for name, path in paths.items():
        script = script.replace(f"/usr/bin/{name}", str(path))
    script_path = tmp_path / "discovery.sh"
    script_path.write_text(script, encoding="utf-8")
    env = {"PATH": f"{fake}:/bin", **environment}
    return subprocess.run(
        ["/bin/bash", str(script_path)], capture_output=True, text=True, env=env
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


def test_p1b_asset_verifier_accepts_complete_licensed_asset_package(tmp_path: Path) -> None:
    manifest, audio_root = _ready_manifest(tmp_path)
    result = _run(manifest, audio_root)
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "manifest_integrity_verified"
    assert payload["word_count"] == 100
    assert payload["audio_count"] == 10
    assert payload["audio_bytes"] > 0


@pytest.mark.parametrize(
    "failure", ["checksum", "symlink", "root_symlink", "license"]
)
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
    elif failure == "root_symlink":
        target = tmp_path / "real-audio"
        audio_root.rename(target)
        audio_root.symlink_to(target, target_is_directory=True)
    elif failure == "license":
        first["license"] = ""
    manifest.write_text(json.dumps(value), encoding="utf-8")

    result = _run(manifest, audio_root)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "blocked"


@pytest.mark.parametrize("root_kind", ["audio", "repo"])
def test_p1b_asset_verifier_rejects_declared_root_with_symlink_ancestor(
    tmp_path: Path, root_kind: str
) -> None:
    manifest, audio_root = _ready_manifest(tmp_path)
    if root_kind == "audio":
        target_parent = tmp_path / "audio-target"
        target_parent.mkdir()
        audio_root.rename(target_parent / "audio")
        link_parent = tmp_path / "audio-link"
        link_parent.symlink_to(target_parent, target_is_directory=True)
        audio_root = link_parent / "audio"
        repo_root = ROOT
    else:
        target_parent = tmp_path / "repo-target"
        repo_root = target_parent / "repo"
        value = json.loads(manifest.read_text(encoding="utf-8"))
        for key in ("path", "phonemes_path"):
            relative = Path(value["content"][key])
            destination = repo_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((ROOT / relative).read_bytes())
        link_parent = tmp_path / "repo-link"
        link_parent.symlink_to(target_parent, target_is_directory=True)
        repo_root = link_parent / "repo"

    result = _run(manifest, audio_root, repo_root)
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "asset root has a symlink component"


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
    assert "disable_symlinks on from=/var/lib/tiny-ipa/audio;" in nginx
    assert "default_server" not in nginx
    assert "xuetuzhiban" not in nginx.lower()

    readme = README.read_text(encoding="utf-8")
    assert "Host discovery, certificate issuance, installation, nginx -t, reload" in nginx
    assert "blocked_missing_approved_audio" in readme


def test_p1b_acme_bootstrap_allows_first_certificate_without_tls_dependency() -> None:
    bootstrap = ACME_BOOTSTRAP.read_text(encoding="utf-8")
    assert bootstrap.count("listen 80;") == 1
    assert "listen 443" not in bootstrap
    assert "ssl_certificate" not in bootstrap
    assert "location ^~ /.well-known/acme-challenge/" in bootstrap
    assert "root /var/lib/tiny-ipa/acme-webroot;" in bootstrap
    assert "location /" in bootstrap
    assert "return 404;" in bootstrap
    assert "return 308" not in bootstrap
    assert "default_server" not in bootstrap
    assert "xuetuzhiban" not in bootstrap.lower()


def test_p1b_readonly_discovery_reports_success_only_after_all_queries(tmp_path: Path) -> None:
    result = _run_discovery(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "p1b-readonly-discovery-passed" in result.stdout
    assert '"dns_ipv4":["203.0.113.10"]' in result.stdout


@pytest.mark.parametrize(
    "environment", [{"FAKE_SS_RC": "9"}, {"FAKE_METADATA_RC": "8"}]
)
def test_p1b_readonly_discovery_query_failure_never_reports_success(
    tmp_path: Path, environment: dict[str, str]
) -> None:
    result = _run_discovery(tmp_path, **environment)
    assert result.returncode != 0
    assert "p1b-readonly-discovery-passed" not in result.stdout


def test_p1b_readonly_discovery_contains_no_mutation_commands() -> None:
    discovery = DISCOVERY.read_text(encoding="utf-8")
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


@pytest.mark.parametrize("error_name", ["EAI_AGAIN", "EAI_FAIL"])
def test_p1b_dns_producer_propagates_resolver_operational_failures(error_name: str) -> None:
    discovery = DISCOVERY.read_text(encoding="utf-8")
    producer = discovery.split("# P1B_DNS_PYTHON_BEGIN", 1)[1].split(
        "# P1B_DNS_PYTHON_END", 1
    )[0]
    injection = (
        "import socket\n"
        "def injected_failure(*args, **kwargs):\n"
        f"    raise socket.gaierror(socket.{error_name}, 'injected')\n"
        "socket.getaddrinfo = injected_failure\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", injection + producer],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert '"dns_ipv4":[]' not in result.stdout


def test_p1b_dns_producer_represents_only_name_absence_as_empty() -> None:
    discovery = DISCOVERY.read_text(encoding="utf-8")
    producer = discovery.split("# P1B_DNS_PYTHON_BEGIN", 1)[1].split(
        "# P1B_DNS_PYTHON_END", 1
    )[0]
    injection = (
        "import socket\n"
        "def injected_failure(*args, **kwargs):\n"
        "    raise socket.gaierror(socket.EAI_NONAME, 'injected')\n"
        "socket.getaddrinfo = injected_failure\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", injection + producer],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"dns_ipv4": []}


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
