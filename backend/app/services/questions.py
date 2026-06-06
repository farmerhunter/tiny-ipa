"""Question generation for IPA practice.

Generates choose-IPA questions with contrast-aware distractors.
Distractors are built by substituting phonemes that Chinese learners
commonly confuse, rather than random IPA strings.
"""

import hashlib
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


def generate_choose_ipa_question(word: dict, primary_accent: str = "US") -> dict:
    """
    Generate a choose-IPA question for a given word.

    Args:
        word: word entry dict.
        primary_accent: "US" or "UK" — determines which IPA and phoneme tags
            are used for distractor generation.

    Returns a question dict with:
    - type: "choose_ipa"
    - prompt: question text
    - choices: list of 3 IPA strings (correct + 2 distractors)
      in deterministic order based on word_id.
    """
    accent_key = primary_accent.lower()
    ipa_field = f"ipa_{accent_key}"
    tags_field = f"phoneme_tags_{accent_key}"

    ipa = word.get(ipa_field, "")
    # Fall back to US if the accent-specific IPA is missing
    if not ipa:
        ipa = word.get("ipa_us", "")
    phoneme_tags = word.get(tags_field, [])
    if not phoneme_tags:
        phoneme_tags = word.get("phoneme_tags_us", [])

    raw_ipa = _strip_slashes_and_stress(ipa)
    correct_ipa = f"/{raw_ipa}/"

    distractors = _apply_confusion(raw_ipa, phoneme_tags)

    # If we don't have enough distractors, use the other accent's IPA
    if len(distractors) < 2:
        other_accent = "uk" if accent_key == "us" else "us"
        other_ipa = word.get(f"ipa_{other_accent}", "")
        if other_ipa:
            other_raw = _strip_slashes_and_stress(other_ipa)
            other_ipa_str = f"/{other_raw}/"
            if other_ipa_str != correct_ipa and other_ipa_str not in distractors:
                distractors.append(other_ipa_str)

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

    # Take up to 2 distractors, sorted deterministically for stability
    chosen = sorted(list(distractors))[:2]

    # Pad with a same-length fallback if still short
    while len(chosen) < 2:
        fallback = raw_ipa.replace("ɪ", "i").replace("æ", "e").replace("ʊ", "u")
        fb_ipa = f"/{fallback}/"
        if fb_ipa != correct_ipa and fb_ipa not in chosen:
            chosen.append(fb_ipa)
        else:
            chosen.append(f"/{raw_ipa}x/")
        break

    # Build choices in deterministic order based on word_id hash
    word_id = word.get("word_id", "")
    seed = int(hashlib.sha256(word_id.encode()).hexdigest()[:8], 16)
    choices = [correct_ipa] + chosen[:2]
    # Stable sort: use the seed to determine position
    # Sort choices lexicographically, then rotate based on seed
    choices.sort()
    rotate = seed % len(choices)
    choices = choices[rotate:] + choices[:rotate]

    return {
        "type": "choose_ipa",
        "prompt": "Which IPA matches this word?",
        "choices": choices,
    }
