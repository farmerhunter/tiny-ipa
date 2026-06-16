"""Tests for the content validator."""

import json
import sys
from pathlib import Path

import pytest

# Add scripts dir to path so we can import validate_content
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_content import (  # noqa: E402
    KNOWN_CONTENT_STATUSES,
    KNOWN_LEVELS,
    KNOWN_REVIEW_STATUSES,
    load_phoneme_set,
    load_words,
    validate_words,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"


def test_load_words_from_list(tmp_path):
    """Words can be loaded from a JSON array."""
    data = [
        {
            "word_id": "a",
            "word": "a",
            "level": "beginner",
            "ipa_us": "/eɪ/",
            "phoneme_tags_us": ["/eɪ/"],
            "content_status": "core_selected",
        },
    ]
    path = tmp_path / "words.json"
    path.write_text(json.dumps(data))
    words = load_words(path)
    assert len(words) == 1
    assert words[0]["word_id"] == "a"


def test_load_words_from_object(tmp_path):
    """Words can be loaded from a JSON object with a 'words' key."""
    data = {"words": [
        {
            "word_id": "a",
            "word": "a",
            "level": "beginner",
            "ipa_us": "/eɪ/",
            "phoneme_tags_us": ["/eɪ/"],
            "content_status": "core_selected",
        },
    ]}
    path = tmp_path / "words.json"
    path.write_text(json.dumps(data))
    words = load_words(path)
    assert len(words) == 1


def test_load_words_invalid(tmp_path):
    """Loading an unexpected JSON shape raises an error."""
    path = tmp_path / "words.json"
    path.write_text('{"not_words": true}')
    with pytest.raises(ValueError):
        load_words(path)


def test_valid_sample_passes():
    """The valid fixture should produce zero errors."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = load_words(FIXTURES / "content_sample.json")
    report = validate_words(words, known)
    assert report["total_words"] == 3
    assert len(report["errors"]) == 0
    assert report["missing_ipa_us"] == 0
    assert report["missing_phoneme_tags_us"] == 0


def test_missing_ipa_us_is_reported():
    """Words missing ipa_us are counted as errors."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "x",
        "word": "x",
        "level": "beginner",
        "phoneme_tags_us": ["/ɪ/"],
        "meaning_zh": "字母 x",
        "content_status": "core_selected",
    }]
    report = validate_words(words, known)
    assert report["missing_ipa_us"] == 1
    assert len(report["errors"]) > 0


def test_missing_phoneme_tags_us_is_reported():
    """Words missing phoneme_tags_us are counted as errors."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "x",
        "word": "x",
        "level": "beginner",
        "ipa_us": "/ɛks/",
        "meaning_zh": "字母 x",
        "content_status": "core_selected",
    }]
    report = validate_words(words, known)
    assert report["missing_phoneme_tags_us"] == 1
    assert len(report["errors"]) > 0


def test_unknown_phoneme_tag_is_reported():
    """Phoneme tags not in the inventory are flagged."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "x", "word": "x", "level": "beginner",
        "ipa_us": "/xyz/",
        "phoneme_tags_us": ["/ɸ/", "/β/"],
        "meaning_zh": "字母 x",
        "content_status": "core_selected",
    }]
    report = validate_words(words, known)
    assert len(report["unknown_phoneme_tags_us"]) > 0
    assert len(report["errors"]) > 0


def test_phoneme_tags_us_and_uk_are_separate():
    """US and UK phoneme tags are validated independently."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "x", "word": "x", "level": "beginner",
        "ipa_us": "/ʃɪp/",
        "ipa_uk": "/ʃɪp/",
        "phoneme_tags_us": ["/ʃ/", "/ɪ/", "/p/"],
        "phoneme_tags_uk": ["/ɸ/"],
        "meaning_zh": "船",
        "content_status": "core_selected",
    }]
    report = validate_words(words, known)
    # US tags are valid, UK tag is invalid
    assert len(report["unknown_phoneme_tags_us"]) == 0
    assert len(report["unknown_phoneme_tags_uk"]) > 0
    assert len(report["errors"]) == 0
    assert len(report["warnings"]) > 0


def test_coverage_counts():
    """Coverage counts should reflect phoneme_tag usage."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = load_words(FIXTURES / "content_sample.json")
    report = validate_words(words, known)
    # ship has /ʃ/, /ɪ/, /p/; sheep has /ʃ/, /iː/, /p/; cat has /k/, /æ/, /t/
    assert report["words_per_phoneme_us"]["/ʃ/"] == 2
    assert report["words_per_phoneme_us"]["/ɪ/"] == 1
    assert report["words_per_phoneme_us"]["/p/"] == 2
    assert report["words_per_phoneme_us"]["/æ/"] == 1


def test_invalid_level_is_reported():
    """Unknown level values are flagged."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "x", "word": "x", "level": "advanced",
        "ipa_us": "/ɛks/",
        "phoneme_tags_us": ["/ɪ/"],
        "meaning_zh": "字母 x",
        "content_status": "core_selected",
    }]
    report = validate_words(words, known)
    assert len(report["invalid_level"]) == 1


def test_invalid_content_status_is_reported():
    """Unknown content_status values are flagged."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "x", "word": "x", "level": "beginner",
        "ipa_us": "/ɛks/",
        "phoneme_tags_us": ["/ɪ/"],
        "meaning_zh": "字母 x",
        "content_status": "bogus_status",
    }]
    report = validate_words(words, known)
    assert len(report["invalid_content_status"]) == 1


def test_missing_meaning_zh_is_blocking():
    """Core 300 words need Chinese meaning coverage."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "x", "word": "x", "level": "beginner",
        "ipa_us": "/ɛks/",
        "phoneme_tags_us": ["/ɪ/"],
        "content_status": "core_selected",
    }]
    report = validate_words(words, known)
    assert report["missing_meaning_zh"] == 1
    assert any("meaning_zh" in err for err in report["errors"])


def test_missing_uk_and_audio_metadata_are_warning_only():
    """Missing UK metadata and audio surface as warnings without blocking validation."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "x", "word": "x", "level": "beginner",
        "ipa_us": "/ɛks/",
        "phoneme_tags_us": ["/ɪ/"],
        "meaning_zh": "字母 x",
        "content_status": "core_selected",
    }]
    report = validate_words(words, known)
    assert report["errors"] == []
    assert report["missing_ipa_uk"] == 1
    assert report["missing_phoneme_tags_uk"] == 1
    assert report["missing_audio_us"] == 1
    assert any("ipa_uk" in warning for warning in report["warnings"])
    assert any("phoneme_tags_uk" in warning for warning in report["warnings"])
    assert any("audio_us" in warning for warning in report["warnings"])


def test_core_300_coverage_threshold_failure_is_blocking():
    """Configured Core 300 phoneme thresholds fail closed when coverage is too low."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "ship", "word": "ship", "level": "beginner",
        "ipa_us": "/ʃɪp/",
        "ipa_uk": "/ʃɪp/",
        "phoneme_tags_us": ["/ʃ/", "/ɪ/", "/p/"],
        "phoneme_tags_uk": ["/ʃ/", "/ɪ/", "/p/"],
        "meaning_zh": "船",
        "audio_us": "/audio/us/ship.mp3",
        "content_status": "core_selected",
    }]
    report = validate_words(words, known, coverage_targets_us={"/ʃ/": 2})
    assert report["coverage_failures_us"] == [
        {"phoneme": "/ʃ/", "count": 1, "minimum": 2}
    ]
    assert any("coverage" in err for err in report["errors"])


def test_priority_phoneme_coverage_is_reported():
    """Priority phoneme coverage is exposed even without failing thresholds."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = load_words(FIXTURES / "content_sample.json")
    report = validate_words(words, known, priority_phonemes={"/ʃ/", "/θ/"})
    assert report["priority_phoneme_coverage_us"] == {"/ʃ/": 2, "/θ/": 0}


def test_unknown_difficulty_tag_is_blocking():
    """Unknown difficulty labels fail closed."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "x", "word": "x", "level": "beginner",
        "ipa_us": "/ɛks/",
        "phoneme_tags_us": ["/ɪ/"],
        "meaning_zh": "字母 x",
        "difficulty_tags": ["not_a_known_tag"],
        "content_status": "core_selected",
    }]
    report = validate_words(words, known)
    assert len(report["unknown_difficulty_tags"]) == 1
    assert any("difficulty tag" in err for err in report["errors"])


def test_blocklisted_word_is_blocking():
    """Blocked words fail validation without changing the schema."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = [{
        "word_id": "ship", "word": "ship", "level": "beginner",
        "ipa_us": "/ʃɪp/",
        "phoneme_tags_us": ["/ʃ/", "/ɪ/", "/p/"],
        "meaning_zh": "船",
        "content_status": "core_selected",
    }]
    report = validate_words(words, known, blocklisted_words={"ship"})
    assert len(report["blocked_words"]) == 1
    assert any("blocked word" in err for err in report["errors"])


def test_license_summary():
    """License notes are aggregated in the report."""
    known = load_phoneme_set(PHONEMES_PATH)
    words = load_words(FIXTURES / "content_sample.json")
    report = validate_words(words, known)
    assert "open-data" in report["license_summary"]
    assert report["license_summary"]["open-data"] == 3


def test_known_constants():
    """Ensure the constant sets cover expected values."""
    assert "beginner" in KNOWN_LEVELS
    assert "core_selected" in KNOWN_CONTENT_STATUSES
    assert "reviewed" in KNOWN_REVIEW_STATUSES
