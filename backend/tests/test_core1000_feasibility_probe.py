import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from probe_core1000_feasibility import build_report, estimate_syllable_count  # noqa: E402


def word(word_id, ipa_us, ipa_uk="/x/", frequency=4.0):
    return {
        "word": word_id,
        "word_id": word_id,
        "ipa_us": ipa_us,
        "ipa_uk": ipa_uk,
        "frequency_zipf": frequency,
        "source_ipa_us": "open-dict-data/ipa-dict en_US",
        "source_frequency": "wordfreq",
        "license_notes": "open-data",
        "phoneme_tags_us": [],
    }


def test_estimate_syllable_count_from_ipa_vowel_nuclei():
    assert estimate_syllable_count("/ʃɪp/") == 1
    assert estimate_syllable_count("/əˈbaʊt/") == 2
    assert estimate_syllable_count("/ˌedjəˈkeɪʃən/") == 4
    assert estimate_syllable_count("/ˈbʌtn̩/") == 2


def test_core1000_probe_recommends_existing_pipeline_when_pool_is_sufficient():
    candidates = [
        word("about", "/əˈbaʊt/"),
        word("garden", "/ˈɡɑrdən/"),
        word("family", "/ˈfæməli/"),
        word("ship", "/ʃɪp/"),
    ]
    core300 = [word("ship", "/ʃɪp/"), word("about", "/əˈbaʊt/")]

    report = build_report(candidates, core300, sample_limit=2, core1000_size=4)

    assert report["recommendation"]["status"] == "proceed_with_existing_pipeline"
    assert report["input_evidence"]["top1000_syllables"]["two"]["count"] == 2
    assert report["input_evidence"]["top1000_syllables"]["three_plus"]["count"] == 1
    assert report["input_evidence"]["top1000_traceability"]["missing_source_ipa_us"] == 0
    assert report["source_strategy"]["runtime_content_changed"] is False


def test_core1000_probe_fails_closed_for_missing_traceability():
    candidates = [
        word("about", "/əˈbaʊt/"),
        {**word("garden", "/ˈɡɑrdən/"), "source_ipa_us": ""},
    ]
    core300 = [word("ship", "/ʃɪp/")]

    report = build_report(candidates, core300, sample_limit=2, core1000_size=2)

    assert report["recommendation"]["status"] == "hold_or_redirect"
    assert "missing_us_ipa_or_source_traceability" in report["recommendation"]["blocking_findings"]
