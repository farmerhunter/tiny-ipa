from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "05-data-api-contracts.md"


def _contract_text() -> str:
    return DOC.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "phrase",
    [
        "personal-VPS data-isolation boundary",
        "Production learner-data endpoints cannot silently use `default`",
        "server-side opaque session identifier",
        "HttpOnly",
        "Secure cookie",
        "SameSite=Lax",
        "wildcard origins are not",
        "Origin/Referer check",
        "Human-gated and must start with a dry-run report",
        "#27 / M14 VPS deployment prerequisite evidence",
    ],
)
def test_m12_auth_contract_covers_required_boundary_phrases(phrase: str) -> None:
    assert phrase in _contract_text()


@pytest.mark.parametrize(
    "endpoint",
    [
        "GET /api/health",
        "POST /api/auth/login",
        "POST /api/auth/logout",
        "GET /api/auth/me",
        "GET /api/today",
        "POST /api/practice/next-normal",
        "POST /api/practice/abandon-current-and-next",
        "POST /api/practice/focus",
        "POST /api/practice/clear-focus",
        "POST /api/review/current-group",
        "POST /api/review/recent-mistakes",
        "POST /api/attempt",
        "GET /api/progress",
        "GET /api/settings",
        "PUT /api/settings",
    ],
)
def test_m12_endpoint_auth_matrix_lists_runtime_routes(endpoint: str) -> None:
    assert endpoint in _contract_text()


@pytest.mark.parametrize("issue", ["#239", "#240", "#241", "#242", "#243", "#244"])
def test_m12_child_issue_test_matrix_is_present(issue: str) -> None:
    assert issue in _contract_text()


@pytest.mark.parametrize(
    "scope",
    [
        "settings",
        "daily_sessions",
        "session_items",
        "attempts",
        "phoneme_stats",
        "review/focus state",
        "words",
        "phonemes",
        "static audio assets",
    ],
)
def test_m12_data_scope_matrix_covers_runtime_and_global_data(scope: str) -> None:
    assert scope in _contract_text()
