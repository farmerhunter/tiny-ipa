from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))

from correct_core100_tags import derive  # noqa: E402
from correct_expanded_tags import load_pack  # noqa: E402
from import_words import import_words  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.models import Attempt  # noqa: E402
from app.services.db_store import create_attempt  # noqa: E402
from app.services.sessions import build_next_normal_group_response  # noqa: E402

PHONEMES = ROOT / "content/phonemes.json"


def snapshot(database):
    with get_connection(str(database)) as conn:
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {
            name: [tuple(row) for row in conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid')]
            for name in names
        }


@pytest.mark.parametrize("size", [300, 1000])
def test_candidates_preserve_frozen_source_and_every_other_field(size):
    content, patch = load_pack(size)
    before = copy.deepcopy(content)
    candidate = derive(content, patch)
    changed = []
    for old, new in zip(content["words"], candidate["words"]):
        if old != new:
            changed.append(old["word_id"])
            assert {k: v for k, v in old.items() if k != "phoneme_tags_us"} == {
                k: v for k, v in new.items() if k != "phoneme_tags_us"
            }
    assert content == before
    assert changed == [c["word_id"] for c in patch["changes"]]
    assert len(changed) == 13
    assert all(w.startswith("mid_") for w in changed) == (size == 1000)


@pytest.mark.parametrize("damage", ["source", "hash", "identity", "ipa", "before", "after", "note"])
def test_invalid_binding_rejected_without_derivation(tmp_path, damage):
    content, patch = load_pack(1000)
    path = tmp_path / "content"
    path.mkdir()
    source = (ROOT / patch["source"]).read_bytes()
    if damage == "source":
        source += b" "
    elif damage == "hash":
        patch["source_sha256"] = "0" * 64
    elif damage == "identity":
        patch["changes"][1]["word_id"] = patch["changes"][0]["word_id"]
    elif damage in ("ipa", "before", "after"):
        field = "ipa_us" if damage == "ipa" else damage
        patch["changes"][0][field] = "/changed/" if damage == "ipa" else ["/ʌ/"]
    else:
        patch["changes"][0]["normalization_note"] = "invented"
    (path / "core_1000_words.json").write_bytes(source)
    (path / "core_1000_phoneme_corrections.json").write_text(json.dumps(patch))
    with pytest.raises(ValueError):
        load_pack(1000, tmp_path)
    assert content["words"]


@pytest.mark.parametrize("size", [300, 1000])
def test_import_copy_applies_bound_tags_and_reimport_preserves_nonempty_history(tmp_path, size):
    content, patch = load_pack(size)
    source = tmp_path / "copied-source.json"
    source.write_bytes((ROOT / patch["source"]).read_bytes())
    database = tmp_path / "learning.sqlite"
    report = import_words(source, PHONEMES, str(database))
    assert not report["errors"]
    assert len(report["tag_corrections"][0]["corrected_word_ids"]) == 13
    with get_connection(str(database)) as conn:
        conn.execute(
            "UPDATE settings SET daily_word_count=3, ui_language='en-US', "
            "learner_level=? WHERE user_id='default'",
            ("entry" if size == 300 else "mid",),
        )
        session = build_next_normal_group_response(conn)
        item = session["items"][0]
        create_attempt(
            conn,
            Attempt(
                id="history",
                user_id="default",
                session_item_id=item["session_item_id"],
                word_id=item["word_id"],
                primary_accent="US",
                question_type="choose_ipa",
                correct_answer=item["display_ipa"],
                selected_answer="/wrong/",
                is_correct=False,
                created_at="2026-10-28T00:00:00Z",
            ),
        )
        conn.execute(
            "INSERT INTO phoneme_stats VALUES('default','US','/ʃ/',1,0,"
            "'2026-10-28','2026-10-28','weak')"
        )
        conn.commit()
        for change in patch["changes"]:
            row = conn.execute(
                "SELECT phoneme_tags_us FROM words WHERE id=?", (change["word_id"],)
            ).fetchone()
            assert json.loads(row[0]) == change["after"]
    before = snapshot(database)
    assert not import_words(source, PHONEMES, str(database))["errors"]
    assert snapshot(database) == before
    source.write_text(json.dumps(derive(content, patch)))
    assert not import_words(source, PHONEMES, str(database))["errors"]
    assert snapshot(database) == before


@pytest.mark.parametrize("skip_validation", [False, True])
def test_stale_partial_import_fails_before_any_domain_write(tmp_path, skip_validation):
    content, patch = load_pack(300)
    database = tmp_path / "guard.sqlite"
    assert not import_words(ROOT / patch["source"], PHONEMES, str(database))["errors"]
    stale = copy.deepcopy(content["words"][:1])
    target = next(w for w in content["words"] if w["word_id"] == "bus")
    stale.append(target)
    stale[0]["meaning_zh"] = "must not be written"
    source = tmp_path / "stale-partial.json"
    source.write_text(json.dumps({"words": stale}))
    before = snapshot(database)
    report = import_words(source, PHONEMES, str(database), skip_validation=skip_validation)
    assert any("tag regression for bus" in error for error in report["errors"])
    assert report["inserted"] == 0
    assert snapshot(database) == before


def test_canonical_source_drift_refuses_before_opening_database(tmp_path, monkeypatch):
    import correct_expanded_tags as corrections

    content, patch = load_pack(300)
    source = tmp_path / patch["source"]
    source.parent.mkdir()
    source.write_text(json.dumps(content) + " ")
    monkeypatch.setattr(corrections, "ROOT", tmp_path)
    database = tmp_path / "must-not-open.sqlite"
    report = import_words(source, PHONEMES, str(database), skip_validation=True)
    assert any("frozen import source changed" in error for error in report["errors"])
    assert not database.exists()
