from __future__ import annotations

import copy
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))

from audit_core100_learning import audit_content  # noqa: E402
from correct_core100_tags import apply, derive, load_corrections, plan  # noqa: E402
from validate_content import load_phoneme_set  # noqa: E402


def test_derived_corrections_restore_tags_without_changing_frozen_source_or_other_fields():
    source, patch = load_corrections()
    before = copy.deepcopy(source)
    corrected = derive(source, patch)
    assert source == before
    changed = []
    for old, new in zip(source["words"], corrected["words"]):
        if old != new:
            changed.append(old["word_id"])
            assert {k: v for k, v in old.items() if k != "phoneme_tags_us"} == {
                k: v for k, v in new.items() if k != "phoneme_tags_us"
            }
    assert len(changed) == 13
    manifest = json.loads((ROOT / "deploy/jingyun/core100-content-audio.manifest.json").read_text())
    report = audit_content(
        corrected["words"], manifest, load_phoneme_set(ROOT / "content/phonemes.json")
    )
    assert report["unexplained_tag_word_ids"] == []
    assert report["schema_errors"] == []


def test_tag_transaction_preserves_history_and_rejects_drift(tmp_path):
    source, patch = load_corrections()
    conn = sqlite3.connect(tmp_path / "tags.sqlite")
    conn.executescript(
        "CREATE TABLE words(id TEXT PRIMARY KEY,ipa_us TEXT,phoneme_tags_us TEXT,audio_us TEXT);"
        "CREATE TABLE attempts(id TEXT,selected_answer TEXT);"
        "INSERT INTO attempts VALUES('keep','unchanged');"
    )
    conn.executemany(
        "INSERT INTO words VALUES(?,?,?,?)",
        [
            (w["word_id"], w["ipa_us"], json.dumps(w["phoneme_tags_us"]), w["audio_us"])
            for w in source["words"]
        ],
    )
    conn.commit()
    planned = plan(conn, patch)
    assert planned["change_count"] == 13
    unchanged = list(conn.execute("SELECT id,ipa_us,audio_us FROM words ORDER BY id"))
    conn.execute("UPDATE words SET phoneme_tags_us='[\"/custom/\"]' WHERE id='water'")
    conn.commit()
    with pytest.raises(ValueError, match="tags differ"):
        apply(conn, patch, planned["plan_sha256"])
    assert json.loads(
        conn.execute("SELECT phoneme_tags_us FROM words WHERE id='bus'").fetchone()[0]
    ) == ["/ə/", "/ʌ/"]
    water = next(w for w in source["words"] if w["word_id"] == "water")
    conn.execute(
        "UPDATE words SET phoneme_tags_us=? WHERE id='water'",
        (json.dumps(water["phoneme_tags_us"]),),
    )
    conn.commit()
    assert apply(conn, patch, planned["plan_sha256"])["updated"] == 13
    assert plan(conn, patch)["change_count"] == 0
    assert list(conn.execute("SELECT id,ipa_us,audio_us FROM words ORDER BY id")) == unchanged
    assert conn.execute("SELECT * FROM attempts").fetchall() == [("keep", "unchanged")]
    conn.close()
