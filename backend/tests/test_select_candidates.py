"""Tests for the IPA parser and candidate selection helpers."""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from select_candidates import (  # noqa: E402
    PHONEME_NORMALIZE,
    SUPPORTED_PHONEMES,
    apply_hard_filters,
    parse_ipa_to_phonemes,
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
