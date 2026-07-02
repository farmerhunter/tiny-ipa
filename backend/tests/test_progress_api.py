"""Tests for GET /api/progress — phoneme summary and streak."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from import_words import import_words  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.main import app  # noqa: E402
from app.services.db_schema import init_db  # noqa: E402
from app.services.progress import build_progress_response  # noqa: E402
from tests.auth_helpers import authenticated_client, bootstrap_owner_user  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTENT_SAMPLE = FIXTURES / "content_sample.json"
PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(name="seeded_db")
def seeded_db_fixture(tmp_path: Path) -> str:
    """Database with imported content and default settings."""
    db_path = str(tmp_path / "test.sqlite")
    import_words(source_path=CONTENT_SAMPLE, phonemes_path=PHONEMES_PATH, db_path=db_path)
    import app.db as db_mod
    orig = db_mod.DEFAULT_DB_PATH
    db_mod.DEFAULT_DB_PATH = db_path
    bootstrap_owner_user(db_path)
    yield db_path
    db_mod.DEFAULT_DB_PATH = orig


@pytest.fixture(name="client")
def client_fixture(seeded_db: str) -> TestClient:
    return authenticated_client(TestClient(app))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProgressApi:
    """Integration tests for GET /api/progress."""

    def test_empty_progress_returns_defaults(self, client):
        """No attempts yet — returns zeros and empty lists."""
        resp = client.get("/api/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_attempts"] == 0
        assert data["total_sessions"] == 0
        assert data["total_normal_groups"] == 0
        assert data["stat_scope"] == "global"
        assert data["level_stats"]["entry"]["label"] == "Entry"
        assert data["level_stats"]["mid"]["label"] == "Mid"
        assert data["today_completed"] is False
        assert data["streak_days"] == 0
        assert data["weak_phonemes"] == []
        assert data["strong_phonemes"] == []

    def test_today_status_reflects_session(self, client, seeded_db):
        """After creating today's session, progress reflects it."""
        # Create today's session
        client.post("/api/practice/next-normal")
        resp = client.get("/api/progress")
        data = resp.json()
        assert data["today_status"] == "in_progress"
        assert data["today_completed"] is False
        assert data["resumable_normal_groups"] == 1
        assert data["level_stats"]["entry"]["resumable_normal_groups"] == 1

    def test_resumable_progress_matches_today_resume_group(self, client, seeded_db):
        client.put("/api/settings", json={"daily_word_count": 1})
        started = client.post("/api/practice/next-normal").json()

        progress = client.get("/api/progress").json()
        today = client.get("/api/today").json()

        assert progress["resumable_normal_groups"] == 1
        assert progress["level_stats"]["entry"]["resumable_normal_groups"] == 1
        assert progress["level_stats"]["mid"]["resumable_normal_groups"] == 0
        assert today["session_id"] == started["session_id"]
        assert today["origin"] == "normal_resume"
        assert today["source_scope"] == "normal_current"

    def test_completed_group_clears_resumable_progress_and_updates_counts(
        self, client, seeded_db
    ):
        client.put("/api/settings", json={"daily_word_count": 1})
        today = client.post("/api/practice/next-normal").json()
        item = today["items"][0]

        client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        })

        progress = client.get("/api/progress").json()

        assert progress["today_status"] == "completed"
        assert progress["today_completed"] is True
        assert progress["resumable_normal_groups"] == 0
        assert progress["level_stats"]["entry"]["resumable_normal_groups"] == 0
        assert progress["level_stats"]["entry"]["completed_normal_groups_today"] == 1

    def test_abandoned_normal_group_is_not_resumable_progress(self, client, seeded_db):
        client.put("/api/settings", json={"daily_word_count": 1})
        started = client.post("/api/practice/next-normal").json()
        client.post("/api/practice/abandon-current-and-next")

        conn = get_connection(seeded_db)
        conn.execute(
            "UPDATE daily_sessions SET status = 'abandoned' WHERE status = 'in_progress'"
        )
        conn.commit()
        conn.close()

        progress = client.get("/api/progress").json()
        today = client.get("/api/today").json()

        assert progress["total_normal_groups"] >= 1
        assert progress["level_stats"]["entry"]["normal_groups"] >= 1
        assert progress["resumable_normal_groups"] == 0
        assert progress["level_stats"]["entry"]["resumable_normal_groups"] == 0
        assert today.get("session_id") != started["session_id"]
        assert today["origin"] == "normal_empty"

    def test_total_attempts_counted(self, client, seeded_db):
        """After submitting attempts, total_attempts increases."""
        # Get a session item
        today = client.post("/api/practice/next-normal").json()
        item = today["items"][0]

        # Submit one attempt
        client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        })

        resp = client.get("/api/progress")
        data = resp.json()
        assert data["total_attempts"] == 1
        assert data["total_sessions"] > 0

    def test_phoneme_lists_after_attempts(self, client, seeded_db):
        """After several attempts across phonemes, weak/strong lists appear."""
        today = client.post("/api/practice/next-normal").json()

        # Submit 3 wrong answers for first item
        for _ in range(3):
            client.post("/api/attempt", json={
                "session_item_id": today["items"][0]["session_item_id"],
                "selected_answer": "/wrong/",
            })

        resp = client.get("/api/progress")
        data = resp.json()
        # Should have weak phonemes (low accuracy)
        assert len(data["weak_phonemes"]) > 0
        for wp in data["weak_phonemes"]:
            assert wp["accuracy"] < 0.70
            assert wp["attempt_count"] >= 2
            assert "phoneme" in wp
            assert "correct_count" in wp
            assert "mastery_status" in wp

    def test_empty_db_no_crash(self, tmp_path, monkeypatch):
        """Fresh database with no content returns safe defaults."""
        db_path = str(tmp_path / "empty.sqlite")
        conn = get_connection(db_path)
        init_db(conn)
        conn.close()

        import app.db as db_mod
        orig = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            c = TestClient(app)
            bootstrap_owner_user(db_path)
            authenticated_client(c)
            resp = c.get("/api/progress")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_attempts"] == 0
            assert data["weak_phonemes"] == []
        finally:
            db_mod.DEFAULT_DB_PATH = orig

    def test_response_shape(self, client):
        """Response contains all documented fields."""
        resp = client.get("/api/progress")
        data = resp.json()
        for key in (
            "today_completed", "today_status", "streak_days",
            "total_attempts", "total_sessions", "total_normal_groups",
            "resumable_normal_groups", "weak_phonemes", "strong_phonemes",
            "stat_scope", "level_stats",
        ):
            assert key in data, f"missing key: {key}"
        for level in ("entry", "mid"):
            assert "resumable_normal_groups" in data["level_stats"][level]

    def test_level_stats_scope_normal_practice_by_entry_and_mid(self, seeded_db):
        conn = get_connection(seeded_db)
        today = date.today().isoformat()
        sessions = [
            ("entry-normal", "normal", "entry", "completed"),
            ("mid-normal", "normal", "mid", "completed"),
            ("mid-focus", "weak_focus", "mid", "completed"),
        ]
        for session_id, group_type, level, status in sessions:
            conn.execute(
                """
                INSERT INTO daily_sessions (
                    id, user_id, session_date, primary_accent,
                    status, created_at, completed_at, group_index,
                    group_type, learner_level
                ) VALUES (?, 'default', ?, 'US', ?, ?, ?, 1, ?, ?)
                """,
                (
                    session_id,
                    today,
                    status,
                    f"{today}T10:00:00Z",
                    f"{today}T10:05:00Z",
                    group_type,
                    level,
                ),
            )
            conn.execute(
                """
                INSERT INTO session_items (
                    id, session_id, word_id, order_index, target_phonemes,
                    question_type, status
                ) VALUES (?, ?, ?, 0, ?, 'choose_ipa', 'complete')
                """,
                (
                    f"{session_id}-item",
                    session_id,
                    "cat",
                    json.dumps(["/æ/"] if level == "entry" else ["/ʃ/"]),
                ),
            )

        for index in range(3):
            conn.execute(
                """
                INSERT INTO attempts (
                    id, user_id, session_item_id, word_id, primary_accent,
                    question_type, selected_answer, correct_answer, is_correct, created_at
                ) VALUES (?, 'default', 'entry-normal-item', 'cat', 'US',
                    'choose_ipa', '/wrong/', '/kæt/', 0, ?)
                """,
                (f"entry-attempt-{index}", f"{today}T10:0{index}:00Z"),
            )
        for index in range(3):
            conn.execute(
                """
                INSERT INTO attempts (
                    id, user_id, session_item_id, word_id, primary_accent,
                    question_type, selected_answer, correct_answer, is_correct, created_at
                ) VALUES (?, 'default', 'mid-normal-item', 'cat', 'US',
                    'choose_ipa', '/ʃɪp/', '/ʃɪp/', 1, ?)
                """,
                (f"mid-attempt-{index}", f"{today}T11:0{index}:00Z"),
            )
        conn.execute(
            """
            INSERT INTO attempts (
                id, user_id, session_item_id, word_id, primary_accent,
                question_type, selected_answer, correct_answer, is_correct, created_at
            ) VALUES ('focus-attempt', 'default', 'mid-focus-item', 'cat', 'US',
                'choose_ipa', '/ʃɪp/', '/ʃɪp/', 1, ?)
            """,
            (f"{today}T12:00:00Z",),
        )
        conn.commit()
        conn.close()

        conn = get_connection(seeded_db)
        resp = build_progress_response(conn)
        conn.close()

        assert resp["total_attempts"] == 7
        assert resp["total_sessions"] == 3
        assert resp["total_normal_groups"] == 2
        assert resp["level_stats"]["entry"]["completed_normal_groups_today"] == 1
        assert resp["level_stats"]["mid"]["completed_normal_groups_today"] == 1
        assert resp["level_stats"]["entry"]["attempts"] == 3
        assert resp["level_stats"]["mid"]["attempts"] == 3
        assert resp["level_stats"]["entry"]["weak_phonemes"][0]["phoneme"] == "/æ/"
        assert resp["level_stats"]["mid"]["strong_phonemes"][0]["phoneme"] == "/ʃ/"

    def test_progress_defaults_do_not_blend_uk_stats_into_us_path(self, seeded_db):
        conn = get_connection(seeded_db)
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        sessions = [
            ("us-normal", "US", today, "completed", "entry"),
            ("uk-normal", "UK", today, "in_progress", "mid"),
            ("uk-streak", "UK", yesterday, "completed", "mid"),
        ]
        for session_id, accent, session_date, status, level in sessions:
            conn.execute(
                """
                INSERT INTO daily_sessions (
                    id, user_id, session_date, primary_accent,
                    status, created_at, completed_at, group_index,
                    group_type, learner_level
                ) VALUES (?, 'default', ?, ?, ?, ?, ?, 1, 'normal', ?)
                """,
                (
                    session_id,
                    session_date,
                    accent,
                    status,
                    f"{session_date}T10:00:00Z",
                    f"{session_date}T10:05:00Z" if status == "completed" else None,
                    level,
                ),
            )
            conn.execute(
                """
                INSERT INTO session_items (
                    id, session_id, word_id, order_index, target_phonemes,
                    question_type, status
                ) VALUES (?, ?, 'ship', 0, ?, 'choose_ipa', 'complete')
                """,
                (
                    f"{session_id}-item",
                    session_id,
                    json.dumps(["/ʃ/"] if accent == "US" else ["/θ/"]),
                ),
            )

        for index in range(3):
            conn.execute(
                """
                INSERT INTO attempts (
                    id, user_id, session_item_id, word_id, primary_accent,
                    question_type, selected_answer, correct_answer, is_correct, created_at
                ) VALUES (?, 'default', 'us-normal-item', 'ship', 'US',
                    'choose_ipa', '/ʃɪp/', '/ʃɪp/', 1, ?)
                """,
                (f"us-attempt-{index}", f"{today}T11:0{index}:00Z"),
            )
            conn.execute(
                """
                INSERT INTO attempts (
                    id, user_id, session_item_id, word_id, primary_accent,
                    question_type, selected_answer, correct_answer, is_correct, created_at
                ) VALUES (?, 'default', 'uk-normal-item', 'ship', 'UK',
                    'choose_ipa', '/wrong/', '/ʃɪp/', 0, ?)
                """,
                (f"uk-attempt-{index}", f"{today}T12:0{index}:00Z"),
            )

        conn.execute(
            """
            INSERT INTO phoneme_stats (
                user_id, primary_accent, phoneme_id, attempt_count, correct_count,
                last_attempt_at, mastery_status
            ) VALUES ('default', 'US', '/ʃ/', 3, 3, ?, 'learning')
            """,
            (f"{today}T11:02:00Z",),
        )
        conn.execute(
            """
            INSERT INTO phoneme_stats (
                user_id, primary_accent, phoneme_id, attempt_count, correct_count,
                last_attempt_at, mastery_status
            ) VALUES ('default', 'UK', '/θ/', 3, 0, ?, 'weak')
            """,
            (f"{today}T12:02:00Z",),
        )
        conn.commit()

        resp = build_progress_response(conn)
        conn.close()

        assert resp["today_status"] == "completed"
        assert resp["today_completed"] is True
        assert resp["streak_days"] == 0
        assert resp["total_attempts"] == 3
        assert resp["total_sessions"] == 1
        assert resp["total_normal_groups"] == 1
        assert resp["level_stats"]["entry"]["normal_groups"] == 1
        assert resp["level_stats"]["mid"]["normal_groups"] == 0
        assert resp["level_stats"]["entry"]["attempts"] == 3
        assert resp["level_stats"]["mid"]["attempts"] == 0
        assert resp["weak_phonemes"] == []
        assert resp["strong_phonemes"][0]["phoneme"] == "/ʃ/"


# ---------------------------------------------------------------------------
# Streak
# ---------------------------------------------------------------------------


class TestStreak:
    def test_no_sessions_zero_streak(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        conn = get_connection(db_path)
        init_db(conn)
        # Insert settings so build_progress_response doesn't 500
        conn.execute(
            """
            INSERT INTO settings (
                user_id, primary_accent, daily_word_count,
                show_translation, show_accent_compare,
                practice_mode, review_strength, updated_at
            ) VALUES ('default','US',10,1,0,'ipa_first','normal','2026-01-01T00:00:00Z')
            """
        )
        conn.commit()
        resp = build_progress_response(conn)
        conn.close()
        assert resp["streak_days"] == 0

    def test_consecutive_streak(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        conn = get_connection(db_path)
        init_db(conn)
        conn.execute(
            """
            INSERT INTO settings (
                user_id, primary_accent, daily_word_count,
                show_translation, show_accent_compare,
                practice_mode, review_strength, updated_at
            ) VALUES ('default','US',10,1,0,'ipa_first','normal','2026-01-01T00:00:00Z')
            """
        )
        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        # Completed yesterday and two days ago
        for d in [yesterday, two_days_ago]:
            conn.execute(
                """
                INSERT INTO daily_sessions (
                    id, user_id, session_date, primary_accent,
                    status, created_at, completed_at
                ) VALUES (?, 'default', ?, 'US', 'completed', ?, NULL)
                """,
                (f"{d.isoformat()}-default", d.isoformat(), f"{d.isoformat()}T10:00:00Z"),
            )
        conn.commit()
        resp = build_progress_response(conn)
        conn.close()
        assert resp["streak_days"] == 2

    def test_gap_breaks_streak(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        conn = get_connection(db_path)
        init_db(conn)
        conn.execute(
            """
            INSERT INTO settings (
                user_id, primary_accent, daily_word_count,
                show_translation, show_accent_compare,
                practice_mode, review_strength, updated_at
            ) VALUES ('default','US',10,1,0,'ipa_first','normal','2026-01-01T00:00:00Z')
            """
        )
        today = date.today()
        two_days_ago = today - timedelta(days=2)
        four_days_ago = today - timedelta(days=4)

        # Completed 2 days ago and 4 days ago (gap at 3 days ago)
        for d in [two_days_ago, four_days_ago]:
            conn.execute(
                """
                INSERT INTO daily_sessions (
                    id, user_id, session_date, primary_accent,
                    status, created_at, completed_at
                ) VALUES (?, 'default', ?, 'US', 'completed', ?, NULL)
                """,
                (f"{d.isoformat()}-default", d.isoformat(), f"{d.isoformat()}T10:00:00Z"),
            )
        conn.commit()
        resp = build_progress_response(conn)
        conn.close()
        # Streak counts consecutive completed days ending at yesterday.
        # Yesterday not completed → no active streak.
        assert resp["streak_days"] == 0


# ---------------------------------------------------------------------------
# Phoneme list ordering
# ---------------------------------------------------------------------------


class TestPhonemeOrdering:
    def test_ordering(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        conn = get_connection(db_path)
        init_db(conn)
        conn.execute(
            """
            INSERT INTO settings (
                user_id, primary_accent, daily_word_count,
                show_translation, show_accent_compare,
                practice_mode, review_strength, updated_at
            ) VALUES ('default','US',10,1,0,'ipa_first','normal','2026-01-01T00:00:00Z')
            """
        )
        # Insert stats with varying accuracy
        stats = [
            ("/ʃ/", 10, 9),   # 90% — strong
            ("/ɪ/", 10, 5),   # 50% — weak
            ("/p/", 5, 2),    # 40% — very weak
            ("/k/", 8, 8),    # 100% — strong
            ("/æ/", 6, 4),    # 67% — weak
            ("/t/", 3, 3),    # 100% but only 3 attempts — strong (>= 85%)
            ("/n/", 5, 5),    # 100% — strong
            ("/θ/", 4, 1),    # 25% — very weak
            ("/d/", 1, 1),    # below threshold — excluded
        ]
        for phoneme_id, cnt, correct in stats:
            conn.execute(
                """
                INSERT INTO phoneme_stats
                VALUES ('default','US',?,?,?,'2026-01-01T00:00:00Z',NULL,'new')
                """,
                (phoneme_id, cnt, correct),
            )
        conn.commit()

        resp = build_progress_response(conn)
        conn.close()

        weak = resp["weak_phonemes"]
        strong = resp["strong_phonemes"]

        # All stats with attempt_count >= 2 should appear
        # /d/ (1 attempt) excluded
        assert len(weak) + len(strong) == 8  # 9 entries - 1 below threshold
        assert len(weak) == 4  # /ɪ/ (50%), /p/ (40%), /æ/ (67%), /θ/ (25%)

        # Weak sorted by low accuracy: /θ/ (25%) < /p/ (40%) < /ɪ/ (50%) < /æ/ (67%)
        assert weak[0]["phoneme"] == "/θ/"
        assert weak[3]["phoneme"] == "/æ/"

        # Strong sorted by high accuracy: /k/ (100%) = /n/ (100%) > /ʃ/ (90%) > /t/ (100% but 3 att)
        # Within same accuracy, higher attempt_count first
        # /k/ (8) before /n/ (5) before /t/ (3)
        assert strong[0]["phoneme"] == "/k/"
        assert strong[1]["phoneme"] == "/n/"
        assert strong[2]["phoneme"] == "/t/"
        assert strong[3]["phoneme"] == "/ʃ/"
