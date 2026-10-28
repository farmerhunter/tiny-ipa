import pytest

from app.models import Word
from app.services.grading import grade_attempt
from app.services.questions import generate_question


def word(ipa):
    return Word(
        id="target",
        word="target",
        level="beginner",
        ipa_us=ipa,
        phoneme_tags_us=["/k/"],
        content_status="core_selected",
        ipa_uk="/UK-target/",
    )


def test_counterpart_survives_filler_pressure_in_both_directions_and_is_stable():
    pool = [f"/filler-{index}/" for index in range(40)]
    for correct, partner in [("/keɪm/", "/geɪm/"), ("/geɪm/", "/keɪm/")]:
        target = word(correct)
        for seed in range(32):
            question = generate_question(
                target, distractor_pool=pool, contrast_ipa=partner, seed=seed
            )
            assert {correct, partner} <= set(question["choices"])
            assert len(question["choices"]) == len(set(question["choices"])) == 4
            assert (
                generate_question(target, distractor_pool=pool, contrast_ipa=partner, seed=seed)
                == question
            )
        ordinary = [
            generate_question(target, distractor_pool=pool + [partner], seed=seed)
            for seed in range(16)
        ]
        assert any(partner not in q["choices"] for q in ordinary)


@pytest.mark.parametrize(
    "pool, count", [([], 2), (["/k/", "/g/", "/g/", "", " "], 2), (["/x/", "/x/", "/k/"], 3)]
)
def test_sparse_pool_uses_only_real_unique_choices(pool, count):
    choices = generate_question(word("/k/"), contrast_ipa="/g/", distractor_pool=pool)["choices"]
    assert {"/k/", "/g/"} <= set(choices)
    assert len(choices) == len(set(choices)) == count


@pytest.mark.parametrize("partner", ["", " ", "/k/", " /k/ "])
def test_invalid_counterpart_is_not_silently_replaced(partner):
    with pytest.raises(ValueError, match="distinct counterpart"):
        generate_question(word("/k/"), contrast_ipa=partner, distractor_pool=["/random/"])


def test_active_accent_uses_uk_correct_and_counterpart():
    question = generate_question(
        word("/US-target/"), accent="UK", contrast_ipa="/UK-partner/", distractor_pool=["/filler/"]
    )
    assert {"/UK-target/", "/UK-partner/"} <= set(question["choices"])
    assert "/US-target/" not in question["choices"]


def test_option_uniqueness_matches_grading_and_keeps_only_one_correct_choice():
    choices = generate_question(
        word(" /k/ "),
        contrast_ipa=" /g/ ",
        distractor_pool=["/k/", " /k/ ", "/g/", " /g/ ", "/x/", " /x/ "],
    )["choices"]
    assert len({value.strip() for value in choices}) == len(choices) == 3
    assert sum(grade_attempt(value, " /k/ ") for value in choices) == 1
    assert " /g/ " in choices
