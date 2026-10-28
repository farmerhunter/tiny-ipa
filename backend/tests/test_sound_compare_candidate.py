from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))

from correct_core100_tags import derive, load_corrections  # noqa: E402
from correct_expanded_tags import load_pack  # noqa: E402
from import_words import import_words  # noqa: E402
from prepare_sound_compare import candidate, load_pairs  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.services.sessions import build_minimal_pair_group_response  # noqa: E402


@pytest.mark.parametrize("size", [100, 300])
def test_candidate_changes_only_four_pair_fields_after_tag_correction(size):
    content, tags = load_corrections() if size == 100 else load_pack(size)
    before = derive(content, tags)
    after = candidate(size)
    changed = []
    for old, new in zip(before["words"], after["words"]):
        if old != new:
            changed.append(old["word_id"])
            assert {k: v for k, v in old.items() if k != "minimal_pair_group"} == {
                k: v for k, v in new.items() if k != "minimal_pair_group"
            }
    assert sorted(changed) == ["back", "bag", "came", "game"]
    assert len(load_pairs()["pairs"]) == 2


@pytest.mark.parametrize(
    "damage",
    ["source", "audio_manifest", "order", "position", "duplicate", "ipa", "audio_member", "status"],
)
def test_bad_pair_or_recording_binding_is_rejected(tmp_path, damage):
    manifest = load_pairs()
    for name in [*manifest["sources"], manifest["audio_manifest"]]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    member = manifest["pairs"][0]["members"][0]
    if damage == "source":
        (tmp_path / "content/core_100_words.json").write_text("{}")
    elif damage == "audio_manifest":
        manifest["audio_manifest_sha256"] = "0" * 64
    elif damage == "order":
        member["ordered_phones_us"].reverse()
    elif damage == "position":
        manifest["pairs"][0]["contrast_index"] = 2
    elif damage == "duplicate":
        manifest["pairs"][1]["members"][0] = member.copy()
    elif damage == "ipa":
        member["ipa_us"] = "/ˈkɪm/"
    elif damage == "audio_member":
        member["audio_sha256"] = "0" * 64
    else:
        manifest["status"] = "production"
    (tmp_path / "content/sound_compare_pairs_candidate.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_pairs(tmp_path)


def test_candidate_import_is_explicit_and_uses_existing_specialty_route(tmp_path):
    db = str(tmp_path / "comparison.sqlite")
    phonemes = ROOT / "content/phonemes.json"
    assert not import_words(ROOT / "content/core_300_words.json", phonemes, db)["errors"]
    with get_connection(db) as conn:
        assert build_minimal_pair_group_response(conn)["status"] == "empty"
    source = tmp_path / "explicit-candidate.json"
    source.write_text(json.dumps(candidate(300)))
    assert not import_words(source, phonemes, db)["errors"]
    with get_connection(db) as conn:
        response = build_minimal_pair_group_response(conn)
        assert response["group_type"] == "minimal_pair"
        assert sorted(w["word_id"] for w in response["items"]) == ["back", "bag", "came", "game"]
        assert all(w["question"]["type"] == "choose_ipa" for w in response["items"])
        assert conn.execute("SELECT count(*) FROM attempts").fetchone()[0] == 0
