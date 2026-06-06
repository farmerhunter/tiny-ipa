"""Question generation for practice items.

For each session item, generates a ``choose_ipa`` question with the correct
IPA and plausible distractors drawn from other words.
"""

import random
from typing import Dict, List, Optional

from app.models import Word


def generate_question(
    word: Word,
    accent: str = "US",
    *,
    distractor_pool: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> dict:
    """Build a ``choose_ipa`` question dict for a word.

    Args:
        word: The target word (must have ipa_us for accent="US").
        accent: "US" or "UK" — which IPA to use as the correct answer.
        distractor_pool: Pre-built pool of IPA strings to draw distractors
                         from. If omitted, no distractors are generated and
                         a placeholder is used (caller should supply a pool
                         for real use).
        seed: Shuffle seed so the same word gets the same choices on repeat
              calls.

    Returns:
        A question dict matching the API contract:
        ``{"type": "choose_ipa", "prompt": "...", "choices": [...]}``
    """
    correct = word.ipa_us if accent.upper() == "US" else (word.ipa_uk or word.ipa_us)

    choices = [correct]
    if distractor_pool:
        rng = random.Random(seed)
        candidates = [ipa for ipa in distractor_pool if ipa != correct]
        rng.shuffle(candidates)
        choices.extend(candidates[:3])
        rng.shuffle(choices)

    return {
        "type": "choose_ipa",
        "prompt": "Which IPA matches this word?",
        "choices": choices,
    }
