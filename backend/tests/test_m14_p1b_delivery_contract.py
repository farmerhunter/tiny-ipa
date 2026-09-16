from __future__ import annotations

import hashlib
import json
import os
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
ATTRIBUTION = ROOT / "audio" / "ATTRIBUTION.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ready_manifest(tmp_path: Path) -> tuple[Path, Path]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audio_root = tmp_path / "audio"
    audio_root.mkdir()
    (audio_root / "ATTRIBUTION.md").write_bytes(ATTRIBUTION.read_bytes())
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


def test_p1b_checked_in_manifest_binds_approved_audio_package() -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert value["status"] == "ready"
    assert value["blocking_reasons"] == []
    assert len(value["audio"]["assets"]) == 10
    assert "Wikimedia Commons" in value["audio"]["source"]
    assert "CC BY-SA 3.0" in value["audio"]["license"]

    result = _run(MANIFEST, ROOT / "audio")
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout) == {
        "status": "manifest_integrity_verified",
        "word_count": 100,
        "audio_count": 10,
        "audio_bytes": 129751,
        "credits_sha256": value["audio"]["credits"]["sha256"],
        "content_sha256": value["content"]["sha256"],
        "phonemes_sha256": value["content"]["phonemes_sha256"],
    }

    credits = ATTRIBUTION.read_text(encoding="utf-8")
    for asset in value["audio"]["assets"]:
        assert f"`{Path(asset['path']).name}`" in credits
        assert asset["source"].split(";", 1)[0] in credits
    assert "CC BY-SA 3.0" in credits
    assert "CC0 1.0" in credits
    assert "Public Domain" in credits
    assert "transcoded from Ogg or WAV to MP3" in credits
    assert "with metadata removed" in credits
    assert value["audio"]["credits"]["path"] == "ATTRIBUTION.md"
    assert value["audio"]["credits"]["public_url"] == "/audio/ATTRIBUTION.md"
    assert _sha256(ATTRIBUTION) == value["audio"]["credits"]["sha256"]


def test_p1b_manifest_binds_current_content_and_required_audio_urls() -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    content = value["content"]
    assert content["import_content_level"] == "auto"
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
    assert nginx.count("listen 443 ssl default_server;") == 1
    assert nginx.count("ssl_reject_handshake on;") == 1
    assert "listen 80 default_server" not in nginx
    assert "listen [::]:443" not in nginx
    assert "xuetuzhiban" not in nginx.lower()

    readme = README.read_text(encoding="utf-8")
    assert "Host discovery, certificate issuance, installation, nginx -t, reload" in nginx
    assert "status `ready`" in readme
    assert "audio/ATTRIBUTION.md" in readme
    assert "/audio/ATTRIBUTION.md" in readme


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


@pytest.mark.parametrize(
    ("environment", "expected_success"),
    [
        ({}, True),
        ({"FAKE_INFO_FAIL": "core24"}, False),
        ({"FAKE_TIMER_UNIT_FILE": "disabled"}, False),
        ({"FAKE_REFRESH_NEXT": "n/a"}, False),
    ],
)
def test_p1b_snap_install_gate_stops_before_issuance(
    tmp_path: Path, environment: dict[str, str], expected_success: bool
) -> None:
    plan = DEPLOYMENT_PLAN.read_text(encoding="utf-8")
    script = plan.split("# P1B_SNAP_INSTALL_GATE_BEGIN", 1)[1].split(
        "# P1B_SNAP_INSTALL_GATE_END", 1
    )[0]
    fake_timeout = _fake_discovery_command(tmp_path, "timeout", 'shift\nexec "$@"')
    fake_snap = _fake_discovery_command(
        tmp_path,
        "snap",
        """
case "$1" in
  info)
    if test "$2" = core24; then
      printf '  latest/stable: 20260824 2026-09-10 (2124) 70MB -\\n'
    else
      printf '  latest/stable: 5.8.0 2026-09-01 (5893) 75MB classic\\n'
    fi
    test "${FAKE_INFO_FAIL:-}" != "$2"
    ;;
  install) exit 0 ;;
  list)
    printf 'Name Version Rev Tracking Publisher Notes\\n'
    printf 'core24 20260824 2124 latest/stable canonical** base\\n'
    printf 'certbot 5.8.0 5893 latest/stable certbot-eff** classic\\n'
    ;;
  refresh)
    printf 'timer: 00:00~24:00/4\\nnext: %s\\n' "${FAKE_REFRESH_NEXT:-tomorrow}"
    ;;
  *) exit 90 ;;
esac
""",
    )
    fake_systemctl = _fake_discovery_command(
        tmp_path,
        "systemctl",
        """
property=
while test "$#" -gt 0; do
  if test "$1" = -p; then property=$2; shift 2; else shift; fi
done
case "$property" in
  LoadState) printf 'loaded\\n' ;;
  ActiveState) printf 'active\\n' ;;
  SubState) printf 'waiting\\n' ;;
  UnitFileState) printf '%s\\n' "${FAKE_TIMER_UNIT_FILE:-enabled}" ;;
  *) exit 91 ;;
esac
""",
    )
    issuance = tmp_path / "issuance"
    fake_certbot = _fake_discovery_command(
        tmp_path,
        "certbot",
        'printf issued > "$FAKE_ISSUANCE_SENTINEL"',
    )
    script = script.replace("sudo -n ", "")
    script = script.replace("/usr/bin/timeout", str(fake_timeout))
    script = script.replace("/usr/bin/snap", str(fake_snap))
    script = script.replace("/usr/bin/systemctl", str(fake_systemctl))
    script = script.replace("/snap/bin/certbot", str(fake_certbot))
    script = script.replace("<HUMAN_APPROVED_ACME_EMAIL>", "owner@example.test")
    script = script.replace("<APPROVED_TOOL_REVISION>", "test-revision")
    result = subprocess.run(
        ["/bin/bash", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, **environment, "FAKE_ISSUANCE_SENTINEL": str(issuance)},
    )

    assert (result.returncode == 0) is expected_success, result.stderr
    assert issuance.exists() is expected_success


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
