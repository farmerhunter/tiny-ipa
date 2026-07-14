from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "development.md"


def _checklist_text() -> str:
    document = DOC.read_text(encoding="utf-8")
    start = document.index("## M14 deployment smoke, rollback, and evidence checklist")
    return " ".join(document[start:].split())


def test_m14_checklist_has_distinct_local_human_and_vps_evidence_states() -> None:
    checklist = _checklist_text()

    for phrase in (
        (
            "not evidence that a VPS, systemd unit, Nginx, TLS, backup artifact, "
            "or restore has been validated"
        ),
        "local-passed",
        "pending-human-input",
        "vps-passed",
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
        "authenticated login",
        "Today start/resume",
        "audio/static",
        "service restart",
    ):
        assert phrase in checklist


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
