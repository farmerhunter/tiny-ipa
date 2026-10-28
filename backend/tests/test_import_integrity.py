import copy
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))

import import_words as importer  # noqa: E402
from validate_content import load_phoneme_set, validate_words  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.models import Attempt  # noqa: E402
from app.services.db_store import create_attempt  # noqa: E402
from app.services.sessions import build_next_normal_group_response  # noqa: E402

SOURCE = ROOT / "backend/tests/fixtures/content_sample.json"
PHONEMES = ROOT / "content/phonemes.json"


def words():
    return json.loads(SOURCE.read_text())["words"]


def snapshot(database):
    with get_connection(str(database)) as conn:
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {
            name: [tuple(row) for row in conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid')]
            for name in names
        }


@pytest.mark.parametrize("skip", [False, True])
@pytest.mark.parametrize("accent", ["us", "uk"])
@pytest.mark.parametrize(
    "damage", ["duplicate", "dict", "nested", "nonstring", "blank", "whitespace"]
)
def test_all_words_reject_unsafe_tag_shapes_before_opening_db(tmp_path, skip, accent, damage):
    entries = words()
    tag = entries[0][f"phoneme_tags_{accent}"][0]
    bad = {
        "duplicate": [tag, tag],
        "dict": {tag: True},
        "nested": [[tag]],
        "nonstring": [False],
        "blank": [""],
        "whitespace": [f" {tag} "],
    }[damage]
    entries[0][f"phoneme_tags_{accent}"] = bad
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps({"words": entries}))
    database = tmp_path / "must-not-open.sqlite"
    report = importer.import_words(source, PHONEMES, str(database), skip_validation=skip)
    assert report["errors"] and not report["committed"]
    assert report["inserted"] == report["phonemes_inserted"] == 0
    assert not database.exists()
    assert validate_words(entries, load_phoneme_set(PHONEMES))["errors"]


@pytest.mark.parametrize("skip", [False, True])
@pytest.mark.parametrize("damage", ["duplicate", "conflict", "bad_id", "nonobject", "empty_us"])
def test_batch_structure_and_identity_cannot_bypass_validation(tmp_path, skip, damage):
    entries = words()
    if damage == "duplicate":
        entries.append(copy.deepcopy(entries[0]))
    elif damage == "conflict":
        entries[0]["id"] = "different"
    elif damage == "bad_id":
        entries[0]["word_id"] = ["unhashable"]
    elif damage == "nonobject":
        entries.append("not an object")
    else:
        entries[0]["phoneme_tags_us"] = []
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(entries))
    database = tmp_path / "must-not-open.sqlite"
    report = importer.import_words(source, PHONEMES, str(database), skip_validation=skip)
    assert report["errors"]
    assert not database.exists()


@pytest.mark.parametrize("uk", [None, "", [], ["/ɸ/"]])
def test_optional_uk_and_unknown_uk_warning_compatibility(tmp_path, uk):
    entries = words()
    entries[0]["phoneme_tags_uk"] = uk
    source = tmp_path / "optional.json"
    source.write_text(json.dumps(entries))
    assert not validate_words(entries, load_phoneme_set(PHONEMES))["errors"]
    report = importer.import_words(source, PHONEMES, str(tmp_path / "optional.sqlite"))
    assert report["committed"] and not report["errors"]


@pytest.mark.parametrize("stage", ["word", "phoneme"])
def test_late_sqlite_failure_rolls_back_all_writes_and_preserves_history(tmp_path, stage):
    database = tmp_path / "existing.sqlite"
    assert importer.import_words(SOURCE, PHONEMES, str(database))["committed"]
    with get_connection(str(database)) as conn:
        conn.execute("UPDATE settings SET daily_word_count=2, ui_language='en-US'")
        group = build_next_normal_group_response(conn)
        item = group["items"][0]
        create_attempt(
            conn,
            Attempt(
                id="retain",
                user_id="default",
                session_item_id=item["session_item_id"],
                word_id=item["word_id"],
                primary_accent="US",
                question_type="choose_ipa",
                correct_answer=item["display_ipa"],
                is_correct=True,
                created_at="2026-10-28T00:00:00Z",
            ),
        )
        conn.execute(
            "INSERT INTO phoneme_stats VALUES('default','US','/ʃ/',1,1,"
            "'2026-10-28',NULL,'learning')"
        )
        table, target = ("words", "sheep") if stage == "word" else ("phonemes", "/ɪ/")
        conn.execute(
            f"CREATE TRIGGER fail_stage BEFORE INSERT ON {table} WHEN NEW.id='{target}' "
            "BEGIN SELECT RAISE(ABORT,'injected stage failure'); END"
        )
        conn.commit()
    entries = words()
    for word in entries:
        word["meaning_zh"] = "must roll back"
    source = tmp_path / "replacement.json"
    source.write_text(json.dumps(entries))
    before = snapshot(database)
    report = importer.import_words(source, PHONEMES, str(database))
    assert any("injected stage failure" in error for error in report["errors"])
    assert not report["committed"] and report["rolled_back"]
    assert report["inserted"] == report["phonemes_inserted"] == 0
    assert report["tables_created"] == []
    assert report["total_words_in_db"] == 3
    assert snapshot(database) == before


def test_fresh_schema_words_and_phonemes_roll_back_on_settings_failure(tmp_path, monkeypatch):
    original = importer.init_db

    def initialize_with_fault(conn):
        original(conn)
        conn.execute(
            "CREATE TRIGGER fail_settings BEFORE INSERT ON settings "
            "BEGIN SELECT RAISE(ABORT,'injected settings failure'); END"
        )

    monkeypatch.setattr(importer, "init_db", initialize_with_fault)
    database = tmp_path / "fresh.sqlite"
    report = importer.import_words(SOURCE, PHONEMES, str(database))
    assert report["rolled_back"] and not report["committed"]
    assert report["inserted"] == report["phonemes_inserted"] == 0
    assert report["tables_created"] == []
    with sqlite3.connect(database) as conn:
        assert (
            conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 0
        )


def test_commit_constraint_failure_does_not_report_transient_writes_as_committed(tmp_path):
    database = tmp_path / "commit.sqlite"
    assert importer.import_words(SOURCE, PHONEMES, str(database))["committed"]
    with get_connection(str(database)) as conn:
        conn.execute("CREATE TABLE parent_guard(id INTEGER PRIMARY KEY)")
        conn.execute(
            "CREATE TABLE child_guard(parent_id INTEGER REFERENCES parent_guard(id) "
            "DEFERRABLE INITIALLY DEFERRED)"
        )
        conn.execute(
            "CREATE TRIGGER deferred_fault BEFORE INSERT ON words BEGIN "
            "INSERT INTO child_guard VALUES(1234); END"
        )
        conn.commit()
    before = snapshot(database)
    report = importer.import_words(SOURCE, PHONEMES, str(database))
    assert any("commit:" in error and "FOREIGN KEY" in error for error in report["errors"])
    assert report["rolled_back"] and not report["committed"]
    assert report["inserted"] == report["phonemes_inserted"] == 0
    assert snapshot(database) == before
