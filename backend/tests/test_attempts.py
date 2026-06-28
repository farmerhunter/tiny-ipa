"""Tests for POST /api/attempt — grading, persistence, and phoneme stats."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from import_words import import_words  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.main import app  # noqa: E402
from app.services.progress import _compute_mastery, update_phoneme_stats  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTENT_SAMPLE = FIXTURES / "content_sample.json"
PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"


@pytest.fixture(name="seeded_db")
def seeded_db_fixture(tmp_path: Path) -> str:
    """Database pre-loaded with the 3-word fixture + imported phonemes."""
    db_path = str(tmp_path / "test.sqlite")
    import_words(
        source_path=CONTENT_SAMPLE,
        phonemes_path=PHONEMES_PATH,
        db_path=db_path,
    )
    import app.db as db_mod

    orig = db_mod.DEFAULT_DB_PATH
    db_mod.DEFAULT_DB_PATH = db_path
    yield db_path
    db_mod.DEFAULT_DB_PATH = orig


@pytest.fixture(name="client")
def client_fixture(seeded_db: str) -> TestClient:
    return TestClient(app)


def _get_first_item(client: TestClient) -> dict:
    """Start today's normal session and return the first item."""
    today = client.post("/api/practice/next-normal").json()
    assert "error" not in today, today
    items = today["items"]
    assert len(items) > 0
    return items[0]


# ---------------------------------------------------------------------------
# Mastery status
# ---------------------------------------------------------------------------


class TestMasteryStatus:
    def test_new(self):
        assert _compute_mastery(0, 0) == "new"
        assert _compute_mastery(1, 0) == "new"
        assert _compute_mastery(2, 2) == "new"

    def test_weak(self):
        # >= 3 attempts AND accuracy < 0.70
        assert _compute_mastery(3, 0) == "weak"  # 0%
        assert _compute_mastery(3, 1) == "weak"  # 33%
        assert _compute_mastery(3, 2) == "weak"  # 66%
        assert _compute_mastery(10, 5) == "weak"  # 50%

    def test_learning(self):
        # >= 3 attempts AND 0.70 <= accuracy < 0.85
        assert _compute_mastery(3, 2) == "weak"  # 66% -> still weak
        assert _compute_mastery(5, 4) == "learning"  # 80%
        assert _compute_mastery(3, 3) == "learning"  # 100% but only 3 attempts
        assert _compute_mastery(4, 3) == "learning"  # 75%

    def test_mastered(self):
        # >= 5 attempts AND accuracy >= 0.85
        assert _compute_mastery(5, 5) == "mastered"  # 100%
        assert _compute_mastery(6, 5) == "learning"  # 83% < 85%
        assert _compute_mastery(10, 9) == "mastered"  # 90%


class TestAttemptRoute:
    """Integration tests for POST /api/attempt."""

    def test_correct_answer_creates_attempt(self, client, seeded_db):
        item = _get_first_item(client)
        correct = item["display_ipa"]

        resp = client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": correct,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is True
        assert data["correct_answer"] == correct
        assert len(data["updated_phonemes"]) > 0
        assert data["next_action"] == "next_item"

    def test_wrong_answer_creates_attempt(self, client, seeded_db):
        item = _get_first_item(client)
        resp = client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": "/wrong/",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is False
        assert data["correct_answer"] == item["display_ipa"]

    def test_uk_comparison_ipa_is_not_accepted_for_us_session(self, client, seeded_db):
        conn = get_connection(seeded_db)
        conn.execute(
            """
            UPDATE words
            SET ipa_uk = '/ʃɪp-uk/', phoneme_tags_uk = '["/ʃ/", "/ɪ/", "/p/"]'
            WHERE id = 'ship'
            """
        )
        conn.execute("UPDATE settings SET show_accent_compare = 1 WHERE user_id = 'default'")
        conn.commit()
        conn.close()

        today = client.post("/api/practice/next-normal").json()
        item = next(item for item in today["items"] if item["word_id"] == "ship")
        assert item["display_ipa"] == "/ʃɪp/"
        assert item["accent_compare"]["comparison"]["ipa"] == "/ʃɪp-uk/"

        resp = client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": "/ʃɪp-uk/",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is False
        assert data["correct_answer"] == "/ʃɪp/"

        conn = get_connection(seeded_db)
        row = conn.execute(
            """
            SELECT selected_answer, correct_answer, is_correct, primary_accent
            FROM attempts
            WHERE session_item_id = ?
            """,
            (item["session_item_id"],),
        ).fetchone()
        conn.close()
        assert row["selected_answer"] == "/ʃɪp-uk/"
        assert row["correct_answer"] == "/ʃɪp/"
        assert row["is_correct"] == 0
        assert row["primary_accent"] == "US"

    def test_attempt_persisted(self, client, seeded_db):
        item = _get_first_item(client)
        client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        })
        # Verify in DB
        conn = get_connection(seeded_db)
        rows = conn.execute(
            "SELECT * FROM attempts WHERE session_item_id = ?",
            (item["session_item_id"],),
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["is_correct"] == 1

    def test_missing_item_returns_error(self, client):
        resp = client.post("/api/attempt", json={
            "session_item_id": "nonexistent_item_999",
            "selected_answer": "/ʃɪp/",
        })
        assert resp.status_code == 404
        data = resp.json()
        assert data["detail"]["error"] == "ITEM_NOT_FOUND"

    def test_missing_session_item_id(self, client):
        resp = client.post("/api/attempt", json={
            "selected_answer": "/ʃɪp/",
        })
        assert resp.status_code == 400
        data = resp.json()
        assert data["detail"]["error"] == "INVALID_ATTEMPT"

    def test_phoneme_stats_updated(self, client, seeded_db):
        item = _get_first_item(client)
        client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        })
        resp_data = client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": "/wrong/",
        }).json()

        # Should show attempt_count=2, correct_count=1 for each phoneme
        for ps in resp_data["updated_phonemes"]:
            assert ps["attempt_count"] == 2
            assert ps["correct_count"] == 1

    def test_stats_are_accent_partitioned(self, client, seeded_db):
        """Stats written with primary_accent='US' are persisted."""
        item = _get_first_item(client)
        client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        })
        conn = get_connection(seeded_db)
        rows = conn.execute(
            "SELECT * FROM phoneme_stats WHERE primary_accent = 'US'"
        ).fetchall()
        conn.close()
        assert len(rows) > 0
        for r in rows:
            assert r["primary_accent"] == "US"

    def test_uk_session_attempt_updates_only_uk_phoneme_stats(self, client, seeded_db):
        """A lower-level UK session writes UK stats without touching US stats."""
        conn = get_connection(seeded_db)
        session_id = "uk-session"
        item_id = f"{session_id}_item_001"
        conn.execute(
            """
            INSERT INTO daily_sessions (
                id, user_id, session_date, primary_accent, status, created_at,
                group_index, group_type, learner_level
            ) VALUES (?, 'default', '2026-06-28', 'UK', 'in_progress',
                '2026-06-28T10:00:00Z', 1, 'normal', 'entry')
            """,
            (session_id,),
        )
        conn.execute(
            """
            INSERT INTO session_items (
                id, session_id, word_id, order_index, target_phonemes,
                question_type, status
            ) VALUES (?, ?, 'ship', 0, ?, 'choose_ipa', 'pending')
            """,
            (item_id, session_id, json.dumps(["/ʃ/"])),
        )
        conn.execute(
            """
            INSERT INTO phoneme_stats (
                user_id, primary_accent, phoneme_id, attempt_count, correct_count,
                last_attempt_at, mastery_status
            ) VALUES ('default', 'US', '/ʃ/', 7, 7, '2026-06-27T10:00:00Z', 'mastered')
            """
        )
        conn.commit()
        conn.close()

        resp = client.post("/api/attempt", json={
            "session_item_id": item_id,
            "selected_answer": "/wrong/",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is False
        assert data["updated_phonemes"] == [
            {
                "phoneme": "/ʃ/",
                "attempt_count": 1,
                "correct_count": 0,
                "mastery_status": "new",
            }
        ]

        conn = get_connection(seeded_db)
        rows = conn.execute(
            """
            SELECT primary_accent, attempt_count, correct_count
            FROM phoneme_stats
            WHERE user_id = 'default' AND phoneme_id = '/ʃ/'
            ORDER BY primary_accent
            """
        ).fetchall()
        conn.close()

        stats_summary = [
            (row["primary_accent"], row["attempt_count"], row["correct_count"])
            for row in rows
        ]
        assert stats_summary == [("UK", 1, 0), ("US", 7, 7)]

    def test_last_wrong_at_preserved_after_correct(self, client, seeded_db):
        """After wrong→correct, last_wrong_at should persist, not be cleared."""
        item = _get_first_item(client)
        # Submit wrong answer first
        client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": "/wrong/",
        })
        # Submit correct answer
        client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": item["display_ipa"],
        })
        conn = get_connection(seeded_db)
        rows = conn.execute(
            "SELECT phoneme_id, last_wrong_at FROM phoneme_stats WHERE primary_accent = 'US'"
        ).fetchall()
        conn.close()
        for r in rows:
            assert r["last_wrong_at"] is not None, (
                f"last_wrong_at was cleared for phoneme {r['phoneme_id']} after correct attempt"
            )

    def test_client_correct_answer_ignored(self, client, seeded_db):
        """Client sending correct_answer in body is ignored."""
        item = _get_first_item(client)
        resp = client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": "/bogus/",
            "correct_answer": "/client_fake/",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Server should have graded against the real answer, not /client_fake/
        assert data["is_correct"] is False
        assert data["correct_answer"] == item["display_ipa"]

    def test_empty_selected_answer(self, client):
        item = _get_first_item(client)
        resp = client.post("/api/attempt", json={
            "session_item_id": item["session_item_id"],
            "selected_answer": "",
        })
        assert resp.status_code == 200
        assert resp.json()["is_correct"] is False


# ---------------------------------------------------------------------------
# Progress service (unit tests)
# ---------------------------------------------------------------------------


class TestProgressService:
    @pytest.fixture(autouse=True)
    def _init(self, tmp_path):
        db_path = str(tmp_path / "test.sqlite")
        conn = get_connection(db_path)
        from app.services.db_schema import init_db
        init_db(conn)
        # Seed phoneme_stats with pre-existing data
        conn.execute(
            """
            INSERT OR REPLACE INTO phoneme_stats
                (user_id, primary_accent, phoneme_id, attempt_count, correct_count,
                 mastery_status, last_attempt_at)
            VALUES
                ('default', 'US', '/ʃ/', 2, 1, 'new', '2026-06-05T00:00:00Z')
            """
        )
        conn.commit()
        self.conn = conn
        self.db_path = db_path
        yield
        conn.close()

    def test_update_existing_stat(self):
        updated = update_phoneme_stats(
            self.conn,
            user_id="default",
            primary_accent="US",
            target_phonemes=["/ʃ/"],
            is_correct=True,
            timestamp="2026-06-06T00:00:00Z",
        )
        assert len(updated) == 1
        assert updated[0]["phoneme"] == "/ʃ/"
        assert updated[0]["attempt_count"] == 3
        assert updated[0]["correct_count"] == 2
        # 3 attempts, 2/3 = 67% < 70% → weak
        assert updated[0]["mastery_status"] == "weak"

    def test_update_new_stat(self):
        updated = update_phoneme_stats(
            self.conn,
            user_id="default",
            primary_accent="US",
            target_phonemes=["/ɪ/"],
            is_correct=False,
            timestamp="2026-06-06T00:00:00Z",
        )
        assert updated[0]["attempt_count"] == 1
        assert updated[0]["correct_count"] == 0
        assert updated[0]["mastery_status"] == "new"

    def test_multiple_phonemes(self):
        updated = update_phoneme_stats(
            self.conn,
            user_id="default",
            primary_accent="US",
            target_phonemes=["/ʃ/", "/ɪ/", "/p/"],
            is_correct=True,
            timestamp="2026-06-06T00:00:00Z",
        )
        assert len(updated) == 3
        symbols = {ps["phoneme"] for ps in updated}
        assert symbols == {"/ʃ/", "/ɪ/", "/p/"}
