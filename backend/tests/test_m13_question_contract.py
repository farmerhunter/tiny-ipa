import json
from collections import defaultdict
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "05-data-api-contracts.md"
CONTENT_ROOT = Path(__file__).resolve().parents[2] / "content"


def _contract_text() -> str:
    return DOC.read_text(encoding="utf-8")


def _normalized_contract_text() -> str:
    return " ".join(_contract_text().split())


def _load_content_words() -> list[tuple[str, dict]]:
    words: list[tuple[str, dict]] = []
    for level, filename in [
        ("entry", "core_300_words.json"),
        ("mid", "core_1000_words.json"),
    ]:
        data = json.loads((CONTENT_ROOT / filename).read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("words", [])
        words.extend((level, row) for row in rows)
    return words


def _same_level_same_ipa_groups(accent: str) -> dict[tuple[str, str], set[str]]:
    field = "ipa_us" if accent == "US" else "ipa_uk"
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for level, row in _load_content_words():
        ipa = (row.get(field) or "").strip()
        word = (row.get("word") or "").strip().lower()
        if ipa and word:
            groups[(level, ipa)].add(word)
    return {
        key: values
        for key, values in groups.items()
        if len(values) > 1
    }


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
    "contract_phrase",
    [
        "server-side accepted-answer snapshot",
        "accepted_answers storage",
        "Unicode NFKC normalization",
        "no fuzzy typo matching in the MVP",
        "exclude that row from type_word candidate generation",
        "no production type_word exposure in the current M13 MVP",
        "normal-only type_word behind an explicit challenge-mode selector",
    ],
)
def test_m13_type_word_accepted_answer_contract_is_actionable(
    contract_phrase: str,
) -> None:
    assert contract_phrase in _normalized_contract_text()


def test_current_content_has_same_ipa_type_word_ambiguity_examples() -> None:
    us_groups = _same_level_same_ipa_groups("US")
    uk_groups = _same_level_same_ipa_groups("UK")

    assert len(us_groups) >= 11
    assert len(uk_groups) >= 7
    assert {"new", "knew"} <= us_groups[("entry", "/ˈnju/")]
    assert {"see", "sea"} <= us_groups[("mid", "/ˈsi/")]
    assert {"buy", "bye"} <= us_groups[("mid", "/ˈbaɪ/")]
    assert {"honor", "honour"} <= us_groups[("mid", "/ˈɑnɝ/")]


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
