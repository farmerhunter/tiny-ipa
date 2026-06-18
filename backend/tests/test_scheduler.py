"""Unit tests for phoneme-aware daily word scheduling."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from sys import path as _python_path
from typing import List, Optional

import pytest

from app.db import get_connection
from app.models import DailySession, SessionItem
from app.services.db_schema import init_db
from app.services.db_store import create_session, create_session_item
from app.services.scheduler import select_daily_words

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in _python_path:
    _python_path.insert(0, str(_SCRIPTS))

from import_words import import_words  # noqa: E402

CORE_300_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "core_300_words.json"
PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"


@pytest.fixture(name="conn")
def conn_fixture(tmp_path: Path):
    db_path = str(tmp_path / "scheduler.sqlite")
    conn = get_connection(db_path)
    init_db(conn)
    yield conn
    conn.close()


def _insert_word(
    conn,
    word_id: str,
    tags: List[str],
    *,
    status: str = "core_selected",
    ipa: Optional[str] = None,
    level: str = "beginner",
) -> None:
    conn.execute(
        """
        INSERT INTO words (
            id, word, level, ipa_us, ipa_uk, phoneme_tags_us, phoneme_tags_uk,
            content_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            word_id,
            word_id,
            level,
            ipa or f"/{word_id}/",
            ipa or f"/{word_id}/",
            _json(tags),
            _json(tags),
            status,
        ),
    )


def _insert_stat(
    conn,
    phoneme_id: str,
    *,
    attempts: int,
    correct: int,
    mastery: str,
    last_wrong_at: Optional[str] = "2026-06-01T00:00:00Z",
) -> None:
    conn.execute(
        """
        INSERT INTO phoneme_stats (
            user_id, primary_accent, phoneme_id, attempt_count, correct_count,
            last_attempt_at, last_wrong_at, mastery_status
        ) VALUES ('default', 'US', ?, ?, ?, '2026-06-02T00:00:00Z', ?, ?)
        """,
        (phoneme_id, attempts, correct, last_wrong_at, mastery),
    )


def _insert_recent_session(conn, word_ids: List[str], *, session_id: str = "recent") -> None:
    session = DailySession(
        id=session_id,
        user_id="default",
        session_date="2026-06-09",
        primary_accent="US",
        status="complete",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    create_session(conn, session)
    for index, word_id in enumerate(word_ids):
        create_session_item(
            conn,
            SessionItem(
                id=f"{session_id}_item_{index}",
                session_id=session_id,
                word_id=word_id,
                order_index=index,
                target_phonemes=[],
                question_type="choose_ipa",
                status="complete",
            ),
        )


def _json(values: List[str]) -> str:
    import json

    return json.dumps(values)


def _ids(words) -> List[str]:
    return [word.id for word in words]


def test_weak_phoneme_words_rank_higher(conn):
    _insert_word(conn, "ship", ["/weak/", "/p/"])
    _insert_word(conn, "cat", ["/strong/", "/t/"])
    _insert_word(conn, "new", ["/fresh/"])
    _insert_stat(conn, "/weak/", attempts=5, correct=1, mastery="weak")
    _insert_stat(conn, "/strong/", attempts=6, correct=6, mastery="mastered", last_wrong_at=None)

    selected = select_daily_words(conn, daily_word_count=2, seed=101)

    assert _ids(selected)[0] == "ship"
    assert "cat" not in _ids(selected)


def test_disabled_words_are_never_selected(conn):
    _insert_word(conn, "disabled", ["/weak/"], status="disabled")
    _insert_word(conn, "active", ["/other/"])
    _insert_stat(conn, "/weak/", attempts=8, correct=0, mastery="weak")

    selected = select_daily_words(conn, daily_word_count=2, seed=7)

    assert _ids(selected) == ["active"]


def test_learner_level_filters_entry_and_mid_pools(conn):
    _insert_word(conn, "entry_one", ["/e/"], level="beginner")
    _insert_word(conn, "entry_two", ["/e2/"], level="beginner")
    _insert_word(conn, "mid_one", ["/m/"], level="intermediate")
    _insert_word(conn, "mid_two", ["/m2/"], level="intermediate")

    entry = select_daily_words(conn, daily_word_count=10, seed=4, learner_level="entry")
    mid = select_daily_words(conn, daily_word_count=10, seed=4, learner_level="mid")

    assert set(_ids(entry)) == {"entry_one", "entry_two"}
    assert set(_ids(mid)) == {"mid_one", "mid_two"}


def test_recent_words_are_suppressed_when_alternatives_exist(conn):
    for word_id in ("recent_a", "recent_b", "fresh_a", "fresh_b"):
        _insert_word(conn, word_id, [f"/{word_id}/"])
    _insert_recent_session(conn, ["recent_a", "recent_b"])

    selected = select_daily_words(conn, daily_word_count=2, seed=9)

    assert set(_ids(selected)) == {"fresh_a", "fresh_b"}


def test_recent_words_can_fill_when_pool_is_small(conn):
    _insert_word(conn, "recent", ["/r/"])
    _insert_word(conn, "fresh", ["/f/"])
    _insert_recent_session(conn, ["recent"])

    selected = select_daily_words(conn, daily_word_count=2, seed=9)

    assert set(_ids(selected)) == {"recent", "fresh"}


def test_new_words_remain_in_mix_when_weak_review_exists(conn):
    _insert_word(conn, "weak_one", ["/weak/"])
    _insert_word(conn, "weak_two", ["/weak/"])
    _insert_word(conn, "weak_three", ["/weak/"])
    _insert_word(conn, "fresh", ["/fresh/"])
    _insert_stat(conn, "/weak/", attempts=8, correct=1, mastery="weak")

    selected = select_daily_words(conn, daily_word_count=3, seed=10)

    assert "fresh" in _ids(selected)
    assert _ids(selected)[0].startswith("weak_")


def test_focus_phonemes_boost_matching_words_without_excluding_others(conn):
    _insert_word(conn, "focus_a", ["/focus/"])
    _insert_word(conn, "focus_b", ["/focus/"])
    _insert_word(conn, "other", ["/other/"])

    selected = select_daily_words(
        conn,
        daily_word_count=3,
        seed=5,
        focus_phonemes=["/focus/"],
    )

    assert _ids(selected)[:2] == ["focus_a", "focus_b"]
    assert "other" in _ids(selected)


def test_review_strength_changes_weak_word_weighting(conn):
    _insert_word(conn, "weak", ["/weak/"])
    _insert_word(conn, "focus", ["/focus/"])
    _insert_stat(conn, "/weak/", attempts=6, correct=0, mastery="weak")

    quick = select_daily_words(
        conn,
        daily_word_count=1,
        seed=3,
        review_strength="quick",
        focus_phonemes=["/focus/"],
    )
    extra_review = select_daily_words(
        conn,
        daily_word_count=1,
        seed=3,
        review_strength="extra_review",
        focus_phonemes=["/focus/"],
    )

    assert _ids(quick) == ["focus"]
    assert _ids(extra_review) == ["weak"]


def test_selection_is_deterministic_for_same_seed(conn):
    for word_id in ("a", "b", "c", "d", "e"):
        _insert_word(conn, word_id, [f"/{word_id}/"])

    first = select_daily_words(conn, daily_word_count=3, seed=123)
    second = select_daily_words(conn, daily_word_count=3, seed=123)
    different_seed = select_daily_words(conn, daily_word_count=3, seed=124)

    assert _ids(first) == _ids(second)
    assert _ids(first) != _ids(different_seed)


def test_core_300_scheduling_remains_stable(tmp_path: Path):
    db_path = str(tmp_path / "core300.sqlite")
    import_words(
        source_path=CORE_300_PATH,
        phonemes_path=PHONEMES_PATH,
        db_path=db_path,
    )

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT id, phoneme_tags_us FROM words WHERE content_status != 'disabled'"
    ).fetchall()
    focus_word = None
    for row in rows:
        tags = row["phoneme_tags_us"]
        if tags:
            parsed = json.loads(tags)
            if "/ʌ/" in parsed:
                focus_word = row["id"]
                break

    if focus_word is None:
        conn.close()
        pytest.skip("No /ʌ/ word available in current core_300 fixture")

    selected = select_daily_words(
        conn,
        daily_word_count=10,
        accent="US",
        seed=777,
        focus_phonemes=["/ʌ/"],
    )
    selected_ids = [w.id for w in selected]

    assert len(selected_ids) == 10
    assert focus_word in selected_ids

    conn.execute(
        "UPDATE words SET content_status = 'disabled' WHERE id = ?",
        (selected_ids[0],),
    )
    conn.commit()

    selected_after = select_daily_words(
        conn,
        daily_word_count=10,
        accent="US",
        seed=777,
        focus_phonemes=["/ʌ/"],
    )
    conn.close()

    assert len(selected_after) <= 10
    assert selected_ids[0] not in [w.id for w in selected_after]
