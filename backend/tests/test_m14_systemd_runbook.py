from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "development.md"


def _runbook_text() -> str:
    document = DOC.read_text(encoding="utf-8")
    start = document.index("## M14 VPS backend systemd runbook")
    return " ".join(document[start:].split())


@pytest.mark.parametrize(
    "phrase",
    [
        "Human inputs and stop conditions",
        "Repo-safe local preflight",
        "systemd unit template shape",
        "Environment-file template shape",
        "Authorized-host checks and failure diagnosis",
        "ExecStart=<app-root>/backend/.venv/bin/uvicorn app.main:app",
        "TINY_IPA_SESSION_SECRET=<Human-provisioned secret>",
        "TINY_IPA_ALLOWED_ORIGINS=https://<public-hostname>",
        "curl --fail --silent --show-error http://127.0.0.1:<backend-port>/api/health",
    ],
)
def test_m14_systemd_runbook_covers_service_contract(phrase: str) -> None:
    assert " ".join(phrase.split()) in _runbook_text()


@pytest.mark.parametrize(
    "boundary",
    [
        "does not authorize SSH access",
        "must not be copied to `/etc/systemd/system/` without a later Human gate",
        "#279 owns reverse-proxy routing",
        "#280 owns backup and restore",
        "#281 owns the end-to-end smoke/rollback checklist",
        "Never commit it",
        "do not generate its secret",
    ],
)
def test_m14_systemd_runbook_preserves_human_and_child_issue_boundaries(
    boundary: str,
) -> None:
    assert " ".join(boundary.split()) in _runbook_text()
