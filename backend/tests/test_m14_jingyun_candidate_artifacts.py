from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIR = ROOT / "deploy" / "jingyun"
SYSTEMD = CANDIDATE_DIR / "tiny-ipa-api.service.candidate"
NGINX = CANDIDATE_DIR / "ipa.jingyun.bj.cn.nginx.candidate"
ENV_EXAMPLE = CANDIDATE_DIR / "tiny-ipa.production.env.example"
DEPLOYMENT_PLAN = ROOT / "docs" / "15-m14-jingyun-candidate-deployment-plan.md"
BACKUP_PLAN = ROOT / "docs" / "16-m14-jingyun-production-backup-restore-plan.md"

REQUIRED_FILES = (
    CANDIDATE_DIR / "CANDIDATE-README.md",
    SYSTEMD,
    NGINX,
    ENV_EXAMPLE,
    DEPLOYMENT_PLAN,
    BACKUP_PLAN,
)

APPROVED_NAMESPACE = (
    "ipa.jingyun.bj.cn",
    "/opt/tiny-ipa",
    "/var/www/tiny-ipa",
    "/var/lib/tiny-ipa",
    "/var/backups/tiny-ipa",
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

    assert "User=<HUMAN_APPROVED_TINY_IPA_SERVICE_USER>" in unit
    assert "Group=<HUMAN_APPROVED_TINY_IPA_SERVICE_GROUP>" in unit
    assert "User=root" not in unit
    assert "Group=root" not in unit
    assert "WorkingDirectory=/opt/tiny-ipa/current/backend" in unit
    assert "EnvironmentFile=<HUMAN_OWNED_TINY_IPA_ENV_FILE>" in unit
    assert "--host 127.0.0.1 --port 18110" in unit
    assert "ReadWritePaths=/var/lib/tiny-ipa" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit

    assert re.findall(r"--port\s+(\d+)", unit) == ["18110"]
    for forbidden in FORBIDDEN_CONFIG_REFERENCES:
        assert forbidden not in unit


def test_m14_jingyun_nginx_candidate_owns_only_subdomain_and_expected_routes() -> None:
    nginx = _text(NGINX)

    assert "server_name ipa.jingyun.bj.cn;" in nginx
    assert "server_name jingyun.bj.cn" not in nginx
    assert "root /var/www/tiny-ipa/current;" in nginx
    assert "ssl_certificate <HUMAN_PROVIDED_TLS_CERTIFICATE_PATH_FOR_IPA_JINGYUN>;" in nginx
    assert "ssl_certificate_key <HUMAN_PROVIDED_TLS_KEY_PATH_FOR_IPA_JINGYUN>;" in nginx
    assert "location = /api/health" in nginx
    assert "proxy_pass http://127.0.0.1:18110/api/health;" in nginx
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
    }

    assert expected_lines.issubset(set(env.splitlines()))
    assert "TINY_IPA_SESSION_SECRET=" in env
    assert "TINY_IPA_CORS_ORIGINS" not in env
    assert "http://" not in env
    assert "*" not in env


def test_m14_jingyun_plans_preserve_deployment_and_backup_stop_conditions() -> None:
    deployment = " ".join(_text(DEPLOYMENT_PLAN).split())
    backup = " ".join(_text(BACKUP_PLAN).split())

    for phrase in (
        "Record pre-state evidence and Xue Tu Zhi Ban baseline health",
        "Verify port `18110` is still free",
        "Validate the Nginx candidate without reload",
        "Tiny IPA success never substitutes",
        "does not authorize applying any artifact",
    ):
        assert phrase in deployment

    for phrase in (
        "#280 proved only a temporary fixture backup/restore method",
        "/var/backups/tiny-ipa/<timestamp>/tiny-ipa.sqlite.backup",
        "/var/lib/tiny-ipa/restore-candidates/<timestamp>/tiny-ipa.sqlite",
        "never the only known-good production database",
        "Retention cleanup is not part of this candidate",
    ):
        assert phrase in backup


@pytest.mark.parametrize(
    ("old", "new", "failure"),
    [
        ("127.0.0.1:18110", "127.0.0.1:8010", "approved namespace missing"),
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
