"""Phoneme-level statistics, mastery computation, and progress summaries.

Every attempt submission updates ``phoneme_stats`` for each target
phoneme on the session item. Mastery status is derived from attempt
count and accuracy with documented precedence rules.

GET /api/progress reads ``phoneme_stats``, ``attempts``, and
``daily_sessions`` to produce a domain summary for the frontend.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
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


# ============================================================================
# Progress summary for GET /api/progress
# ============================================================================

_MIN_ATTEMPTS_FOR_PHONEME_LIST = 2


def build_progress_response(
    conn: sqlite3.Connection,
    user_id: str = "default",
) -> dict:
    """Build the GET /api/progress response dict from runtime data.

    Returns zero/empty defaults when no data exists (no crash).
    """
    # ---- accent from settings ------------------------------------------------
    primary_accent = "US"
    row = conn.execute(
        "SELECT primary_accent FROM settings WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row:
        primary_accent = row["primary_accent"]

    # ---- total attempts ------------------------------------------------------
    total_row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM attempts WHERE user_id = ?", (user_id,)
    ).fetchone()
    total_attempts = total_row["cnt"] if total_row else 0

    # ---- total sessions ------------------------------------------------------
    sess_row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM daily_sessions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    total_sessions = sess_row["cnt"] if sess_row else 0

    # ---- today ---------------------------------------------------------------
    today_str = date.today().isoformat()
    today_row = conn.execute(
        """
        SELECT status FROM daily_sessions
        WHERE user_id = ? AND session_date = ?
        """,
        (user_id, today_str),
    ).fetchone()
    today_status = today_row["status"] if today_row else "none"
    today_completed = today_status == "completed"

    # ---- streak --------------------------------------------------------------
    streak_days = _compute_streak(conn, user_id)

    # ---- weak / strong phonemes ----------------------------------------------
    weak_phonemes, strong_phonemes = _compute_phoneme_lists(
        conn, user_id, primary_accent
    )

    return {
        "today_completed": today_completed,
        "today_status": today_status,
        "streak_days": streak_days,
        "total_attempts": total_attempts,
        "total_sessions": total_sessions,
        "weak_phonemes": weak_phonemes,
        "strong_phonemes": strong_phonemes,
    }


# ---------------------------------------------------------------------------
# Streak
# ---------------------------------------------------------------------------


def _compute_streak(conn: sqlite3.Connection, user_id: str) -> int:
    """Count consecutive completed daily sessions.

    Walks backwards from yesterday; a gap or incomplete day breaks the streak.
    Days that are not completed before the streak starts are skipped.
    """
    rows = conn.execute(
        """
        SELECT session_date FROM daily_sessions
        WHERE user_id = ? AND status = 'completed'
        ORDER BY session_date DESC
        """,
        (user_id,),
    ).fetchall()
    completed_dates = {r["session_date"] for r in rows}

    if not completed_dates:
        return 0

    streak = 0
    d = date.today() - timedelta(days=1)  # start from yesterday

    for _ in range(366):  # safety limit
        ds = d.isoformat()
        if ds in completed_dates:
            streak += 1
            d = d - timedelta(days=1)
        else:
            # First miss after streak started (or no streak yet) — break
            break

    return streak


# ---------------------------------------------------------------------------
# Weak / strong phoneme lists
# ---------------------------------------------------------------------------


def _compute_phoneme_lists(
    conn: sqlite3.Connection, user_id: str, primary_accent: str
) -> Tuple[List[dict], List[dict]]:
    """Return (weak_phonemes, strong_phonemes) sorted lists from phoneme_stats.

    Only includes phonemes with attempt_count >= _MIN_ATTEMPTS_FOR_PHONEME_LIST.
    """
    rows = conn.execute(
        """
        SELECT phoneme_id, attempt_count, correct_count, mastery_status
        FROM phoneme_stats
        WHERE user_id = ? AND primary_accent = ?
          AND attempt_count >= ?
        """,
        (user_id, primary_accent, _MIN_ATTEMPTS_FOR_PHONEME_LIST),
    ).fetchall()

    entries: List[dict] = []
    for r in rows:
        acc = r["correct_count"] / r["attempt_count"] if r["attempt_count"] > 0 else 0.0
        entries.append({
            "phoneme": r["phoneme_id"],
            "accuracy": round(acc, 2),
            "attempt_count": r["attempt_count"],
            "correct_count": r["correct_count"],
            "mastery_status": r["mastery_status"],
        })

    # Weak: sort by low accuracy then higher attempt count
    weak = sorted(
        [e for e in entries if e["accuracy"] < 0.70],
        key=lambda e: (e["accuracy"], -e["attempt_count"]),
    )

    # Strong: sort by high accuracy then higher attempt count
    strong = sorted(
        [e for e in entries if e["accuracy"] >= 0.85],
        key=lambda e: (-e["accuracy"], -e["attempt_count"]),
    )

    return weak, strong
