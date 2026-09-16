from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "development.md"
STATUS_TAXONOMY = (
    "local-passed",
    "pending-human-input",
    "vps-passed",
    "blocked",
)
REQUIRED_REAL_HOST_ROWS = (
    "| HTTPS/domain |",
    "| frontend load |",
    "| health |",
    "| authenticated login |",
    "| Settings save |",
    "| Today start/resume |",
    "| audio/static |",
    "| service restart |",
)


def _checklist_text() -> str:
    document = DOC.read_text(encoding="utf-8")
    start = document.index("## M14 deployment smoke, rollback, and evidence checklist")
    return " ".join(document[start:].split())


def _assert_exact_status_taxonomy(checklist: str) -> None:
    status_line = checklist.split("status: ", 1)[1].split(" evidence:", 1)[0]
    assert tuple(status_line.split(" | ")) == STATUS_TAXONOMY


def _assert_required_real_host_rows(checklist: str) -> None:
    for row in REQUIRED_REAL_HOST_ROWS:
        assert row in checklist


def test_m14_checklist_has_distinct_local_human_and_vps_evidence_states() -> None:
    checklist = _checklist_text()

    _assert_exact_status_taxonomy(checklist)

    for phrase in (
        (
            "not evidence that a VPS, systemd unit, Nginx, TLS, backup artifact, "
            "or restore has been validated"
        ),
        "a missing row is a blocker",
        "Local/disposable preflight: executable now",
        "Human-gated VPS preflight inputs",
        "Human-gated real-host smoke sequence",
    ):
        assert phrase in checklist


def test_m14_checklist_integrates_accepted_child_contracts() -> None:
    checklist = _checklist_text()

    for phrase in (
        "#277 production checks",
        "#278 owns the service/environment template",
        "#279 owns the placeholder reverse-proxy contract",
        "#280 is temporary-only proof",
        "VITE_API_BASE=/api",
        "TINY_IPA_AUDIO_DIR",
        "`TINY_IPA_AUDIO_ROOT` is not a supported alias",
        "/api/health",
    ):
        assert phrase in checklist


def test_m14_checklist_has_each_required_real_host_smoke_row() -> None:
    _assert_required_real_host_rows(_checklist_text())


def test_m14_checklist_contract_rejects_status_and_row_regressions() -> None:
    checklist = _checklist_text()

    with pytest.raises(AssertionError):
        _assert_exact_status_taxonomy(checklist.replace(" | blocked", "", 1))

    for row in REQUIRED_REAL_HOST_ROWS:
        with pytest.raises(AssertionError):
            _assert_required_real_host_rows(checklist.replace(row, "", 1))


def test_m14_checklist_fails_closed_on_backup_and_rollback_boundaries() -> None:
    checklist = _checklist_text()

    for phrase in (
        "not a production restore",
        "Stop and escalate to Architect/Human owner",
        "Do not restore in place",
        "could overwrite the only known-good private database",
        "#282 alone decides",
    ):
        assert phrase in checklist
