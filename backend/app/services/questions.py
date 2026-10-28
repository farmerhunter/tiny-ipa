"""Question generation for practice items."""

import random
from typing import List, Optional

from app.models import Word


def generate_question(
    word: Word,
    accent: str = "US",
    *,
    distractor_pool: Optional[List[str]] = None,
    question_type: str = "choose_ipa",
    seed: Optional[int] = None,
    contrast_ipa: Optional[str] = None,
) -> dict:
    """Build a question dict for a word using the persisted question type."""
    if question_type == "choose_word":
        return _generate_choose_word_question(
            word,
            accent=accent,
            distractor_pool=distractor_pool,
            seed=seed,
        )
    if question_type == "choose_ipa":
        return _generate_choose_ipa_question(
            word,
            accent=accent,
            distractor_pool=distractor_pool,
            seed=seed,
            contrast_ipa=contrast_ipa,
        )
    raise ValueError(f"Unsupported question_type: {question_type}")


def _active_ipa(word: Word, accent: str) -> str:
    return word.ipa_us if accent.upper() == "US" else (word.ipa_uk or word.ipa_us)


def _shuffled_choices(
    correct: str,
    distractor_pool: Optional[List[str]],
    seed: Optional[int],
) -> list[str]:
    choices = [correct]
    if not distractor_pool:
        return choices

    rng = random.Random(seed)
    candidates = [value for value in distractor_pool if value and value != correct]
    rng.shuffle(candidates)
    choices.extend(candidates[:3])
    rng.shuffle(choices)
    return choices


def _generate_choose_ipa_question(
    word: Word,
    accent: str,
    *,
    distractor_pool: Optional[List[str]],
    seed: Optional[int],
    contrast_ipa: Optional[str] = None,
) -> dict:
    correct = _active_ipa(word, accent)
    if contrast_ipa is not None:
        if (
            not correct.strip()
            or not contrast_ipa.strip()
            or contrast_ipa.strip() == correct.strip()
        ):
            raise ValueError("Sound Compare requires a distinct counterpart IPA")
        rng = random.Random(seed)
        fillers = sorted(
            {value.strip() for value in (distractor_pool or []) if value.strip()}
            - {correct.strip(), contrast_ipa.strip()}
        )
        rng.shuffle(fillers)
        choices = [correct, contrast_ipa, *fillers[:2]]
        rng.shuffle(choices)
    else:
        choices = _shuffled_choices(correct, distractor_pool, seed)
    return {
        "type": "choose_ipa",
        "prompt": "Which IPA matches this word?",
        "choices": choices,
    }


def _generate_choose_word_question(
    word: Word,
    accent: str,
    *,
    distractor_pool: Optional[List[str]],
    seed: Optional[int],
) -> dict:
    return {
        "type": "choose_word",
        "prompt": "Which word matches this IPA?",
        "display_ipa": _active_ipa(word, accent),
        "choices": _shuffled_choices(word.word, distractor_pool, seed),
    }
