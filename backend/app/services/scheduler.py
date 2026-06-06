"""Word selection for daily practice sessions.

The scheduler selects ``daily_word_count`` words from the ``words`` table.
For M2 the selection is simple — usable words, shuffle, take N. Weak-phoneme
weighting and new/review ratio are M5 concerns.
"""

import random
import sqlite3
from typing import List

from app.models import Word
from app.services.db_store import get_word_by_id


def select_daily_words(
    conn: sqlite3.Connection,
    daily_word_count: int = 10,
    accent: str = "US",
    seed: int = 0,
) -> List[Word]:
    """Select ``daily_word_count`` usable words for today's practice.

    Usable = ipa_us is present and content_status is not 'disabled'.

    Args:
        conn: Database connection.
        daily_word_count: How many words to select.
        accent: "US" or "UK" — only words with the matching IPA field.
        seed: Deterministic seed for shuffle. Use the date-derived value
              so same-day calls return the same order.

    Returns:
        List of Word dataclasses, length ≤ daily_word_count.
    """
    ipa_field = "ipa_us" if accent.upper() == "US" else "ipa_uk"
    rows = conn.execute(
        f"""
        SELECT id FROM words
        WHERE {ipa_field} IS NOT NULL AND {ipa_field} != ''
          AND content_status != 'disabled'
        """
    ).fetchall()

    word_ids = [r["id"] for r in rows]
    rng = random.Random(seed)
    rng.shuffle(word_ids)
    selected_ids = word_ids[:daily_word_count]

    words: List[Word] = []
    for wid in selected_ids:
        w = get_word_by_id(conn, wid)
        if w is not None:
            words.append(w)
    return words
