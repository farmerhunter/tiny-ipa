from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = REPO_ROOT / "backend"
BACKEND_SCRIPTS = BACKEND_DIR / "scripts"

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_SCRIPTS))

from app.db import get_connection  # noqa: E402
from app.models import User  # noqa: E402
from app.services.auth import hash_password  # noqa: E402
from app.services.db_store import create_user, get_user_by_id  # noqa: E402
from import_words import import_words  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_m11_real_db.py <db-path>")

    db_path = sys.argv[1]
    content_path = BACKEND_DIR / "tests" / "fixtures" / "content_sample.json"
    phonemes_path = REPO_ROOT / "content" / "phonemes.json"

    report = import_words(
        source_path=content_path,
        phonemes_path=phonemes_path,
        db_path=db_path,
    )
    if report.get("errors"):
        raise SystemExit(json.dumps(report["errors"], ensure_ascii=False))

    with get_connection(db_path) as conn:
        if get_user_by_id(conn, "default") is None:
            create_user(
                conn,
                User(
                    id="default",
                    username="owner",
                    password_hash=hash_password("secret123"),
                    is_owner=True,
                    is_active=True,
                    created_at="2026-07-02T00:00:00+00:00",
                    updated_at="2026-07-02T00:00:00+00:00",
                ),
            )
        conn.execute(
            """
            UPDATE settings
            SET daily_word_count = 1,
                review_strength = 'quick',
                learner_level = 'entry',
                ui_language = 'en-US',
                focus_phonemes = ?
            WHERE user_id = 'default'
            """,
            (json.dumps(["/æ/"]),),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO phoneme_stats (
                user_id, primary_accent, phoneme_id, attempt_count, correct_count,
                last_attempt_at, last_wrong_at, mastery_status
            ) VALUES (
                'default', 'US', '/ʃ/', 8, 0,
                '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z', 'weak'
            )
            """
        )


if __name__ == "__main__":
    main()
