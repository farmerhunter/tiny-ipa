"""Phoneme-level statistics and mastery computation.

Every attempt submission updates ``phoneme_stats`` for each target
phoneme on the session item. Mastery status is derived from attempt
count and accuracy with documented precedence rules.
"""

from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Mastery status
# ---------------------------------------------------------------------------

# Precedence: "weak" beats "learning" when accuracy < 0.70.
#              "mastered" beats "learning"/"weak" when threshold met.
#              "new" is the base state.

def _compute_mastery(attempt_count: int, correct_count: int) -> str:
    """Map attempt count and accuracy to a mastery status string.

    Rules (in evaluation order — first match wins):
    1. ``attempt_count < 3`` → ``"new"``
    2. ``attempt_count >= 5 AND accuracy >= 0.85`` → ``"mastered"``
    3. ``attempt_count >= 3 AND accuracy < 0.70`` → ``"weak"``
    4. ``attempt_count >= 3 AND accuracy < 0.85`` → ``"learning"``
    5. ``attempt_count >= 3 AND accuracy >= 0.85`` → ``"learning"``
       (ready for mastery after 5+)
    """
    if attempt_count == 0:
        return "new"
    accuracy = correct_count / attempt_count
    if attempt_count >= 5 and accuracy >= 0.85:
        return "mastered"
    if attempt_count >= 3:
        if accuracy < 0.70:
            return "weak"
        return "learning"
    return "new"


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------


def _get_or_create_stat(
    conn: sqlite3.Connection,
    user_id: str,
    primary_accent: str,
    phoneme_id: str,
) -> dict:
    """Return the current phoneme_stats row for (user, accent, phoneme) or a
    default dict suitable for first-time insert."""
    row = conn.execute(
        """
        SELECT attempt_count, correct_count, mastery_status, last_wrong_at
        FROM phoneme_stats
        WHERE user_id = ? AND primary_accent = ? AND phoneme_id = ?
        """,
        (user_id, primary_accent, phoneme_id),
    ).fetchone()
    if row is None:
        return {
            "attempt_count": 0,
            "correct_count": 0,
            "mastery_status": "new",
            "last_wrong_at": None,
        }
    return {
        "attempt_count": row["attempt_count"],
        "correct_count": row["correct_count"],
        "mastery_status": row["mastery_status"],
        "last_wrong_at": row["last_wrong_at"],
    }


def _upsert_phoneme_stat(
    conn: sqlite3.Connection,
    user_id: str,
    primary_accent: str,
    phoneme_id: str,
    attempt_count: int,
    correct_count: int,
    mastery_status: str,
    last_attempt_at: str,
    last_wrong_at: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO phoneme_stats (
            user_id, primary_accent, phoneme_id,
            attempt_count, correct_count,
            last_attempt_at, last_wrong_at, mastery_status
        ) VALUES (
            :user_id, :primary_accent, :phoneme_id,
            :attempt_count, :correct_count,
            :last_attempt_at, :last_wrong_at, :mastery_status
        )
        """,
        {
            "user_id": user_id,
            "primary_accent": primary_accent,
            "phoneme_id": phoneme_id,
            "attempt_count": attempt_count,
            "correct_count": correct_count,
            "last_attempt_at": last_attempt_at,
            "last_wrong_at": last_wrong_at,
            "mastery_status": mastery_status,
        },
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def update_phoneme_stats(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    primary_accent: str,
    target_phonemes: List[str],
    is_correct: bool,
    timestamp: str,
) -> List[dict]:
    """Update phoneme_stats for each target phoneme after an attempt.

    Args:
        conn: Database connection.
        user_id: e.g. "default".
        primary_accent: "US" or "UK".
        target_phonemes: Phoneme symbols from the session item.
        is_correct: Whether the user answered correctly.
        timestamp: ISO-8601 timestamp for this attempt.

    Returns:
        A list of ``updated_phonemes`` dicts matching the API contract,
        one per target phoneme.
    """
    updated: List[dict] = []
    for phoneme_id in target_phonemes:
        stat = _get_or_create_stat(conn, user_id, primary_accent, phoneme_id)
        new_count = stat["attempt_count"] + 1
        new_correct = stat["correct_count"] + (1 if is_correct else 0)
        mastery = _compute_mastery(new_count, new_correct)
        # Preserve existing last_wrong_at on correct attempts.
        if is_correct:
            wrong_at = stat.get("last_wrong_at")
        else:
            wrong_at = timestamp

        _upsert_phoneme_stat(
            conn,
            user_id,
            primary_accent,
            phoneme_id,
            attempt_count=new_count,
            correct_count=new_correct,
            mastery_status=mastery,
            last_attempt_at=timestamp,
            last_wrong_at=wrong_at,
        )

        updated.append(
            {
                "phoneme": phoneme_id,
                "attempt_count": new_count,
                "correct_count": new_correct,
                "mastery_status": mastery,
            }
        )
    return updated
