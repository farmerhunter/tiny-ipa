from pathlib import Path

import pytest


DOC = Path(__file__).resolve().parents[2] / "docs" / "05-data-api-contracts.md"


def _contract_text() -> str:
    return DOC.read_text(encoding="utf-8")


def _normalized_contract_text() -> str:
    return " ".join(_contract_text().split())


@pytest.mark.parametrize(
    "phrase",
    [
        "M13 practice question contract",
        "`choose_ipa` remains the compatibility baseline",
        "`choose_word` is the first reverse-recognition expansion",
        "`type_word` is deferred",
        "`phoneme_stats` continuity is preserved",
        "not from the frontend-visible answer string",
        "server-side canonical answer for feedback",
        "Unsupported `question_type` values fail closed",
    ],
)
def test_m13_question_contract_covers_core_boundaries(phrase: str) -> None:
    assert phrase in _normalized_contract_text()


@pytest.mark.parametrize(
    "question_type",
    ["choose_ipa", "choose_word", "type_word"],
)
def test_m13_question_taxonomy_lists_supported_and_deferred_modes(
    question_type: str,
) -> None:
    assert question_type in _normalized_contract_text()


@pytest.mark.parametrize(
    "policy_phrase",
    [
        "exact same active-accent IPA",
        "`new` / `knew`",
        "`sun` / `son`",
        "`see` / `sea`",
        "accepted_answers source",
        "normalization rules",
        "spelling variant policy",
        "must not be exposed as a learner-selectable runtime mode",
    ],
)
def test_m13_type_word_homophone_policy_is_explicit(policy_phrase: str) -> None:
    assert policy_phrase in _normalized_contract_text()


@pytest.mark.parametrize(
    "behavior",
    [
        "mistake_review -> stays choose_ipa",
        "weak_focus -> stays choose_ipa",
        "minimal/sound compare -> unchanged specialty behavior",
    ],
)
def test_m13_review_focus_first_slice_behavior_is_conservative(
    behavior: str,
) -> None:
    assert behavior in _normalized_contract_text()


@pytest.mark.parametrize(
    "issue",
    ["#261", "#260", "#259", "#262", "#264", "#263"],
)
def test_m13_child_issue_test_matrix_is_present(issue: str) -> None:
    assert issue in _normalized_contract_text()
