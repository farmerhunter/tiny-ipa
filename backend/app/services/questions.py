"""Question generation for IPA practice.

Generates choose-IPA questions with contrast-aware distractors.
Distractors are built by substituting phonemes that Chinese learners
commonly confuse, rather than random IPA strings.
"""

import re
from typing import List


# Common phoneme confusions for Chinese learners.
# Each entry is (correct_phoneme, common_confusion).
CONFUSIONS = [
    ("/ɪ/", "/iː/"),
    ("/iː/", "/ɪ/"),
    ("/æ/", "/e/"),
    ("/e/", "/æ/"),
    ("/ʊ/", "/uː/"),
    ("/uː/", "/ʊ/"),
    ("/θ/", "/s/"),
    ("/ð/", "/z/"),
    ("/ʃ/", "/s/"),
    ("/s/", "/ʃ/"),
    ("/tʃ/", "/ʃ/"),
    ("/v/", "/w/"),
    ("/w/", "/v/"),
    ("/r/", "/l/"),
    ("/l/", "/r/"),
    ("/ŋ/", "/n/"),
    ("/ʌ/", "/ɑ/"),
    ("/ɑ/", "/ʌ/"),
    ("/ɔ/", "/oʊ/"),
]


def _strip_slashes_and_stress(ipa: str) -> str:
    """Remove / / delimiters and primary/secondary stress marks from an IPA string."""
    raw = ipa.strip()
    if raw.startswith("/") and raw.endswith("/"):
        raw = raw[1:-1]
    raw = raw.replace("ˈ", "").replace("ˌ", "")
    return raw


def _phonemes_to_raw_ipa(phoneme_tags: List[str]) -> str:
    """Join phoneme tags into a raw IPA string (no slashes, no stress)."""
    return "".join(tag.strip("/") for tag in phoneme_tags)


def _apply_confusion(raw_ipa: str, phoneme_tags: List[str]) -> List[str]:
    """Generate confused IPA strings by substituting one phoneme at a time."""
    distractors = set()

    for i, tag in enumerate(phoneme_tags):
        for correct, confused in CONFUSIONS:
            if tag == correct:
                # Build a new IPA with this one phoneme swapped
                new_tags = list(phoneme_tags)
                new_tags[i] = confused
                new_ipa = _phonemes_to_raw_ipa(new_tags)
                distractors.add(f"/{new_ipa}/")
                break

    # Remove the correct answer from distractors
    correct_ipa = f"/{raw_ipa}/"
    distractors.discard(correct_ipa)

    return list(distractors)


def generate_choose_ipa_question(word: dict) -> dict:
    """
    Generate a choose-IPA question for a given word.

    Returns a question dict with:
    - type: "choose_ipa"
    - prompt: question text
    - choices: list of 3 IPA strings (correct + 2 distractors)
    - correct: the correct IPA for server-side grading
    """
    ipa_us = word.get("ipa_us", "")
    phoneme_tags = word.get("phoneme_tags_us", [])

    raw_ipa = _strip_slashes_and_stress(ipa_us)
    correct_ipa = f"/{raw_ipa}/"

    distractors = _apply_confusion(raw_ipa, phoneme_tags)

    # If we don't have enough distractors, generate fallbacks by
    # using UK IPA if it differs, or vowel length swapping
    if len(distractors) < 2:
        ipa_uk = word.get("ipa_uk", "")
        if ipa_uk:
            uk_raw = _strip_slashes_and_stress(ipa_uk)
            uk_ipa = f"/{uk_raw}/"
            if uk_ipa != correct_ipa:
                distractors.append(uk_ipa)

    # Fallback: common vowel length alternations
    if len(distractors) < 2:
        for tag in phoneme_tags:
            if tag == "/ɪ/":
                fb = f"/{raw_ipa.replace('ɪ', 'i')}/"
                if fb != correct_ipa and fb not in distractors:
                    distractors.append(fb)
            elif tag == "/i/":
                fb = f"/{raw_ipa.replace('i', 'ɪ')}/"
                if fb != correct_ipa and fb not in distractors:
                    distractors.append(fb)
            elif tag == "/ʊ/":
                fb = f"/{raw_ipa.replace('ʊ', 'u')}/"
                if fb != correct_ipa and fb not in distractors:
                    distractors.append(fb)

    # Take up to 2 distractors
    chosen = list(distractors)[:2]

    # Pad with a same-length fallback if still short
    while len(chosen) < 2:
        # Generate a simple substitution
        fallback = raw_ipa.replace("ɪ", "i").replace("æ", "e").replace("ʊ", "u")
        fb_ipa = f"/{fallback}/"
        if fb_ipa != correct_ipa and fb_ipa not in chosen:
            chosen.append(fb_ipa)
        else:
            chosen.append(f"/{raw_ipa}x/")
        break  # only one fallback needed

    # Build choices: correct answer at random position
    import random
    choices = [correct_ipa] + chosen[:2]
    random.shuffle(choices)

    return {
        "type": "choose_ipa",
        "prompt": "Which IPA matches this word?",
        "choices": choices,
    }
