from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "06-epic-roadmap.md"


def _contract_text() -> str:
    return " ".join(DOC.read_text(encoding="utf-8").split())


@pytest.mark.parametrize(
    "phrase",
    [
        "Deployment Target and Runtime Config Contract",
        "Human input checklist",
        "Runtime config variables",
        "Production config must fail closed",
        "Optional VPS inventory plan",
        "Forbidden in #276",
        "Deployment verification matrix",
    ],
)
def test_m14_deployment_contract_sections_exist(phrase: str) -> None:
    assert phrase in _contract_text()


@pytest.mark.parametrize(
    "runtime_variable",
    [
        "TINY_IPA_ENV",
        "TINY_IPA_DB_PATH",
        "TINY_IPA_SESSION_SECRET",
        "TINY_IPA_COOKIE_SECURE",
        "TINY_IPA_ALLOWED_ORIGINS",
        "VITE_API_BASE_URL",
        "TINY_IPA_AUDIO_ROOT",
        "TINY_IPA_STATIC_ROOT",
        "TINY_IPA_BACKEND_PORT",
        "TINY_IPA_LOG_DIR",
        "TINY_IPA_HEALTH_PATH",
    ],
)
def test_m14_runtime_config_inventory_covers_required_variables(
    runtime_variable: str,
) -> None:
    assert runtime_variable in _contract_text()


@pytest.mark.parametrize(
    "boundary",
    [
        "production without TINY_IPA_SESSION_SECRET -> refuse startup",
        "production with TINY_IPA_COOKIE_SECURE=false -> refuse startup",
        "production with wildcard credentialed CORS -> refuse startup",
        "production with relative or repo-local DB path -> refuse startup",
        "ssh to the VPS without explicit Human authorization",
        "private SQLite read, copy, migration, restore, or mutation",
    ],
)
def test_m14_deployment_contract_fails_closed_for_production_boundaries(
    boundary: str,
) -> None:
    assert boundary in _contract_text()


@pytest.mark.parametrize("child_issue", ["#277", "#278", "#279", "#280", "#281", "#282"])
def test_m14_deployment_contract_covers_follow_up_verification_matrix(
    child_issue: str,
) -> None:
    assert child_issue in _contract_text()
