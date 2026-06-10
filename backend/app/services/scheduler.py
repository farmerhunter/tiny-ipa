"""Word selection for daily practice sessions.

The scheduler intentionally stays small: it filters unusable content, suppresses
short-term repeats when the pool allows it, then scores candidates using
phoneme stats and deterministic tie-breaking.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set

from app.models import Word
from app.services.db_store import get_word_by_id

_REVIEW_STRENGTH_MULTIPLIERS = {
    "quick": 0.35,
    "low": 0.35,
    "normal": 1.0,
    "extra_review": 1.7,
    "high": 1.7,
}


@dataclass(frozen=True)
class _Candidate:
    word_id: str
    phoneme_tags: List[str]
    score: float
    has_seen_phoneme: bool


def select_daily_words(
    conn: sqlite3.Connection,
    daily_word_count: int = 10,
    accent: str = "US",
    seed: int = 0,
    *,
    user_id: str = "default",
    review_strength: str = "normal",
    focus_phonemes: Optional[Sequence[str]] = None,
) -> List[Word]:
    """Select ``daily_word_count`` usable words for today's practice.

    Usable = accent IPA is present and content_status is not 'disabled'.

    Args:
        conn: Database connection.
        daily_word_count: How many words to select.
        accent: "US" or "UK" — only words with the matching IPA field.
        seed: Deterministic seed for shuffle. Use the date-derived value
              so same-day calls return the same order.
        user_id: User whose phoneme stats and recent sessions should be read.
        review_strength: Weighting mode for weak-phoneme review.
        focus_phonemes: Optional phoneme ids/symbols to boost for this session.

    Returns:
        List of Word dataclasses, length ≤ daily_word_count.
    """
    if daily_word_count <= 0:
        return []

    accent = accent.upper()
    ipa_field = "ipa_us" if accent.upper() == "US" else "ipa_uk"
    tag_field = "phoneme_tags_us" if accent.upper() == "US" else "phoneme_tags_uk"
    rows = conn.execute(
        f"""
        SELECT id, {tag_field} AS phoneme_tags
        FROM words
        WHERE {ipa_field} IS NOT NULL AND {ipa_field} != ''
          AND content_status != 'disabled'
        """
    ).fetchall()

    recent_word_ids = _recent_word_ids(conn, user_id=user_id, accent=accent)
    usable_rows = rows
    non_recent_rows = [r for r in rows if r["id"] not in recent_word_ids]
    if len(non_recent_rows) >= daily_word_count:
        usable_rows = non_recent_rows

    stats = _phoneme_stats(conn, user_id=user_id, accent=accent)
    focus = _normalise_focus_phonemes(conn, focus_phonemes or [])
    review_multiplier = _REVIEW_STRENGTH_MULTIPLIERS.get(review_strength, 1.0)

    candidates = [
        _score_candidate(
            word_id=r["id"],
            phoneme_tags=_parse_tags(r["phoneme_tags"]),
            stats=stats,
            focus_phonemes=focus,
            review_multiplier=review_multiplier,
            seed=seed,
            is_recent=r["id"] in recent_word_ids,
        )
        for r in usable_rows
    ]
    candidates.sort(key=lambda c: (-c.score, c.word_id))
    selected_ids = _choose_with_new_word_balance(candidates, daily_word_count)

    words: List[Word] = []
    for wid in selected_ids:
        w = get_word_by_id(conn, wid)
        if w is not None:
            words.append(w)
    return words


def _parse_tags(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(tag) for tag in parsed if tag]


def _recent_word_ids(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    accent: str,
    session_limit: int = 3,
) -> Set[str]:
    session_rows = conn.execute(
        """
        SELECT id
        FROM daily_sessions
        WHERE user_id = ? AND primary_accent = ?
        ORDER BY session_date DESC, created_at DESC
        LIMIT ?
        """,
        (user_id, accent, session_limit),
    ).fetchall()
    if not session_rows:
        return set()

    placeholders = ",".join("?" for _ in session_rows)
    item_rows = conn.execute(
        f"""
        SELECT DISTINCT word_id
        FROM session_items
        WHERE session_id IN ({placeholders})
        """,
        tuple(r["id"] for r in session_rows),
    ).fetchall()
    return {r["word_id"] for r in item_rows}


def _phoneme_stats(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    accent: str,
) -> Dict[str, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT *
        FROM phoneme_stats
        WHERE user_id = ? AND primary_accent = ?
        """,
        (user_id, accent),
    ).fetchall()
    return {r["phoneme_id"]: r for r in rows}


def _normalise_focus_phonemes(
    conn: sqlite3.Connection,
    focus_phonemes: Iterable[str],
) -> Set[str]:
    focus = {str(p).strip() for p in focus_phonemes if str(p).strip()}
    if not focus:
        return set()

    rows = conn.execute("SELECT id, symbol FROM phonemes").fetchall()
    aliases: Dict[str, Set[str]] = {}
    for row in rows:
        values = {row["id"], row["symbol"]}
        aliases[row["id"]] = values
        aliases[row["symbol"]] = values

    normalised = set()
    for phoneme in focus:
        normalised.update(aliases.get(phoneme, {phoneme}))
    return normalised


def _score_candidate(
    *,
    word_id: str,
    phoneme_tags: List[str],
    stats: Dict[str, sqlite3.Row],
    focus_phonemes: Set[str],
    review_multiplier: float,
    seed: int,
    is_recent: bool,
) -> _Candidate:
    review_scores = [
        _phoneme_review_score(stats[tag])
        for tag in phoneme_tags
        if tag in stats
    ]
    review_score = 0.0
    if review_scores:
        review_score = max(review_scores) + (sum(review_scores) * 0.2)

    focus_matches = len(set(phoneme_tags) & focus_phonemes)
    focus_bonus = 2.25 * focus_matches
    new_bonus = 0.35 if not review_scores else 0.0
    recent_penalty = -8.0 if is_recent else 0.0
    tie_breaker = _stable_fraction(f"{seed}:{word_id}") * 0.01

    return _Candidate(
        word_id=word_id,
        phoneme_tags=phoneme_tags,
        score=(review_score * review_multiplier) + focus_bonus + new_bonus + recent_penalty
        + tie_breaker,
        has_seen_phoneme=bool(review_scores),
    )


def _phoneme_review_score(row: sqlite3.Row) -> float:
    attempt_count = max(int(row["attempt_count"]), 0)
    correct_count = max(int(row["correct_count"]), 0)
    accuracy = correct_count / attempt_count if attempt_count else 0.0

    score = 0.0
    mastery_status = row["mastery_status"]
    if mastery_status == "weak":
        score += 3.0
    elif mastery_status == "learning":
        score += 1.0
    elif mastery_status == "mastered":
        score -= 0.25

    if attempt_count:
        score += max(0.0, 0.85 - accuracy) * 2.0
    if row["last_wrong_at"]:
        score += 1.25
    return score


def _choose_with_new_word_balance(
    candidates: List[_Candidate],
    daily_word_count: int,
) -> List[str]:
    if len(candidates) <= daily_word_count:
        return [c.word_id for c in candidates]

    new_candidates = [c for c in candidates if not c.has_seen_phoneme]
    if daily_word_count <= 1 or not new_candidates:
        return [c.word_id for c in candidates[:daily_word_count]]

    desired_new = min(len(new_candidates), max(1, daily_word_count // 4))
    review_slots = max(daily_word_count - desired_new, 0)
    selected: List[_Candidate] = []

    for candidate in candidates:
        if candidate.has_seen_phoneme and len(selected) < review_slots:
            selected.append(candidate)

    selected_ids = {c.word_id for c in selected}
    for candidate in new_candidates:
        if len([c for c in selected if not c.has_seen_phoneme]) >= desired_new:
            break
        if candidate.word_id not in selected_ids:
            selected.append(candidate)
            selected_ids.add(candidate.word_id)

    for candidate in candidates:
        if len(selected) >= daily_word_count:
            break
        if candidate.word_id not in selected_ids:
            selected.append(candidate)
            selected_ids.add(candidate.word_id)

    selected.sort(key=lambda c: (-c.score, c.word_id))
    return [c.word_id for c in selected[:daily_word_count]]


def _stable_fraction(value: str) -> float:
    digest = hashlib.md5(value.encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF
