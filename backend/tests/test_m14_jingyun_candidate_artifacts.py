from __future__ import annotations

import errno
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIR = ROOT / "deploy" / "jingyun"
SYSTEMD = CANDIDATE_DIR / "tiny-ipa-api.service.candidate"
NGINX = CANDIDATE_DIR / "ipa.jingyun.bj.cn.nginx.candidate"
ENV_EXAMPLE = CANDIDATE_DIR / "tiny-ipa.production.env.example"
REVISION = CANDIDATE_DIR / "REVISION.candidate"
DEPLOYMENT_PLAN = ROOT / "docs" / "15-m14-jingyun-candidate-deployment-plan.md"
BACKUP_PLAN = ROOT / "docs" / "16-m14-jingyun-production-backup-restore-plan.md"

REQUIRED_FILES = (
    CANDIDATE_DIR / "CANDIDATE-README.md",
    SYSTEMD,
    NGINX,
    ENV_EXAMPLE,
    REVISION,
    DEPLOYMENT_PLAN,
    BACKUP_PLAN,
)

APPROVED_NAMESPACE = (
    "ipa.jingyun.bj.cn",
    "/opt/tiny-ipa",
    "/var/www/tiny-ipa",
    "/var/lib/tiny-ipa",
    "/var/backups/tiny-ipa",
    "/opt/tiny-ipa/current/REVISION",
    "/api/version",
    "tiny-ipa-api.service",
    "127.0.0.1:18110",
)

HUMAN_PLACEHOLDERS = (
    "<HUMAN_APPROVED_TINY_IPA_SERVICE_USER>",
    "<HUMAN_APPROVED_TINY_IPA_SERVICE_GROUP>",
    "<HUMAN_OWNED_TINY_IPA_ENV_FILE>",
    "<HUMAN_PROVIDED_TLS_CERTIFICATE_PATH_FOR_IPA_JINGYUN>",
    "<HUMAN_PROVIDED_TLS_KEY_PATH_FOR_IPA_JINGYUN>",
    "<HUMAN_PROVISIONED_TINY_IPA_SESSION_SECRET>",
    "<HUMAN_APPROVED_BACKUP_OWNER>",
    "<HUMAN_APPROVED_BACKUP_RETENTION_POLICY>",
    "<HUMAN_APPROVED_ROLLBACK_OWNER>",
    "<INTENDED_GIT_COMMIT_OR_TAG_RELEASE_ID>",
    "<INTENDED_GITHUB_COMMIT_SHA>",
    "<OPTIONAL_SIGNED_OR_ANNOTATED_GIT_TAG>",
    "<UTC_RELEASE_ARTIFACT_TIMESTAMP>",
    "<PREVIOUS_ACTIVE_RELEASE_ID_RECORDED_BEFORE_CHANGE>",
    "<PREVIOUS_ACTIVE_RELEASE_PATH_RECORDED_BEFORE_CHANGE>",
)

FORBIDDEN_CONFIG_REFERENCES = (
    "/opt/hermes",
    "/var/www/hermes-web",
    "/home/ubuntu/.hermes",
    "xuetuzhiban-api.service",
    "redis-server.service",
)

FORBIDDEN_SECRET_PATTERNS = (
    "BEGIN PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "ghp_",
    "github_pat_",
    "local-dry-run-only",
    "password=",
    "token=",
    "cookie=",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _marked(text: str, begin: str, end: str) -> str:
    return text.split(begin, 1)[1].split(end, 1)[0].strip()


def _fake_command(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)


def _h0_fake_bin(tmp_path: Path) -> Path:
    fake = tmp_path / "bin"
    fake.mkdir()
    _fake_command(
        fake,
        "whoami",
        "printf '%s\\n' \"${FAKE_IDENTITY:-ubuntu}\"\n"
        "exit \"${FAKE_IDENTITY_RC:-0}\"",
    )
    _fake_command(
        fake,
        "hostname",
        "printf '%s\\n' \"${FAKE_HOST:-VM-0-7-ubuntu}\"",
    )
    _fake_command(fake, "uname", "printf '%s\\n' \"${FAKE_MACHINE:-x86_64}\"")
    _fake_command(
        fake,
        "free",
        "printf 'Mem: 4096 1 1 1 1 %s\\n' \"${FAKE_AVAILABLE_MB:-2048}\"",
    )
    _fake_command(
        fake,
        "df",
        "printf 'Filesystem 1024-blocks Used Available Capacity Mounted\\n'\n"
        "printf '/dev/fake 9000000 1 8000000 1%% /\\n'",
    )
    _fake_command(
        fake,
        "ss",
        "printf '%s' \"${FAKE_SS_OUTPUT:-}\"\nexit \"${FAKE_SS_RC:-0}\"",
    )
    _fake_command(
        fake,
        "getent",
        "key=$(printf '%s' \"$1\" | tr '[:lower:]' '[:upper:]')\n"
        "eval 'output=${FAKE_GETENT_'\"$key\"'_OUTPUT:-}'\n"
        "eval 'rc=${FAKE_GETENT_'\"$key\"'_RC:-2}'\n"
        "printf '%s' \"$output\"\nexit \"$rc\"",
    )
    _fake_command(
        fake,
        "systemctl",
        "printf 'not-found\\n'\nexit \"${FAKE_SYSTEMCTL_RC:-0}\"",
    )
    _fake_command(fake, "systemd-analyze", "printf 'systemd 255\\n'")
    _fake_command(fake, "openssl", "printf 'OpenSSL test\\n'")
    _fake_command(fake, "tar", "printf 'tar test\\n'")
    _fake_command(fake, "sha256sum", "printf 'sha test\\n'")
    _fake_command(
        fake,
        "timeout",
        "if test \"$1\" = --version; then printf 'timeout test\\n'; exit 0; fi\n"
        "exit \"${FAKE_PYTHON_RC:-0}\"",
    )
    _fake_command(
        fake,
        "python3",
        "cat >/dev/null\nexit \"${FAKE_PYTHON_RC:-0}\"",
    )
    _fake_command(
        fake,
        "curl",
        "case \"${*: -1}\" in\n"
        "  */apps/xuetuzhiban/demo/) printf '200||' ;;\n"
        "  */apps/xuetuzhiban-test/demo/) printf '302||/apps/xuetuzhiban/demo/' ;;\n"
        "  *) printf '503|no-store|' ;;\n"
        "esac",
    )
    for command in ("useradd", "install", "scp"):
        _fake_command(
            fake,
            command,
            "printf '%s\\n' \"$0 $*\" >> \"$FAKE_H0_SENTINEL\"\nexit 99",
        )
    return fake


def _run_h0(tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    plan = _text(DEPLOYMENT_PLAN)
    script = _marked(plan, "# P1A_H0_GATE_BEGIN", "# P1A_H0_GATE_END")
    replacements = {
        "<APPROVED_PYTHON_VERSION>": "3.12.0",
        "<APPROVED_SOABI>": "cpython-test",
        "<APPROVED_SYSCONFIG_PLATFORM>": "linux-x86_64",
        "<APPROVED_LIBC_PROFILE>": "glibc-test",
    }
    for source, target in replacements.items():
        script = script.replace(source, target)
    fake = _h0_fake_bin(tmp_path)
    environment = os.environ.copy()
    environment.update(overrides)
    environment["PATH"] = f"{fake}:{environment['PATH']}"
    environment["FAKE_H0_SENTINEL"] = str(tmp_path / "h0-mutation-sentinel")
    return subprocess.run(
        ["bash", "-c", script], check=False, capture_output=True, text=True,
        env=environment,
    )


def _run_staging(
    tmp_path: Path, *, fail_step: int = 0, bad_digest: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    plan = _text(DEPLOYMENT_PLAN)
    script = _marked(
        plan, "# P1A_H1_STAGING_BEGIN", "# P1A_H1_STAGING_END"
    )
    stage = tmp_path / "stage"
    stage.mkdir(mode=0o700)
    (stage / "tiny-ipa-release-1.tar.gz").touch()
    replacements = {
        "/tmp/tiny-ipa-p1a": str(stage),
        "<APPROVED_RELEASE_ID>": "release-1",
        "<APPROVED_ARTIFACT_SHA256>": "approved-digest",
        "<APPROVED_STAGING_REQUIRED_KB>": "1",
        "<APPROVED_UNPACKED_MAX_BYTES>": "1000000",
    }
    for source, target in replacements.items():
        script = script.replace(source, target)

    fake = tmp_path / "stage-bin"
    fake.mkdir()
    counter = tmp_path / "timeout-counter"
    sentinel = tmp_path / "activation-sentinel"
    _fake_command(fake, "stat", "printf 'ubuntu|700\\n'")
    _fake_command(
        fake,
        "sha256sum",
        "printf '%s  %s\\n' \"${FAKE_DIGEST:-approved-digest}\" \"$1\"",
    )
    _fake_command(
        fake,
        "df",
        "printf 'Filesystem 1024-blocks Used Available Capacity Mounted\\n'\n"
        "printf '/dev/fake 9000000 1 8000000 1%% /\\n'",
    )
    _fake_command(
        fake,
        "timeout",
        "count=0\n"
        "test -f \"$FAKE_COUNTER\" && count=$(cat \"$FAKE_COUNTER\")\n"
        "count=$((count + 1))\nprintf '%s' \"$count\" > \"$FAKE_COUNTER\"\n"
        "test \"${FAKE_FAIL_STEP:-0}\" -eq \"$count\" && exit 1\nexit 0",
    )
    for command in ("sudo", "useradd", "systemctl", "install"):
        _fake_command(
            fake,
            command,
            "printf '%s\\n' \"$0 $*\" >> \"$FAKE_SENTINEL\"\nexit 99",
        )
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake}:{environment['PATH']}",
            "FAKE_COUNTER": str(counter),
            "FAKE_SENTINEL": str(sentinel),
            "FAKE_FAIL_STEP": str(fail_step),
            "FAKE_DIGEST": "wrong" if bad_digest else "approved-digest",
        }
    )
    result = subprocess.run(
        ["bash", "-c", script], check=False, capture_output=True, text=True,
        env=environment,
    )
    return result, sentinel


def _run_runtime_probe(
    tmp_path: Path,
    overrides: dict[str, tuple[int, dict[str, str], bytes]] | None = None,
    *,
    bad_revision: bool = False,
) -> subprocess.CompletedProcess[str]:
    release = "release-1"
    commit = "a" * 40
    responses = {
        "/api/health": (200, {}, b'{"status":"ok"}'),
        "/api/version": (
            200,
            {"Cache-Control": "no-store"},
            json.dumps(
                {
                    "status": "ok",
                    "release_id": release,
                    "commit": commit,
                    "tag": None,
                }
            ).encode(),
        ),
        "/api/auth/me": (200, {}, b'{"authenticated":false,"user":null}'),
        "/api/progress": (401, {}, b'{"detail":{"error":"AUTH_REQUIRED"}}'),
    }
    responses.update(overrides or {})

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            status, headers, body = responses[self.path]
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    revision = tmp_path / "REVISION"
    revision_commit = "wrong" if bad_revision else commit
    revision.write_text(f"release_id={release}\ncommit={revision_commit}\ntag=\n")
    probe = _marked(
        _text(DEPLOYMENT_PLAN),
        "# P1A_RUNTIME_PROBE_BEGIN",
        "# P1A_RUNTIME_PROBE_END",
    )
    probe = probe.replace(
        '("127.0.0.1", 18110, timeout=3)',
        f'("127.0.0.1", {server.server_port}, timeout=3)',
    ).replace("/opt/tiny-ipa/current/REVISION", str(revision))
    try:
        return subprocess.run(
            [sys.executable, "-I", "-B", "-", release, commit],
            input=probe,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _run_acceptance(tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    script = _marked(
        _text(DEPLOYMENT_PLAN),
        "# P1A_H1_ACCEPTANCE_BEGIN",
        "# P1A_H1_ACCEPTANCE_END",
    ).replace("<APPROVED_RELEASE_ID>", "release-1").replace(
        "<APPROVED_GITHUB_SHA>", "a" * 40
    )
    fake = tmp_path / "accept-bin"
    fake.mkdir()
    restart_state = tmp_path / "restarted"
    _fake_command(
        fake,
        "systemctl",
        "case \"$*\" in\n"
        "  *ActiveState*) printf 'active\\n' ;;\n"
        "  *MemoryMax*) printf '536870912\\n' ;;\n"
        "  *TasksMax*) printf '64\\n' ;;\n"
        "  *InvocationID*)\n"
        "    if test -f \"$FAKE_RESTART_STATE\" "
        "&& test \"${FAKE_UNCHANGED:-0}\" != 1; then "
        "printf 'after\\n'; else printf 'before\\n'; fi ;;\n"
        "  *) exit 1 ;;\n"
        "esac",
    )
    _fake_command(
        fake,
        "ss",
        "printf '%s' \"${FAKE_LISTENERS:-LISTEN 0 128 127.0.0.1:18110 0.0.0.0:*}\"\n"
        "exit \"${FAKE_SS_RC:-0}\"",
    )
    _fake_command(
        fake,
        "readlink",
        "printf '%s\\n' \"${FAKE_POINTER:-/opt/tiny-ipa/releases/release-1}\"",
    )
    _fake_command(
        fake,
        "timeout",
        "duration=$1\nshift\n"
        "if test \"$duration\" = 45s; then\n"
        "  test \"${FAKE_RESTART_RC:-0}\" -eq 0 || exit \"$FAKE_RESTART_RC\"\n"
        "  : > \"$FAKE_RESTART_STATE\"\n  exit 0\n"
        "fi\n"
        "exit \"${FAKE_PROBE_RC:-0}\"",
    )
    _fake_command(
        fake,
        "curl",
        "case \"${*: -1}\" in\n"
        "  */apps/xuetuzhiban/demo/) printf '200||' ;;\n"
        "  */apps/xuetuzhiban-test/demo/) printf '302||/apps/xuetuzhiban/demo/' ;;\n"
        "  *) printf '503|no-store|' ;;\n"
        "esac",
    )
    environment = os.environ.copy()
    environment.update(overrides)
    environment.update(
        {
            "PATH": f"{fake}:{environment['PATH']}",
            "FAKE_RESTART_STATE": str(restart_state),
        }
    )
    return subprocess.run(
        ["bash", "-c", script], check=False, capture_output=True, text=True,
        env=environment,
    )


def _run_withdrawal(tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    script = _marked(
        _text(DEPLOYMENT_PLAN), "# P1A_WITHDRAWAL_BEGIN", "# P1A_WITHDRAWAL_END"
    )
    fake = tmp_path / "withdraw-bin"
    fake.mkdir()
    _fake_command(
        fake,
        "systemctl",
        "test \"${FAKE_SYSTEMCTL_RC:-0}\" -eq 0 || exit \"$FAKE_SYSTEMCTL_RC\"\n"
        "case \"$*\" in *LoadState*) printf 'loaded\\n' ;; "
        "*ActiveState*) printf 'inactive\\n' ;; *) exit 1 ;; esac",
    )
    _fake_command(
        fake,
        "timeout",
        "exit \"${FAKE_STOP_RC:-0}\"",
    )
    _fake_command(
        fake,
        "ss",
        "printf '%s' \"${FAKE_SS_OUTPUT:-}\"\nexit \"${FAKE_SS_RC:-0}\"",
    )
    environment = os.environ.copy()
    environment.update(overrides)
    environment["PATH"] = f"{fake}:{environment['PATH']}"
    return subprocess.run(
        ["bash", "-c", script], check=False, capture_output=True, text=True,
        env=environment,
    )


def _run_archive_validator(
    tmp_path: Path, *, unsafe: str | None = None,
) -> subprocess.CompletedProcess[str]:
    archive = tmp_path / "candidate.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        members = {
            "backend/requirements.lock.txt": b"demo==1 --hash=sha256:abc\n",
            "backend/wheelhouse/demo-1-py3-none-any.whl": b"wheel",
        }
        if unsafe == "traversal":
            members["../escape"] = b"escape"
        elif unsafe == "url":
            members["backend/requirements.lock.txt"] = b"demo @ https://example.invalid/x.whl\n"
        elif unsafe == "sdist":
            members["backend/wheelhouse/demo-1.tar.gz"] = b"sdist"
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            bundle.addfile(info, io.BytesIO(payload))
        if unsafe == "symlink":
            info = tarfile.TarInfo("backend/wheelhouse/link.whl")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            bundle.addfile(info)
    validator = _marked(
        _text(DEPLOYMENT_PLAN),
        "# P1A_STAGE_ARCHIVE_PYTHON_BEGIN",
        "# P1A_STAGE_ARCHIVE_PYTHON_END",
    )
    destination = tmp_path / "extracted"
    destination.mkdir()
    return subprocess.run(
        [sys.executable, "-I", "-B", "-", str(archive), str(destination), "1000000"],
        input=validator,
        check=False,
        capture_output=True,
        text=True,
    )


def _all_candidate_text() -> str:
    return "\n".join(_text(path) for path in REQUIRED_FILES)


def _assert_bundle_text(combined: str) -> None:
    for value in APPROVED_NAMESPACE:
        assert value in combined, f"approved namespace missing: {value}"

    for placeholder in HUMAN_PLACEHOLDERS:
        assert placeholder in combined, f"Human placeholder missing: {placeholder}"

    assert "CANDIDATE - DO NOT APPLY" in combined, "candidate safety marker missing"
    assert "TINY_IPA_AUDIO_ROOT" not in combined, "unsupported audio variable present"
    assert "default_server" not in combined, "unsafe default Nginx ownership present"

    for pattern in FORBIDDEN_SECRET_PATTERNS:
        assert pattern not in combined, f"secret-like material present: {pattern}"


def _assert_common_candidate_boundaries() -> None:
    for path in REQUIRED_FILES:
        assert path.exists(), f"missing candidate artifact: {path}"
        assert "CANDIDATE - DO NOT APPLY" in _text(path)

    _assert_bundle_text(_all_candidate_text())


def test_m14_jingyun_candidate_files_exist_and_keep_human_gates() -> None:
    _assert_common_candidate_boundaries()

    combined = " ".join(_all_candidate_text().split())
    for boundary in (
        "does not authorize SSH",
        "does not authorize applying any artifact",
        "TLS certificate ownership remains unresolved",
        "backup owner and retention policy",
        "rollback owner",
        "Xue Tu Zhi Ban baseline",
    ):
        assert boundary in combined


def test_m14_jingyun_systemd_candidate_is_loopback_non_root_and_isolated() -> None:
    unit = _text(SYSTEMD)

    assert "User=tiny-ipa" in unit
    assert "Group=tiny-ipa" in unit
    assert "User=root" not in unit
    assert "Group=root" not in unit
    assert "WorkingDirectory=/opt/tiny-ipa/current/backend" in unit
    assert "EnvironmentFile=/etc/tiny-ipa/tiny-ipa.env" in unit
    assert "--host 127.0.0.1 --port 18110" in unit
    assert "ReadWritePaths=/var/lib/tiny-ipa" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "MemoryMax=512M" in unit
    assert "TasksMax=64" in unit

    assert re.findall(r"--port\s+(\d+)", unit) == ["18110"]
    for forbidden in FORBIDDEN_CONFIG_REFERENCES:
        assert forbidden not in unit


def test_m14_p1a_preflight_and_withdrawal_are_fail_closed() -> None:
    plan = _text(DEPLOYMENT_PLAN)
    required = (
        'test "$(whoami)" = ubuntu',
        'test "$(hostname)" = VM-0-7-ubuntu',
        'test "$(uname -m)" = x86_64',
        "test -z \"$(ss -ltnH 'sport = :18110')\"",
        "if getent passwd tiny-ipa >/dev/null; then exit 20; fi",
        "if getent group tiny-ipa >/dev/null; then exit 21; fi",
        "permission failure are distinct results",
        "python3 -m venv --help >/dev/null",
        "sysconfig.get_config_var",
        "test \"$status\" = 503",
        "sudo -n useradd --system --user-group",
        "TINY_IPA_SESSION_SECRET=$secret",
        "sha256sum -c OFFLINE-MANIFEST.sha256",
        "for unit in tiny-ipa-backup.timer tiny-ipa-backup.service "
        "tiny-ipa-api.service",
        'sudo -n systemctl stop "$unit"',
        "No `rm`, `unlink`,",
    )
    for phrase in required:
        assert phrase in plan
    assert "absent or exactly explained" not in plan


def test_m14_p1a_h0_canonical_gate_accepts_only_checked_absence(tmp_path: Path) -> None:
    result = _run_h0(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "200||" in result.stdout
    assert "302||/apps/xuetuzhiban/demo/" in result.stdout
    assert result.stdout.count("503|no-store|") == 4
    assert not (tmp_path / "h0-mutation-sentinel").exists()


@pytest.mark.parametrize(
    "environment",
    [
        {"FAKE_SS_RC": "1"},
        {"FAKE_SS_OUTPUT": "LISTEN 0 1 0.0.0.0:18110 0.0.0.0:*"},
        {"FAKE_IDENTITY": "root"},
        {"FAKE_IDENTITY_RC": "1"},
        {"FAKE_AVAILABLE_MB": "unknown"},
        {"FAKE_SYSTEMCTL_RC": "1"},
        {"FAKE_GETENT_PASSWD_RC": "0"},
        {"FAKE_GETENT_PASSWD_RC": "2", "FAKE_GETENT_PASSWD_OUTPUT": "row"},
        {"FAKE_GETENT_PASSWD_RC": "3"},
        {"FAKE_GETENT_GROUP_RC": "127"},
        {"FAKE_PYTHON_RC": "61"},
        {"FAKE_PYTHON_RC": "65"},
        {"FAKE_PYTHON_RC": "66"},
    ],
)
def test_m14_p1a_h0_query_and_python_boundary_failures_hold(
    tmp_path: Path, environment: dict[str, str],
) -> None:
    result = _run_h0(tmp_path, **environment)
    assert result.returncode != 0
    assert not (tmp_path / "h0-mutation-sentinel").exists()


@pytest.mark.parametrize(
    ("rc", "observed_errno", "present", "passes"),
    [
        (0, 0, False, True),
        (errno.EAGAIN, errno.EAGAIN, False, False),
        (errno.EIO, errno.EIO, False, False),
        (errno.ERANGE, errno.ERANGE, False, False),
        (0, 0, True, False),
    ],
)
def test_m14_p1a_documented_libc_decision_is_behavior_checked(
    rc: int, observed_errno: int, present: bool, passes: bool,
) -> None:
    plan = _text(DEPLOYMENT_PLAN)
    decision = _marked(
        plan, "# P1A_NSS_DECISION_BEGIN", "# P1A_NSS_DECISION_END"
    )

    def fail(code: int, label: str) -> None:
        raise RuntimeError(code, label)

    namespace = {"errno": errno, "fail": fail}
    exec(decision, namespace)
    if passes:
        namespace["require_absent"](rc, observed_errno, present)
    else:
        with pytest.raises(RuntimeError):
            namespace["require_absent"](rc, observed_errno, present)


def test_m14_p1a_documented_lstat_decision_distinguishes_absence_and_errors() -> None:
    decision = _marked(
        _text(DEPLOYMENT_PLAN),
        "# P1A_LSTAT_DECISION_BEGIN",
        "# P1A_LSTAT_DECISION_END",
    )

    def fail(code: int, label: str) -> None:
        raise RuntimeError(code, label)

    namespace = {
        "os": os,
        "platform": __import__("platform"),
        "stat": __import__("stat"),
        "fail": fail,
    }
    exec(decision, namespace)

    def missing(path: str):
        raise FileNotFoundError(path)

    namespace["require_path_absent"]("/var/lib/tiny-ipa", False, missing)

    def denied(path: str):
        raise PermissionError(path)

    with pytest.raises(RuntimeError):
        namespace["require_path_absent"]("/var/lib/tiny-ipa", False, denied)
    with pytest.raises(RuntimeError):
        namespace["require_path_absent"](
            "/var/lib/tiny-ipa", False, lambda _: object()
        )


def test_m14_p1a_staging_success_never_reaches_activation_mutations(
    tmp_path: Path,
) -> None:
    result, sentinel = _run_staging(tmp_path)
    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()


@pytest.mark.parametrize("fail_step", [1, 2, 3, 4, 5])
def test_m14_p1a_staging_failures_stop_before_activation_mutations(
    tmp_path: Path, fail_step: int,
) -> None:
    result, sentinel = _run_staging(tmp_path, fail_step=fail_step)
    assert result.returncode != 0
    assert not sentinel.exists()


def test_m14_p1a_staging_hash_failure_stops_before_activation(
    tmp_path: Path,
) -> None:
    result, sentinel = _run_staging(tmp_path, bad_digest=True)
    assert result.returncode != 0
    assert not sentinel.exists()


def test_m14_p1a_archive_validator_accepts_only_bounded_wheel_payload(
    tmp_path: Path,
) -> None:
    result = _run_archive_validator(tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("unsafe", ["traversal", "symlink", "url", "sdist"])
def test_m14_p1a_archive_validator_rejects_escape_and_unlocked_inputs(
    tmp_path: Path, unsafe: str,
) -> None:
    result = _run_archive_validator(tmp_path, unsafe=unsafe)
    assert result.returncode != 0


def test_m14_p1a_runtime_probe_accepts_exact_anonymous_contract(
    tmp_path: Path,
) -> None:
    result = _run_runtime_probe(tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report == {
        "checks": "passed",
        "commit": "a" * 40,
        "release_id": "release-1",
    }


@pytest.mark.parametrize(
    "failure",
    ["wrong_sha", "wrong_release", "disk_sha", "non_401", "malformed", "oversized"],
)
def test_m14_p1a_runtime_probe_rejects_identity_auth_and_body_failures(
    tmp_path: Path, failure: str,
) -> None:
    overrides: dict[str, tuple[int, dict[str, str], bytes]] = {}
    if failure == "wrong_sha":
        overrides["/api/version"] = (
            200,
            {"Cache-Control": "no-store"},
            b'{"status":"ok","release_id":"release-1","commit":"wrong","tag":null}',
        )
    elif failure == "wrong_release":
        overrides["/api/version"] = (
            200,
            {"Cache-Control": "no-store"},
            b'{"status":"ok","release_id":"wrong","commit":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","tag":null}',
        )
    elif failure == "non_401":
        overrides["/api/progress"] = (
            403, {}, b'{"detail":{"error":"AUTH_REQUIRED"}}'
        )
    elif failure == "malformed":
        overrides["/api/auth/me"] = (200, {}, b"{")
    else:
        overrides["/api/version"] = (
            200, {"Cache-Control": "no-store"}, b"{" + b" " * 65536
        )
    result = _run_runtime_probe(
        tmp_path, overrides, bad_revision=failure == "disk_sha"
    )
    assert result.returncode != 0
    assert "authenticated" not in result.stderr
    assert "AUTH_REQUIRED" not in result.stderr


def test_m14_p1a_acceptance_observes_restart_and_loopback_only(tmp_path: Path) -> None:
    result = _run_acceptance(tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "environment",
    [
        {"FAKE_SS_RC": "1"},
        {"FAKE_POINTER": "/opt/tiny-ipa/releases/wrong"},
        {"FAKE_LISTENERS": "LISTEN 0 128 0.0.0.0:18110 0.0.0.0:*"},
        {"FAKE_RESTART_RC": "1"},
        {"FAKE_RESTART_RC": "124"},
        {"FAKE_UNCHANGED": "1"},
        {"FAKE_PROBE_RC": "1"},
    ],
)
def test_m14_p1a_acceptance_rejects_listener_restart_and_probe_failures(
    tmp_path: Path, environment: dict[str, str],
) -> None:
    result = _run_acceptance(tmp_path, **environment)
    assert result.returncode != 0


def test_m14_p1a_withdrawal_reports_checked_port_closed(tmp_path: Path) -> None:
    result = _run_withdrawal(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "withdrawal-port-closed" in result.stdout


@pytest.mark.parametrize(
    "environment",
    [
        {"FAKE_SYSTEMCTL_RC": "1"},
        {"FAKE_STOP_RC": "1"},
        {"FAKE_SS_RC": "1"},
        {"FAKE_SS_OUTPUT": "LISTEN 0 128 127.0.0.1:18110 0.0.0.0:*"},
    ],
)
def test_m14_p1a_withdrawal_failures_never_report_success(
    tmp_path: Path, environment: dict[str, str],
) -> None:
    result = _run_withdrawal(tmp_path, **environment)
    assert result.returncode != 0
    assert "withdrawal-port-closed" not in result.stdout


def test_m14_jingyun_nginx_candidate_owns_only_subdomain_and_expected_routes() -> None:
    nginx = _text(NGINX)

    assert "server_name ipa.jingyun.bj.cn;" in nginx
    assert "server_name jingyun.bj.cn" not in nginx
    assert "root /var/www/tiny-ipa/current;" in nginx
    assert "ssl_certificate <HUMAN_PROVIDED_TLS_CERTIFICATE_PATH_FOR_IPA_JINGYUN>;" in nginx
    assert "ssl_certificate_key <HUMAN_PROVIDED_TLS_KEY_PATH_FOR_IPA_JINGYUN>;" in nginx
    assert "location = /api/health" in nginx
    assert "proxy_pass http://127.0.0.1:18110/api/health;" in nginx
    assert "location = /api/version" in nginx
    assert "proxy_pass http://127.0.0.1:18110/api/version;" in nginx
    assert 'add_header Cache-Control "no-store" always;' in nginx
    assert "location /api/" in nginx
    assert "proxy_pass http://127.0.0.1:18110/api/;" in nginx
    assert "location ^~ /audio/" in nginx
    assert "alias /var/lib/tiny-ipa/audio/;" in nginx
    assert "try_files $uri $uri/ /index.html;" in nginx
    assert "listen 80" not in nginx
    assert "default_server" not in nginx

    for forbidden in FORBIDDEN_CONFIG_REFERENCES:
        assert forbidden not in nginx


def test_m14_jingyun_env_example_is_non_secret_and_matches_runtime_contract() -> None:
    env = _text(ENV_EXAMPLE)

    expected_lines = {
        "TINY_IPA_ENV=production",
        "TINY_IPA_DB_PATH=/var/lib/tiny-ipa/tiny-ipa.sqlite",
        "TINY_IPA_SESSION_SECRET=<HUMAN_PROVISIONED_TINY_IPA_SESSION_SECRET>",
        "TINY_IPA_ALLOWED_ORIGINS=https://ipa.jingyun.bj.cn",
        "TINY_IPA_COOKIE_SECURE=true",
        "TINY_IPA_COOKIE_SAMESITE=lax",
        "TINY_IPA_AUDIO_DIR=/var/lib/tiny-ipa/audio",
        "TINY_IPA_RELEASE_ID=<INTENDED_GIT_COMMIT_OR_TAG_RELEASE_ID>",
        "TINY_IPA_RELEASE_COMMIT=<INTENDED_GITHUB_COMMIT_SHA>",
        "TINY_IPA_RELEASE_TAG=<OPTIONAL_SIGNED_OR_ANNOTATED_GIT_TAG>",
    }

    assert expected_lines.issubset(set(env.splitlines()))
    assert "TINY_IPA_SESSION_SECRET=" in env
    assert "TINY_IPA_CORS_ORIGINS" not in env
    assert "TINY_IPA_REVISION_PATH" not in env
    assert "http://" not in env
    assert "*" not in env


def test_m14_jingyun_revision_candidate_records_non_secret_release_identity() -> None:
    revision = _text(REVISION)

    assert "release_id=<INTENDED_GIT_COMMIT_OR_TAG_RELEASE_ID>" in revision
    assert "commit=<INTENDED_GITHUB_COMMIT_SHA>" in revision
    assert "tag=<OPTIONAL_SIGNED_OR_ANNOTATED_GIT_TAG>" in revision
    assert "created_at=<UTC_RELEASE_ARTIFACT_TIMESTAMP>" in revision
    assert "secret" not in revision.lower()


def test_m14_jingyun_plans_preserve_deployment_and_backup_stop_conditions() -> None:
    deployment = " ".join(_text(DEPLOYMENT_PLAN).split())
    backup = " ".join(_text(BACKUP_PLAN).split())

    for phrase in (
        "Record pre-state evidence and Xue Tu Zhi Ban baseline health",
        "Record the intended GitHub commit/tag and verified first-install "
        "or upgrade recovery record",
        "Generate `REVISION` in the candidate release directory",
        "Verify port `18110` is still free",
        "Validate the Nginx candidate without reload",
        "Compare local/GitHub/REVISION/live `/api/version` release identity",
        "Tiny IPA success never substitutes",
        "does not authorize applying any artifact",
        "A first installation instead requires verified absence",
    ):
        assert phrase in deployment

    for phrase in (
        "#280 proved only a temporary fixture backup/restore method",
        "/var/backups/tiny-ipa/<timestamp>/tiny-ipa.sqlite.backup",
        "/opt/tiny-ipa/current/REVISION",
        "live `/api/version` identity",
        "/var/lib/tiny-ipa/restore-candidates/<timestamp>/tiny-ipa.sqlite",
        "never the only known-good production database",
        "Retention cleanup is not part of this candidate",
    ):
        assert phrase in backup


@pytest.mark.parametrize(
    ("old", "new", "failure"),
    [
        ("127.0.0.1:18110", "127.0.0.1:8010", "approved namespace missing"),
        ("/api/version", "/api/build-info", "approved namespace missing"),
        (
            "<HUMAN_APPROVED_BACKUP_OWNER>",
            "ubuntu",
            "Human placeholder missing",
        ),
        ("CANDIDATE - DO NOT APPLY", "APPLY", "candidate safety marker missing"),
        ("TINY_IPA_AUDIO_DIR", "TINY_IPA_AUDIO_ROOT", "unsupported audio variable"),
    ],
)
def test_m14_jingyun_boundary_check_detects_namespace_or_placeholder_drift(
    old: str,
    new: str,
    failure: str,
) -> None:
    bad_text = _all_candidate_text().replace(old, new)

    with pytest.raises(AssertionError, match=failure):
        _assert_bundle_text(bad_text)


def _records(path: Path) -> list[dict]:
    return json.loads(re.search(r"```json\n(.*?)\n```", _text(path), re.S).group(1))


def _assert_history(record: dict) -> None:
    assert record["kind"] in {"first_install", "upgrade"}
    if record["kind"] == "first_install":
        assert record["pre_state"] == "verified_absent"
        assert record["previous_release"] == "none"
    else:
        assert record["pre_state"] == "verified_existing"
        assert record["previous_release"] not in {None, "", "none", "unknown"}


def _assert_recovery_record(record: dict) -> None:
    _assert_history(record)
    assert record["recovery_owner"] not in {None, "", "unknown"}
    assert record["recovery_scope"] == "tiny_ipa_only"
    assert record["preserve_data"] is True
    assert record["delete"] is False
    assert record["in_place_restore"] is False
    assert record["phase_authorization_required"] is True
    assert record["version_stages"] == [
        "loopback_after_backend_start", "https_after_public_activation"
    ]
    if record["kind"] == "first_install":
        assert record["backend_pointer"] is None
        assert record["frontend_pointer"] is None
        assert record["previous_env_identity"] is None
        assert record["recovery_plan"] == "withdraw_this_trial_activation"
    else:
        release = record["previous_release"]
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", release)
        assert record["backend_pointer"] == f"/opt/tiny-ipa/releases/{release}"
        assert record["frontend_pointer"] == f"/var/www/tiny-ipa/releases/{release}"
        assert record["previous_env_identity"] == release
        assert record["db_compatibility"] == "verified"
        assert record["recovery_plan"] == "restore_backend_frontend_env_identity"


def _assert_backup_record(record: dict) -> None:
    _assert_history(record)
    assert record["current_identity_matches"] is True
    assert record["source"] == "/var/lib/tiny-ipa/tiny-ipa.sqlite"
    assert record["integrity"] == "ok"
    for field in ("timestamp", "checksum", "backup_owner", "retention"):
        assert record[field] not in {None, "", "unknown"}


def test_documented_first_install_and_upgrade_records_are_valid() -> None:
    recovery = _records(DEPLOYMENT_PLAN)
    backup = _records(BACKUP_PLAN)
    assert [r["kind"] for r in recovery] == ["first_install", "upgrade"]
    assert [r["kind"] for r in backup] == ["first_install", "upgrade"]
    for record in recovery:
        _assert_recovery_record(record)
    for record in backup:
        _assert_backup_record(record)


@pytest.mark.parametrize(
    ("index", "field", "value"),
    [
        (0, "pre_state", "unknown"),
        (0, "pre_state", "partial_install"),
        (0, "previous_release", "unknown"),
        (0, "backend_pointer", "/opt/tiny-ipa/current"),
        (0, "recovery_owner", ""),
        (0, "recovery_plan", ""),
        (0, "recovery_scope", "xuetuzhiban"),
        (0, "preserve_data", False),
        (0, "delete", True),
        (0, "in_place_restore", True),
        (0, "phase_authorization_required", False),
        (0, "version_stages", ["https_before_public_activation"]),
        (0, "version_stages", ["loopback_after_backend_start"]),
        (1, "backend_pointer", None),
        (1, "frontend_pointer", None),
        (1, "previous_env_identity", "different-release"),
        (1, "previous_release", "none"),
        (1, "db_compatibility", "unknown"),
        (1, "recovery_scope", "shared_nginx_defaults"),
    ],
)
def test_lifecycle_validator_rejects_unsafe_mutations(index, field, value) -> None:
    record = _records(DEPLOYMENT_PLAN)[index]
    record[field] = value
    with pytest.raises(AssertionError):
        _assert_recovery_record(record)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pre_state", "unknown"),
        ("previous_release", ""),
        ("current_identity_matches", False),
        ("source", "/opt/hermes/private.sqlite"),
        ("integrity", "failed"),
        ("backup_owner", ""),
        ("retention", "unknown"),
    ],
)
def test_first_release_backup_rejects_missing_or_unsafe_evidence(field, value) -> None:
    record = _records(BACKUP_PLAN)[0]
    record[field] = value
    with pytest.raises(AssertionError):
        _assert_backup_record(record)
