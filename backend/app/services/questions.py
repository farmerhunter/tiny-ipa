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
) -> dict:
    correct = _active_ipa(word, accent)
    return {
        "type": "choose_ipa",
        "prompt": "Which IPA matches this word?",
        "choices": _shuffled_choices(correct, distractor_pool, seed),
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
