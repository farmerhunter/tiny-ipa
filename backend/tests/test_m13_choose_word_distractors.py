"""Tests for M13 choose_word distractor scoring and reporting."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from report_choose_word_distractors import load_word_models  # noqa: E402

from app.models import Word  # noqa: E402
from app.services.distractors import (  # noqa: E402
    build_choose_word_quality_report,
    choose_word_distractors,
    score_choose_word_candidate,
)


def word(
    word_id: str,
    ipa: str,
    *,
    text: str | None = None,
    level: str = "beginner",
    phonemes: list[str] | None = None,
    tags: list[str] | None = None,
    status: str = "core_selected",
) -> Word:
    return Word(
        id=word_id,
        word=text or word_id,
        level=level,
        ipa_us=ipa,
        phoneme_tags_us=phonemes or [],
        content_status=status,
        difficulty_tags=tags,
    )


def test_choose_word_scorer_is_deterministic_and_prefers_shared_phonemes():
    target = word(
        "ship",
        "/ʃɪp/",
        phonemes=["/ʃ/", "/ɪ/", "/p/"],
        tags=["sh", "short_i"],
    )
    candidates = [
        word(
            "cat",
            "/kæt/",
            phonemes=["/k/", "/æ/", "/t/"],
            tags=["short_a"],
        ),
        word(
            "sheep",
            "/ʃiːp/",
            phonemes=["/ʃ/", "/iː/", "/p/"],
            tags=["sh", "long_i"],
        ),
        word(
            "shop",
            "/ʃɑp/",
            phonemes=["/ʃ/", "/ɑ/", "/p/"],
            tags=["sh"],
        ),
    ]

    first = choose_word_distractors(target, candidates, seed=42)
    second = choose_word_distractors(target, candidates, seed=42)

    assert [item.word.id for item in first] == [item.word.id for item in second]
    assert first[0].word.id in {"sheep", "shop"}
    assert first[0].shared_phonemes == 2


def test_choose_word_scorer_excludes_same_ipa_and_other_levels():
    target = word("new", "/nu/", phonemes=["/n/", "/u/"])
    same_ipa = word("knew", "/nu/", phonemes=["/n/", "/u/"])
    other_level = word(
        "noon",
        "/nun/",
        level="intermediate",
        phonemes=["/n/", "/u/"],
    )

    assert score_choose_word_candidate(target, same_ipa) is None
    assert score_choose_word_candidate(target, other_level) is None
    assert choose_word_distractors(target, [same_ipa, other_level]) == []


def test_choose_word_report_surfaces_sparse_and_fallback_buckets():
    words = [
        word("ship", "/ʃɪp/", phonemes=["/ʃ/", "/ɪ/", "/p/"]),
        word("knew", "/nu/", phonemes=["/n/", "/u/"]),
        word("new", "/nu/", phonemes=["/n/", "/u/"]),
        word("cat", "/kæt/", phonemes=["/k/", "/æ/", "/t/"]),
        word("want", "/wɑnt/", level="intermediate", phonemes=["/w/", "/ɑ/", "/n/", "/t/"]),
    ]

    report = build_choose_word_quality_report(words, choice_count=4, sample_limit=5)

    assert report["report_name"] == "M13 choose_word distractor quality report"
    assert report["totals"]["targets"] == 5
    assert report["totals"]["sparse_targets"] > 0
    assert report["totals"]["fallback_distractors"] > 0
    assert report["totals"]["sparse_target_rate"] > 0
    assert report["totals"]["fallback_distractor_rate"] > 0
    assert report["totals"]["same_ipa_excluded_pairs"] == 2
    assert report["by_level"]["intermediate"]["sparse_targets"] == 1
    assert report["by_level"]["beginner"]["full_choice_rate"] < 1
    assert report["ambiguous_same_ipa_groups"] == [
        {
            "level": "beginner",
            "ipa": "/nu/",
            "words": ["knew", "new"],
            "word_ids": ["knew", "new"],
        }
    ]
    assert "learner_level_partition" in report["scoring_signals"]


def test_report_script_loads_content_json_as_word_models(tmp_path):
    source = tmp_path / "words.json"
    source.write_text(
        """[
          {
            "word_id": "ship",
            "word": "ship",
            "level": "beginner",
            "ipa_us": "/ʃɪp/",
            "phoneme_tags_us": ["/ʃ/", "/ɪ/", "/p/"],
            "content_status": "core_selected"
          }
        ]""",
        encoding="utf-8",
    )

    words = load_word_models([source])

    assert len(words) == 1
    assert words[0].id == "ship"
    assert words[0].phoneme_tags_us == ["/ʃ/", "/ɪ/", "/p/"]
