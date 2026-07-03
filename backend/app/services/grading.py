"""Server-side grading for practice attempts."""

from __future__ import annotations

from app.models import SessionItem, Word


def determine_correct_answer(item: SessionItem, word: Word, accent: str = "US") -> str:
    """Return the server-side canonical answer for a session item."""
    if item.question_type == "choose_word":
        return word.word
    if item.question_type != "choose_ipa":
        raise ValueError(f"Unsupported question_type: {item.question_type}")
    if accent.upper() == "UK" and word.ipa_uk:
        return word.ipa_uk
    return word.ipa_us


def grade_attempt(selected_answer: str, correct_answer: str) -> bool:
    """Compare the selected answer with the correct answer.

    Leading/trailing whitespace is stripped. The comparison is
    exact — no fuzzy matching for M2.
    """
    if not selected_answer or not correct_answer:
        return False
    return selected_answer.strip() == correct_answer.strip()
