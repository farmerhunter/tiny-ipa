"""Static scheduler for daily practice sessions.

For Milestone 1, selection is deterministic by date — no SQLite, no persistent
session state. The same date always produces the same word list (stable across
refreshes), and the seed is derived from the ISO date string so results are
spread across the available word pool.
"""

import hashlib
from datetime import date
from typing import List, Optional


def _date_seed(iso_date: str) -> int:
    """Derive a stable integer seed from an ISO date string (YYYY-MM-DD)."""
    h = hashlib.sha256(iso_date.encode()).digest()
    return int.from_bytes(h[:4], "big")


def select_daily_words(
    words: List[dict],
    daily_count: int = 10,
    session_date: Optional[str] = None,
) -> List[dict]:
    """
    Select a daily word list deterministically from the enabled word pool.

    The selection is:
    - Stable: same date → same words (no shuffle across refreshes)
    - Deterministic: derived from the date, not random
    - Filtered: disabled words are excluded

    If there are fewer enabled words than daily_count, all available words
    are returned.
    """
    if session_date is None:
        session_date = date.today().isoformat()

    # Filter out disabled words
    enabled = [w for w in words if w.get("content_status") != "disabled"]
    if not enabled:
        return []

    daily_count = max(1, daily_count)
    if len(enabled) <= daily_count:
        return list(enabled)

    # Deterministic selection: sort by a hash that mixes word_id + date
    seed = _date_seed(session_date)

    def sort_key(w: dict) -> int:
        raw = f"{session_date}:{w['word_id']}:{seed}"
        h = hashlib.sha256(raw.encode()).digest()
        return int.from_bytes(h[:4], "big")

    shuffled = sorted(enabled, key=sort_key)
    return shuffled[:daily_count]
