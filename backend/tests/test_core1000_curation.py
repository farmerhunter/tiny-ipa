"""Tests for Mid/Core1000 runtime curation helpers."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import curate_core_1000 as curation  # noqa: E402


def test_curate_core_1000_filters_low_quality_and_replenishes_targets(monkeypatch):
    monkeypatch.setattr(
        curation,
        "CORE_1000_TARGETS",
        {"one": 1, "two": 1, "three_plus": 1},
    )
    candidates = [
        _candidate("vs", "/ˈviˈɛs/", 1, "one"),
        _candidate("table", "/ˈteɪbəl/", 2, "two"),
        _candidate("family", "/ˈfæməli/", 3, "three_plus"),
    ]
    pool = candidates + [_candidate("cat", "/kæt/", 1, "one")]

    selected, report = curation.curate_core_1000(
        candidates,
        pool,
        meaning_map={"cat": "猫"},
    )

    assert [item["word"] for item in selected] == ["cat", "table", "family"]
    assert all(item["word_id"].startswith("mid_") for item in selected)
    assert selected[0]["source_word_id"] == "cat"
    assert selected[0]["meaning_zh"] == "猫"
    assert selected[0]["meaning_zh_review_status"] == "inherited_core300"
    assert report["rejection_reasons"]["manual_quality_exclude"] == 1
    assert report["syllable_distribution_us"]["one"]["count"] == 1
    assert report["runtime_content_promoted"] is True


def _candidate(word: str, ipa_us: str, syllable_count: int, bucket: str) -> dict:
    return {
        "word_id": word,
        "word": word,
        "level": "intermediate",
        "ipa_us": ipa_us,
        "ipa_uk": ipa_us,
        "phoneme_tags_us": ["/t/"],
        "phoneme_tags_uk": ["/t/"],
        "meaning_zh": None,
        "content_status": "core1000_candidate",
        "review_status_us": "auto_checked",
        "review_status_uk": "auto_checked",
        "candidate_score": 1,
        "syllable_count_us": syllable_count,
        "syllable_bucket_us": bucket,
    }
