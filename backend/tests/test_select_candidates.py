"""Tests for the IPA parser and candidate selection helpers."""

import sys
from collections import Counter
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from select_candidates import (  # noqa: E402
    PHONEME_NORMALIZE,
    SUPPORTED_PHONEMES,
    apply_hard_filters,
    build_core_1000_report,
    estimate_syllable_count,
    parse_ipa_to_phonemes,
    select_core_1000_candidates,
    syllable_distribution,
)


class TestParseIpaToPhonemes:
    def test_simple_monosyllabic(self):
        tags, unknown = parse_ipa_to_phonemes("/ʃɪp/")
        assert set(tags) == {"/ʃ/", "/ɪ/", "/p/"}
        assert unknown == []

    def test_long_vowel(self):
        tags, unknown = parse_ipa_to_phonemes("/ʃiːp/")
        assert "/iː/" in tags

    def test_diphthong(self):
        tags, unknown = parse_ipa_to_phonemes("/feɪs/")
        assert "/eɪ/" in tags

    def test_affricate(self):
        tags, unknown = parse_ipa_to_phonemes("/tʃɪp/")
        assert "/tʃ/" in tags

    def test_r_colored(self):
        tags, unknown = parse_ipa_to_phonemes("/bɝd/")
        assert "/ɝ/" in tags

    def test_strips_slashes(self):
        tags, _ = parse_ipa_to_phonemes("/ʃɪp/")
        assert all(t.startswith("/") and t.endswith("/") for t in tags)

    def test_handles_stress_mark(self):
        tags, unknown = parse_ipa_to_phonemes("/ˈʃɪp/")
        assert "/ʃ/" in tags
        assert "/ˈ/" not in tags  # stress mark filtered

    def test_handles_length_mark(self):
        tags, unknown = parse_ipa_to_phonemes("/iː/")
        assert "/iː/" in tags
        assert "/ː/" not in tags  # length mark not a separate tag

    def test_normalizes_ipa_dict_symbols(self):
        """ipa-dict uses /ɹ/ for r, /i/ for tense i, /u/ for tense u."""
        tags, _ = parse_ipa_to_phonemes("/ɹɛd/")
        assert "/r/" in tags  # /ɹ/ normalized to /r/

    def test_deduplicates_phonemes(self):
        tags, _ = parse_ipa_to_phonemes("/pʌp/")
        # p appears twice but should only be listed once
        assert tags.count("/p/") == 1

    def test_empty_input(self):
        tags, unknown = parse_ipa_to_phonemes("")
        assert tags == []
        assert unknown == []

    def test_normalization_map_coverage(self):
        """Every key in PHONEME_NORMALIZE should have the normalized value in SUPPORTED_PHONEMES."""
        for source, target in PHONEME_NORMALIZE.items():
            assert target in SUPPORTED_PHONEMES, (
                f"Normalized target {target} not in SUPPORTED_PHONEMES"
            )

    def test_normalized_tags_are_supported(self):
        """After normalization, all tags should be in SUPPORTED_PHONEMES."""
        test_cases = [
            "/ʃɪp/",         # basic
            "/ˈkæt/",        # with stress
            "/θɪŋk/",        # theta
            "/ˈfaɪɝ/",       # diphthong + r-colored
            "/tʃɝtʃ/",       # affricates
        ]
        for ipa in test_cases:
            tags, _ = parse_ipa_to_phonemes(ipa)
            for tag in tags:
                assert tag in SUPPORTED_PHONEMES, (
                    f"Tag {tag} from '{ipa}' not in SUPPORTED_PHONEMES"
                )


class TestHardFilters:
    CONFIG = {
        "hard_filters": {
            "lowercase_ascii_only": True,
            "no_spaces_hyphens_apostrophes": True,
            "no_digits": True,
            "require_ipa_us": True,
            "max_pronunciation_variants": 2,
        },
        "input": {
            "min_word_length": 2,
            "max_word_length": 8,
            "min_frequency_zipf": 2.0,
        },
    }

    def test_valid_word_passes(self):
        reason, _, _ = apply_hard_filters("ship", 4.5, ["/ʃɪp/"], ["/ʃɪp/"], self.CONFIG)
        assert reason is None

    def test_non_ascii_rejected(self):
        reason, _, _ = apply_hard_filters("café", 3.0, ["/kæˈfeɪ/"], [], self.CONFIG)
        assert reason == "non_ascii_lowercase"

    def test_too_long_rejected(self):
        reason, _, _ = apply_hard_filters("elephants", 3.5, ["/ˈɛləfənts/"], [], self.CONFIG)
        assert reason == "too_long"

    def test_too_short_rejected(self):
        reason, _, _ = apply_hard_filters("a", 5.0, ["/ˈeɪ/"], [], self.CONFIG)
        assert reason == "too_short"

    def test_missing_ipa_us_rejected(self):
        reason, _, _ = apply_hard_filters("xyz", 2.5, [], [], self.CONFIG)
        assert reason == "missing_ipa_us"

    def test_low_frequency_rejected(self):
        reason, _, _ = apply_hard_filters("rareword", 1.5, ["/ˈɹɛɝwɝd/"], [], self.CONFIG)
        assert reason == "low_frequency"

    def test_function_word_rejected(self):
        reason, _, _ = apply_hard_filters("the", 7.5, ["/ðə/"], ["/ðə/"], self.CONFIG)
        assert reason == "function_word"

    def test_pronoun_rejected(self):
        reason, _, _ = apply_hard_filters("she", 5.0, ["/ʃi/"], ["/ʃiː/"], self.CONFIG)
        assert reason == "function_word"

    def test_content_word_not_rejected_as_function(self):
        reason, _, _ = apply_hard_filters("ship", 4.5, ["/ʃɪp/"], ["/ʃɪp/"], self.CONFIG)
        assert reason is None  # "ship" is not a function word


def _candidate(word, ipa_us, score=10.0, phonemes=None):
    return {
        "word_id": word,
        "word": word,
        "level": "beginner",
        "ipa_us": ipa_us,
        "ipa_uk": ipa_us,
        "phoneme_tags_us": phonemes or ["/t/"],
        "phoneme_tags_uk": phonemes or ["/t/"],
        "meaning_zh": None,
        "difficulty_tags": [],
        "minimal_pair_group": None,
        "frequency_zipf": 4.5,
        "candidate_score": score,
        "source_ipa_us": "open-dict-data/ipa-dict en_US",
        "source_ipa_uk": "open-dict-data/ipa-dict en_UK",
        "source_frequency": "wordfreq",
        "license_notes": "open-data",
        "content_status": "candidate",
        "review_status_us": "auto_checked",
        "review_status_uk": "auto_checked",
    }


class TestCore1000Rebalance:
    CONFIG = {
        "phoneme_coverage_targets_us": {
            "/t/": 1,
            "/æ/": 1,
            "/ə/": 1,
        },
        "greedy_selection": {
            "max_same_rhyme_group": 3,
        },
    }

    def test_estimate_syllable_count_uses_ipa_vowel_nuclei(self):
        assert estimate_syllable_count("/ʃɪp/") == 1
        assert estimate_syllable_count("/əˈbaʊt/") == 2
        assert estimate_syllable_count("/ˌedjəˈkeɪʃən/") == 4
        assert estimate_syllable_count("/ˈbʌtn̩/") == 2

    def test_select_core_1000_uses_syllable_targets_not_naive_score_order(self):
        candidates = [
            _candidate("ship", "/ʃɪp/", score=99, phonemes=["/ʃ/", "/ɪ/"]),
            _candidate("cat", "/kæt/", score=98, phonemes=["/k/", "/æ/"]),
            _candidate("about", "/əˈbaʊt/", score=10, phonemes=["/ə/", "/b/", "/aʊ/"]),
            _candidate("garden", "/ˈɡɑrdən/", score=9, phonemes=["/g/", "/ɑ/", "/ə/"]),
            _candidate("family", "/ˈfæməli/", score=8, phonemes=["/f/", "/æ/", "/ə/"]),
        ]

        selected = select_core_1000_candidates(
            candidates,
            self.CONFIG,
            target_size=4,
            syllable_targets={"one": 1, "two": 2, "three_plus": 1},
        )

        distribution = syllable_distribution(selected)
        assert len(selected) == 4
        assert distribution["one"]["count"] == 1
        assert distribution["two"]["count"] == 2
        assert distribution["three_plus"]["count"] == 1
        assert all(c["content_status"] == "core1000_candidate" for c in selected)
        assert all(c["level"] == "intermediate" for c in selected)
        assert [c["core1000_rank"] for c in selected] == [1, 2, 3, 4]

    def test_core_1000_report_includes_distribution_and_runtime_guard(self):
        candidates = [
            _candidate("ship", "/ʃɪp/"),
            _candidate("about", "/əˈbaʊt/"),
            _candidate("family", "/ˈfæməli/"),
        ]
        core_300 = candidates[:2]
        core_1000 = select_core_1000_candidates(
            candidates,
            self.CONFIG,
            target_size=3,
            syllable_targets={"one": 1, "two": 1, "three_plus": 1},
        )

        report = build_core_1000_report(
            candidates,
            core_300,
            core_300,
            core_1000,
            Counter({"function_word": 2}),
            self.CONFIG,
            "python3 scripts/select_candidates.py --top-n 5000",
            {"python_version": "test"},
        )

        assert report["runtime_content_promoted"] is False
        assert report["core_1000_count"] == 3
        assert report["core_1000_syllable_distribution"]["three_plus"]["count"] == 1
        assert report["core_1000_multisyllable_count"] == 2
        assert report["core_300_reference_multisyllable_count"] == 1
        assert report["rejection_reasons"] == {"function_word": 2}
        assert report["sample_candidates"]["two"][0]["word"] == "about"
