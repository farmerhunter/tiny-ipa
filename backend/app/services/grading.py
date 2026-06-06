"""Server-side grading for practice attempts.

Compares the user's selected answer against the correct IPA for the
session item's word and accent. The correct answer is determined from
the database, not trusted from the client request.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from app.models import SessionItem, Word


def determine_correct_answer(item: SessionItem, word: Word, accent: str = "US") -> str:
    """Return the correct IPA string for a session item.

    Args:
        item: The session item being answered.
        word: The corresponding word row.
        accent: "US" or "UK".

    Returns:
        The IPA string the user should match, e.g. "/ʃɪp/".
    """
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
