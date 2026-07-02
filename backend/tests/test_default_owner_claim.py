from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.db import get_connection
from app.services.db_schema import init_db
from scripts.default_owner_claim import build_default_owner_claim_report

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "default_owner_claim.py"


def _seed_default_runtime_db(db_path: Path) -> None:
    conn = get_connection(str(db_path))
    try:
        init_db(conn)
        conn.execute(
            """
            INSERT INTO words (
                id, word, level, ipa_us, phoneme_tags_us, content_status
            ) VALUES ('ship', 'ship', 'entry', '/ʃɪp/', '["/ʃ/"]', 'safe')
            """
        )
        conn.execute(
            """
            INSERT INTO users (
                id, username, password_hash, is_owner, is_active, created_at, updated_at
            ) VALUES (
                'default', 'owner', 'hash', 1, 1,
                '2026-07-02T00:00:00Z', '2026-07-02T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO settings (
                user_id, primary_accent, daily_word_count, show_translation,
                show_accent_compare, practice_mode, review_strength, learner_level,
                ui_language, focus_phonemes, updated_at
            ) VALUES (
                'default', 'US', 2, 1, 0, 'ipa_first', 'normal', 'entry',
                'zh-CN', '[]', '2026-07-02T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO daily_sessions (
                id, user_id, session_date, primary_accent, status, created_at,
                completed_at, group_index, group_type, learner_level,
                source_session_item_ids, focus_phonemes
            ) VALUES (
                'session-default-1', 'default', '2026-07-02', 'US', 'in_progress',
                '2026-07-02T00:00:00Z', NULL, 1, 'normal', 'entry', '[]', '[]'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO daily_sessions (
                id, user_id, session_date, primary_accent, status, created_at,
                completed_at, group_index, group_type, learner_level,
                source_session_item_ids, focus_phonemes
            ) VALUES (
                'session-default-2', 'default', '2026-07-01', 'US', 'completed',
                '2026-07-01T00:00:00Z', '2026-07-01T00:10:00Z', 2,
                'mistake_review', 'entry', '[]', '[]'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO session_items (
                id, session_id, word_id, order_index, target_phonemes,
                question_type, status
            ) VALUES (
                'item-default-1', 'session-default-1', 'ship', 0, '["/ʃ/"]',
                'ipa_choice', 'pending'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO session_items (
                id, session_id, word_id, order_index, target_phonemes,
                question_type, status
            ) VALUES (
                'item-default-2', 'session-default-2', 'ship', 0, '["/ʃ/"]',
                'ipa_choice', 'completed'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO attempts (
                id, user_id, session_item_id, word_id, primary_accent,
                question_type, target_phoneme, selected_answer, correct_answer,
                is_correct, created_at
            ) VALUES (
                'attempt-default-1', 'default', 'item-default-2', 'ship', 'US',
                'ipa_choice', '/ʃ/', '/sɪp/', '/ʃɪp/', 0,
                '2026-07-01T00:05:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO phoneme_stats (
                user_id, primary_accent, phoneme_id, attempt_count, correct_count,
                last_attempt_at, last_wrong_at, mastery_status
            ) VALUES (
                'default', 'US', '/ʃ/', 3, 1,
                '2026-07-01T00:05:00Z', '2026-07-01T00:05:00Z', 'weak'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _row_counts(db_path: Path) -> dict[str, int]:
    conn = get_connection(str(db_path))
    try:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()["cnt"]
            for table in [
                "users",
                "settings",
                "daily_sessions",
                "session_items",
                "attempts",
                "phoneme_stats",
            ]
        }
    finally:
        conn.close()


def test_default_owner_claim_report_counts_default_runtime_rows(tmp_path: Path):
    db_path = tmp_path / "tiny_ipa.sqlite"
    _seed_default_runtime_db(db_path)

    conn = get_connection(str(db_path))
    try:
        report = build_default_owner_claim_report(conn, db_path=str(db_path))
    finally:
        conn.close()

    assert report["dry_run"] is True
    assert report["mutation_authorized"] is False
    assert report["apply_mode_available"] is False
    assert report["row_counts"] == {
        "users_default": 1,
        "settings_default": 1,
        "daily_sessions_default": 2,
        "session_items_owned_by_default_sessions": 2,
        "attempts_default_user": 1,
        "attempts_on_default_session_items": 1,
        "phoneme_stats_default": 1,
        "auth_sessions_default": 0,
    }
    assert report["breakdown"]["daily_sessions_by_status"] == {
        "completed": 1,
        "in_progress": 1,
    }
    assert report["breakdown"]["session_items_by_group_type"] == {
        "mistake_review": 1,
        "normal": 1,
    }
    assert (
        report["owner_claim_strategy"]["future_real_apply_requires_human_decision_contract"]
        is True
    )
    assert report["owner_claim_strategy"]["no_real_db_mutation_in_this_tool"] is True


def test_default_owner_claim_cli_is_read_only_and_outputs_json(tmp_path: Path):
    db_path = tmp_path / "tiny_ipa.sqlite"
    _seed_default_runtime_db(db_path)
    before = _row_counts(db_path)

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--db-url", str(db_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(completed.stdout)
    assert report["row_counts"]["daily_sessions_default"] == 2
    assert report["backup_guidance"]
    assert _row_counts(db_path) == before


def test_default_owner_claim_cli_does_not_create_missing_database(tmp_path: Path):
    db_path = tmp_path / "missing.sqlite"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--db-url", str(db_path)],
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert not db_path.exists()
