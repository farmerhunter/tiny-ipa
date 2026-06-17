"""Tests for GET /api/today — session persistence and refresh safety."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure scripts importable.
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from import_words import import_words  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DailySession, SessionItem  # noqa: E402
from app.services.db_schema import init_db  # noqa: E402
from app.services.db_store import (  # noqa: E402
    create_session,
    create_session_item,
    get_session_for_date,
    get_session_items,
    get_word_by_id,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTENT_SAMPLE = FIXTURES / "content_sample.json"
PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"
CORE_300_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "core_300_words.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(name="seeded_db")
def seeded_db_fixture(tmp_path: Path) -> str:
    """Create a database pre-loaded with the 3-word fixture content."""
    db_path = str(tmp_path / "test.sqlite")
    import_words(
        source_path=CONTENT_SAMPLE,
        phonemes_path=PHONEMES_PATH,
        db_path=db_path,
    )
    # Monkey-patch the default DB path so the TestClient uses this DB.
    import app.db as db_mod

    orig = db_mod.DEFAULT_DB_PATH
    db_mod.DEFAULT_DB_PATH = db_path
    yield db_path
    db_mod.DEFAULT_DB_PATH = orig


@pytest.fixture(name="client")
def client_fixture(seeded_db: str) -> TestClient:
    return TestClient(app)


@pytest.fixture(name="seeded_db_core_300")
def seeded_db_core_300_fixture(tmp_path: Path) -> str:
    """Create a database pre-loaded with the full Core 300 runtime content."""
    db_path = str(tmp_path / "core300.sqlite")
    import_words(
        source_path=CORE_300_PATH,
        phonemes_path=PHONEMES_PATH,
        db_path=db_path,
    )

    # Monkey-patch the default DB path so the TestClient uses this DB.
    import app.db as db_mod

    orig = db_mod.DEFAULT_DB_PATH
    db_mod.DEFAULT_DB_PATH = db_path
    yield db_path
    db_mod.DEFAULT_DB_PATH = orig


@pytest.fixture(name="core_300_client")
def core_300_client_fixture(seeded_db_core_300: str) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Session persistence tests
# ---------------------------------------------------------------------------


class TestTodayPersistence:
    """Tests that /api/today is database-backed and refresh-safe."""

    def test_first_today_creates_session(self, client, seeded_db):
        resp = client.get("/api/today")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data, data
        assert data["status"] == "in_progress"
        assert data["group_id"] == data["session_id"]
        assert data["group_index"] == 1
        assert data["group_type"] == "normal"
        assert data["word_count"] == len(data["items"])
        assert data["source_session_item_ids"] == []
        assert data["date"] == date.today().isoformat()
        assert data["primary_accent"] == "US"
        assert data["daily_word_count"] == 10
        assert len(data["items"]) == 3  # fixture has 3 words
        # Session row exists in DB
        conn = get_connection(seeded_db)
        s = get_session_for_date(conn, "default", date.today().isoformat(), "US")
        conn.close()
        assert s is not None
        assert s.status == "in_progress"

    def test_second_today_returns_same_session(self, client, seeded_db):
        first = client.get("/api/today").json()
        second = client.get("/api/today").json()
        assert second["session_id"] == first["session_id"]
        assert len(second["items"]) == len(first["items"])
        for a, b in zip(first["items"], second["items"]):
            assert a["session_item_id"] == b["session_item_id"]
            assert a["word_id"] == b["word_id"]

    def test_second_today_creates_no_duplicate(self, client, seeded_db):
        client.get("/api/today")
        client.get("/api/today")
        conn = get_connection(seeded_db)
        today = date.today().isoformat()
        # Try to create another — should be caught by uniqueness of session_id
        items = conn.execute(
            "SELECT COUNT(*) as cnt FROM daily_sessions WHERE session_date = ?", (today,)
        ).fetchone()
        conn.close()
        assert items["cnt"] == 1

    def test_completed_group_allows_next_same_day_group(self, client, seeded_db):
        first = client.get("/api/today").json()
        conn = get_connection(seeded_db)
        conn.execute(
            """
            UPDATE daily_sessions
            SET status = 'completed', completed_at = '2026-06-16T00:00:00Z'
            WHERE id = ?
            """,
            (first["session_id"],),
        )
        conn.commit()
        conn.close()

        second = client.get("/api/today").json()

        assert second["session_id"] != first["session_id"]
        assert second["group_index"] == 2
        assert second["group_type"] == "normal"

        conn = get_connection(seeded_db)
        today = date.today().isoformat()
        sessions = conn.execute(
            """
            SELECT id, group_index, group_type, status
            FROM daily_sessions
            WHERE user_id = 'default' AND session_date = ?
            ORDER BY group_index
            """,
            (today,),
        ).fetchall()
        conn.close()

        assert [(row["group_index"], row["group_type"]) for row in sessions] == [
            (1, "normal"),
            (2, "normal"),
        ]

    def test_items_have_required_fields(self, client, seeded_db):
        resp = client.get("/api/today")
        data = resp.json()
        for item in data["items"]:
            assert "session_item_id" in item
            assert "word_id" in item
            assert "display_ipa" in item
            assert "word" in item
            assert "question" in item
            assert item["question"]["type"] == "choose_ipa"
            assert "choices" in item["question"]
            assert len(item["question"]["choices"]) >= 2  # correct + distractors

    def test_items_use_us_accent(self, client, seeded_db):
        resp = client.get("/api/today")
        data = resp.json()
        for item in data["items"]:
            conn = get_connection(seeded_db)
            w = get_word_by_id(conn, item["word_id"])
            conn.close()
            assert w is not None
            # display_ipa should match ipa_us
            assert item["display_ipa"] == w.ipa_us

    def test_disabled_words_not_scheduled(self, client, seeded_db):
        # Mark one word as disabled and verify it's excluded.
        conn = get_connection(seeded_db)
        conn.execute("UPDATE words SET content_status = 'disabled' WHERE id = 'cat'")
        conn.commit()
        conn.close()

        resp = client.get("/api/today")
        data = resp.json()
        word_ids = [item["word_id"] for item in data["items"]]
        assert "cat" not in word_ids

    def test_daily_word_count_respected(self, client, seeded_db):
        # Lower daily_word_count and verify fewer items.
        conn = get_connection(seeded_db)
        conn.execute("UPDATE settings SET daily_word_count = 1 WHERE user_id = 'default'")
        conn.commit()
        conn.close()

        resp = client.get("/api/today")
        data = resp.json()
        assert len(data["items"]) <= 1

    def test_single_item_attempt_completes_group_and_next_today_creates_group(
        self, client, seeded_db
    ):
        conn = get_connection(seeded_db)
        conn.execute("UPDATE settings SET daily_word_count = 1 WHERE user_id = 'default'")
        conn.commit()
        conn.close()

        first = client.get("/api/today").json()
        item = first["items"][0]
        attempt = client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        }).json()

        assert attempt["next_action"] == "group_complete"

        second = client.get("/api/today").json()
        assert second["session_id"] != first["session_id"]
        assert second["group_index"] == 2

    def test_next_normal_action_reports_intended_group(self, client, seeded_db):
        conn = get_connection(seeded_db)
        conn.execute("UPDATE settings SET daily_word_count = 1 WHERE user_id = 'default'")
        conn.commit()
        conn.close()

        first = client.get("/api/today").json()
        item = first["items"][0]
        client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        })

        resp = client.post("/api/practice/next-normal")
        assert resp.status_code == 200
        data = resp.json()

        assert data["session_id"] != first["session_id"]
        assert data["group_index"] == 2
        assert data["group_type"] == "normal"
        assert data["origin"] == "normal_next"
        assert data["source_scope"] == "normal_next"
        assert data["action_label"] == "Start Group 2"

    def test_recent_mistake_review_empty_queue_is_stable(self, client):
        resp = client.post("/api/review/recent-mistakes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["group_type"] == "mistake_review"
        assert data["status"] == "empty"
        assert data["items"] == []
        assert data["source_count"] == 0
        assert data["source_scope"] == "recent_global"

    def test_recent_mistake_review_group_reuses_attempt_path(self, client, seeded_db):
        today = client.get("/api/today").json()
        missed = today["items"][0]
        miss_resp = client.post("/api/attempt", json={
            "session_item_id": missed["session_item_id"],
            "selected_answer": "/wrong/",
        })
        assert miss_resp.status_code == 200
        assert miss_resp.json()["is_correct"] is False

        review_resp = client.post("/api/review/recent-mistakes")
        assert review_resp.status_code == 200
        review = review_resp.json()

        assert review["group_type"] == "mistake_review"
        assert review["group_index"] == 2
        assert review["source_scope"] == "recent_global"
        assert review["source_session_item_ids"] == [missed["session_item_id"]]
        assert review["items"][0]["word_id"] == missed["word_id"]

        second_review = client.post("/api/review/recent-mistakes").json()
        assert second_review["session_id"] == review["session_id"]

        review_item = review["items"][0]
        retry = client.post("/api/attempt", json={
            "session_item_id": review_item["session_item_id"],
            "selected_answer": review_item["display_ipa"],
        })
        assert retry.status_code == 200
        assert retry.json()["is_correct"] is True

        conn = get_connection(seeded_db)
        attempts = conn.execute(
            "SELECT COUNT(*) AS cnt FROM attempts WHERE word_id = ?",
            (missed["word_id"],),
        ).fetchone()
        stats = conn.execute(
            """
            SELECT attempt_count
            FROM phoneme_stats
            WHERE user_id = 'default' AND primary_accent = 'US'
            ORDER BY attempt_count DESC
            LIMIT 1
            """
        ).fetchone()
        conn.close()

        assert attempts["cnt"] == 2
        assert stats["attempt_count"] == 2

    def test_current_group_review_uses_only_source_group_misses(self, client, seeded_db):
        today = client.get("/api/today").json()
        missed = today["items"][0]
        client.post("/api/attempt", json={
            "session_item_id": missed["session_item_id"],
            "selected_answer": "/wrong/",
        })

        resp = client.post("/api/review/current-group", json={
            "group_id": today["group_id"],
        })
        assert resp.status_code == 200
        review = resp.json()

        assert review["group_type"] == "mistake_review"
        assert review["source_scope"] == "current_group"
        assert review["source_group_id"] == today["group_id"]
        assert review["source_session_item_ids"] == [missed["session_item_id"]]
        assert review["items"][0]["word_id"] == missed["word_id"]

    def test_current_group_review_empty_queue_is_non_error(self, client, seeded_db):
        today = client.get("/api/today").json()
        resp = client.post("/api/review/current-group", json={
            "group_id": today["group_id"],
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["group_type"] == "mistake_review"
        assert data["status"] == "empty"
        assert data["source_scope"] == "current_group"
        assert data["source_group_id"] == today["group_id"]
        assert data["source_count"] == 0

    def test_current_group_review_rejects_unknown_group(self, client):
        resp = client.post("/api/review/current-group", json={
            "group_id": "missing-group",
        })
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "GROUP_NOT_FOUND"

    def test_current_group_review_rejects_missing_group_id(self, client):
        resp = client.post("/api/review/current-group", json={})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "INVALID_REVIEW_SOURCE"

    def test_current_and_recent_review_scopes_do_not_reuse_each_other(
        self, client, seeded_db
    ):
        today = client.get("/api/today").json()
        missed = today["items"][0]
        client.post("/api/attempt", json={
            "session_item_id": missed["session_item_id"],
            "selected_answer": "/wrong/",
        })

        current = client.post("/api/review/current-group", json={
            "group_id": today["group_id"],
        }).json()
        recent = client.post("/api/review/recent-mistakes").json()

        assert current["session_id"] != recent["session_id"]
        assert current["source_scope"] == "current_group"
        assert current["source_group_id"] == today["group_id"]
        assert recent["source_scope"] == "recent_global"
        assert "source_group_id" not in recent

    def test_focus_action_starts_weak_focus_group_and_clear_returns_normal(
        self, client, seeded_db
    ):
        conn = get_connection(seeded_db)
        conn.execute("UPDATE settings SET daily_word_count = 1 WHERE user_id = 'default'")
        conn.commit()
        conn.close()

        resp = client.post("/api/practice/focus", json={
            "focus_phonemes": ["/æ/"],
        })
        assert resp.status_code == 200
        focused = resp.json()

        assert focused["group_type"] == "weak_focus"
        assert focused["source_scope"] == "focus_selection"
        assert focused["focus_phonemes"] == ["/æ/"]
        assert [item["word_id"] for item in focused["items"]] == ["cat"]

        clear_resp = client.post("/api/practice/clear-focus")
        assert clear_resp.status_code == 200
        cleared = clear_resp.json()

        assert cleared["group_type"] == "normal"
        assert cleared["origin"] == "focus_clear"
        assert cleared["source_scope"] == "normal_current"
        assert cleared["focus_phonemes"] == []

    def test_focus_action_resumes_active_weak_focus_group(self, client, seeded_db):
        first = client.post("/api/practice/focus", json={
            "focus_phonemes": ["/æ/"],
        }).json()
        second = client.post("/api/practice/focus", json={
            "focus_phonemes": ["/æ/"],
        }).json()

        assert second["session_id"] == first["session_id"]
        assert second["origin"] == "focus_resume"
        assert second["source_scope"] == "focus_selection"
        assert second["focus_phonemes"] == ["/æ/"]

    def test_different_focus_selection_creates_new_weak_focus_group(
        self, client, seeded_db
    ):
        first = client.post("/api/practice/focus", json={
            "focus_phonemes": ["/æ/"],
        }).json()
        second = client.post("/api/practice/focus", json={
            "focus_phonemes": ["/ʃ/"],
        }).json()

        assert second["session_id"] != first["session_id"]
        assert second["group_type"] == "weak_focus"
        assert second["origin"] == "focus_start"
        assert second["source_scope"] == "focus_selection"
        assert second["focus_phonemes"] == ["/ʃ/"]

    def test_focus_action_rejects_invalid_focus_payload(self, client):
        resp = client.post("/api/practice/focus", json={
            "focus_phonemes": [""],
        })
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "INVALID_FOCUS"

    def test_focus_action_rejects_empty_focus_payload(self, client):
        resp = client.post("/api/practice/focus", json={
            "focus_phonemes": [],
        })
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "INVALID_FOCUS"

    def test_fresh_today_uses_focus_phoneme_setting(self, client, seeded_db):
        conn = get_connection(seeded_db)
        conn.execute(
            """
            UPDATE settings
            SET daily_word_count = 1, focus_phonemes = ?
            WHERE user_id = 'default'
            """,
            (json.dumps(["/æ/"]),),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/today")
        data = resp.json()

        assert [item["word_id"] for item in data["items"]] == ["cat"]

    def test_existing_today_session_is_stable_after_settings_change(self, client, seeded_db):
        conn = get_connection(seeded_db)
        conn.execute(
            """
            UPDATE settings
            SET daily_word_count = 1, focus_phonemes = ?
            WHERE user_id = 'default'
            """,
            (json.dumps(["/æ/"]),),
        )
        conn.commit()
        conn.close()

        first = client.get("/api/today").json()
        assert [item["word_id"] for item in first["items"]] == ["cat"]

        conn = get_connection(seeded_db)
        conn.execute(
            """
            UPDATE settings
            SET daily_word_count = 3, focus_phonemes = ?
            WHERE user_id = 'default'
            """,
            (json.dumps(["/ʃ/"]),),
        )
        conn.commit()
        conn.close()

        second = client.get("/api/today").json()

        assert second["session_id"] == first["session_id"]
        assert [item["session_item_id"] for item in second["items"]] == [
            item["session_item_id"] for item in first["items"]
        ]
        assert [item["word_id"] for item in second["items"]] == ["cat"]

    def test_weak_phoneme_stats_influence_fresh_today_session(self, client, seeded_db):
        conn = get_connection(seeded_db)
        conn.execute("UPDATE settings SET daily_word_count = 1 WHERE user_id = 'default'")
        conn.execute(
            """
            INSERT OR REPLACE INTO phoneme_stats (
                user_id, primary_accent, phoneme_id, attempt_count, correct_count,
                last_attempt_at, last_wrong_at, mastery_status
            ) VALUES (
                'default', 'US', '/æ/', 6, 1,
                '2026-06-09T00:00:00Z', '2026-06-09T00:00:00Z', 'weak'
            )
            """
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/today")
        data = resp.json()

        assert [item["word_id"] for item in data["items"]] == ["cat"]

    def test_recent_words_are_suppressed_for_fresh_today_session(self, client, seeded_db):
        conn = get_connection(seeded_db)
        conn.execute("UPDATE settings SET daily_word_count = 1 WHERE user_id = 'default'")
        session = DailySession(
            id="2026-06-09-default",
            user_id="default",
            session_date="2026-06-09",
            primary_accent="US",
            status="completed",
            created_at="2026-06-09T00:00:00Z",
        )
        create_session(conn, session)
        create_session_item(
            conn,
            SessionItem(
                id="2026-06-09-default_item_001",
                session_id=session.id,
                word_id="cat",
                order_index=0,
                target_phonemes=["/k/", "/æ/", "/t/"],
                question_type="choose_ipa",
                status="complete",
            ),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/today")
        data = resp.json()

        assert "cat" not in [item["word_id"] for item in data["items"]]

    def test_content_not_ready_without_import(self, tmp_path):
        """Without running import first, /api/today returns CONTENT_NOT_READY."""
        db_path = str(tmp_path / "empty.sqlite")
        conn = get_connection(db_path)
        init_db(conn)
        conn.close()

        import app.db as db_mod

        orig = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            c = TestClient(app)
            resp = c.get("/api/today")
            assert resp.status_code == 200
            data = resp.json()
            assert data["error"] == "CONTENT_NOT_READY"
        finally:
            db_mod.DEFAULT_DB_PATH = orig


class TestCore300TodayReadiness:
    """Regression coverage for the full Core 300 runtime content path."""

    def test_core_300_today_keeps_daily_count_to_settings(self, core_300_client):
        resp = core_300_client.get("/api/today")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data, data
        assert data["daily_word_count"] == 10
        assert len(data["items"]) == 10

    def test_core_300_disabled_words_are_not_scheduled(self, core_300_client):
        # Disable one of the scheduled candidates and confirm it's filtered.
        import app.db as db_mod

        conn = get_connection(db_mod.DEFAULT_DB_PATH)
        first_resp = core_300_client.get("/api/today")
        assert first_resp.status_code == 200
        first_data = first_resp.json()
        session_id = first_data["session_id"]

        first_id = conn.execute(
            "SELECT word_id FROM session_items WHERE session_id = ? ORDER BY order_index LIMIT 1",
            (session_id,),
        ).fetchone()
        assert first_id is not None

        conn.execute(
            "UPDATE words SET content_status = 'disabled' WHERE id = ?",
            (first_id[0],),
        )
        conn.commit()

        # Existing session should still be stable; create a fresh one by deleting the
        # existing row to emulate next-day scheduling semantics.
        conn.execute(
            "DELETE FROM session_items WHERE session_id = ?",
            (session_id,),
        )
        conn.execute(
            "DELETE FROM daily_sessions WHERE id = ?",
            (session_id,),
        )
        conn.commit()
        conn.close()

        resp = core_300_client.get("/api/today")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data, data
        assert first_id[0] not in {item["word_id"] for item in data["items"]}

    def test_core_300_focus_phonemes_continue_to_work(self, core_300_client):
        import app.db as db_mod

        conn = get_connection(db_mod.DEFAULT_DB_PATH)
        focus_id = conn.execute(
            """
            SELECT id
            FROM words
            WHERE content_status != 'disabled'
              AND phoneme_tags_us LIKE '%/ʌ/%'
            LIMIT 1
            """,
        ).fetchone()
        if focus_id is None:
            conn.close()
            pytest.skip("No /ʌ/ word available in current core_300 fixture")

        conn.execute(
            "UPDATE settings SET focus_phonemes = ? WHERE user_id = 'default'",
            (json.dumps(["/ʌ/"]),),
        )
        conn.commit()
        conn.close()

        resp = core_300_client.get("/api/today")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data, data
        assert focus_id[0] in {item["word_id"] for item in data["items"]}


# ---------------------------------------------------------------------------
# Session store tests (unit-level)
# ---------------------------------------------------------------------------


class TestSessionStore:
    @pytest.fixture(autouse=True)
    def _init(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        conn = get_connection(db_path)
        init_db(conn)
        # Insert required settings so FK-based tests pass
        conn.execute(
            """
            INSERT OR REPLACE INTO settings (
                user_id, primary_accent, daily_word_count,
                show_translation, show_accent_compare,
                practice_mode, review_strength, updated_at
            ) VALUES ('default', 'US', 10, 1, 0, 'ipa_first', 'normal', '2026-06-06T00:00:00Z')
            """
        )
        # Insert a test word
        conn.execute(
            """
            INSERT OR REPLACE INTO words (
                id, word, level, ipa_us, phoneme_tags_us, content_status
            ) VALUES ('ship', 'ship', 'beginner', '/ʃɪp/', '["/ʃ/", "/ɪ/", "/p/"]', 'core_selected')
            """
        )
        conn.commit()
        self.conn = conn
        yield
        conn.close()

    def test_create_and_retrieve_session(self):
        s = DailySession(
            id="2026-06-06-default",
            user_id="default",
            session_date="2026-06-06",
            primary_accent="US",
            status="in_progress",
            created_at="2026-06-06T00:00:00Z",
        )
        create_session(self.conn, s)
        got = get_session_for_date(self.conn, "default", "2026-06-06", "US")
        assert got is not None
        assert got.id == "2026-06-06-default"
        assert got.status == "in_progress"

    def test_get_missing_session(self):
        assert (
            get_session_for_date(self.conn, "default", "2099-01-01", "US") is None
        )

    def test_create_and_retrieve_session_items(self):
        sess = DailySession(
            id="s1",
            user_id="default",
            session_date="2026-06-06",
            primary_accent="US",
            status="in_progress",
            created_at="2026-06-06T00:00:00Z",
        )
        create_session(self.conn, sess)

        item = SessionItem(
            id="s1_item_001",
            session_id="s1",
            word_id="ship",
            order_index=0,
            target_phonemes=["/ʃ/", "/ɪ/", "/p/"],
            question_type="choose_ipa",
            status="pending",
        )
        create_session_item(self.conn, item)

        items = get_session_items(self.conn, "s1")
        assert len(items) == 1
        assert items[0].id == "s1_item_001"
        assert items[0].word_id == "ship"
        assert items[0].target_phonemes == ["/ʃ/", "/ɪ/", "/p/"]
