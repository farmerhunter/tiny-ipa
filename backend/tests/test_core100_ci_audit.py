from __future__ import annotations

import copy
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))

from audit_core100_learning import audit_content, probe_attempt_semantics  # noqa: E402
from validate_content import load_phoneme_set  # noqa: E402


def load_fixture_module():
    spec = importlib.util.spec_from_file_location(
        "core100_real_fixture", ROOT / "frontend/tests/e2e/support/prepare_core100_real_db.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs():
    return (
        json.loads((ROOT / "content/core_100_words.json").read_text())["words"],
        json.loads((ROOT / "deploy/jingyun/core100-content-audio.manifest.json").read_text()),
        load_phoneme_set(ROOT / "content/phonemes.json"),
    )


def test_frozen_media_seeds_all_assets_without_network(tmp_path, monkeypatch):
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: pytest.fail("network"))
    _, manifest, _ = inputs()
    cache = tmp_path / "cache"
    load_fixture_module().seed_audio_cache(
        ROOT / "frontend/tests/fixtures/core100-media.zip", manifest, cache
    )
    assert len(list(cache.glob("*.mp3"))) == 99


@pytest.mark.parametrize("damage", ["missing", "extra", "duplicate", "corrupt", "credits"])
def test_fixture_damage_is_rejected_before_cache_write(tmp_path, damage):
    _, manifest, _ = inputs()
    original = ROOT / "frontend/tests/fixtures/core100-media.zip"
    archive = tmp_path / "damaged.zip"
    first = manifest["audio"]["assets"][0]["path"]
    credits = manifest["audio"]["credits"]["path"]
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(archive, "w") as out:
        for name in src.namelist():
            if damage == "missing" and name == first:
                continue
            data = src.read(name)
            if (damage == "corrupt" and name == first) or (damage == "credits" and name == credits):
                data = b"unreviewed replacement"
            out.writestr(name, data)
        if damage == "extra":
            out.writestr("../escape", b"bad")
        if damage == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate name"):
                out.writestr(first, b"duplicate")
    cache = tmp_path / "cache"
    with pytest.raises(ValueError, match="fixture"):
        load_fixture_module().seed_audio_cache(archive, manifest, cache)
    assert not cache.exists()


def test_audit_separates_documented_vowel_normalization_from_lost_tags():
    words, manifest, known = inputs()
    report = audit_content(words, manifest, known)
    bus = next(d for d in report["ipa_tag_differences"] if d["word_id"] == "bus")
    assert bus["normalization_additions"] == ["/ʌ/"]
    assert bus["unexplained_missing_tags"] == ["/b/", "/s/"]
    repaired = copy.deepcopy(words)
    next(w for w in repaired if w["word_id"] == "bus")["phoneme_tags_us"] = ["/b/", "/ʌ/", "/s/"]
    result = audit_content(repaired, manifest, known)
    assert "bus" not in result["unexplained_tag_word_ids"]


def test_audit_reports_actual_audio_coverage_and_homophone_exclusion():
    report = audit_content(*inputs())
    assert report["audio_word_count"] == 99
    assert report["missing_audio_word_ids"] == ["wood"]
    assert report["audio_phoneme_coverage"]["/ð/"] == 1
    groups = report["choose_word_distractors"]["ambiguous_same_ipa_groups"]
    assert any(set(g["word_ids"]) == {"knew", "new"} for g in groups)
    samples = report["choose_word_distractors"]["samples"]
    assert all(s["word_id"] not in {d["word_id"] for d in s["distractors"]} for s in samples)


def test_disposable_probe_exposes_current_replay_and_whole_answer_attribution():
    observed = probe_attempt_semantics()
    assert observed["duplicate_attempt_risk"]
    assert observed["recorded_total_attempts"] == 5
    assert observed["unique_submitted_items"] == 1
    assert all(s["mastery_status"] == "mastered" for s in observed["phoneme_stats_after_replay"])
    wrong = observed["whole_answer_wrong_updates"]
    assert {p["phoneme"] for p in wrong} == set(observed["whole_answer_wrong_target_tags"])
