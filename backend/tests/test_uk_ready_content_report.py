"""Tests for the M9 UK-ready content report."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from report_uk_ready_content import (  # noqa: E402
    build_uk_ready_report,
    render_markdown_report,
)
from validate_content import load_phoneme_inventory  # noqa: E402

PHONEMES_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "phonemes.json"


def _inventory():
    inventory = load_phoneme_inventory(PHONEMES_PATH)
    return inventory, set(inventory)


def _row(
    word_id,
    word,
    ipa_us,
    ipa_uk,
    tags_us,
    tags_uk,
    review_status_uk="reviewed",
    content_status="core_selected",
):
    return {
        "word_id": word_id,
        "word": word,
        "level": "beginner",
        "ipa_us": ipa_us,
        "ipa_uk": ipa_uk,
        "phoneme_tags_us": tags_us,
        "phoneme_tags_uk": tags_uk,
        "meaning_zh": word,
        "source_ipa_us": "open-dict-data/ipa-dict en_US",
        "source_ipa_uk": "open-dict-data/ipa-dict en_UK",
        "license_notes": "open-data",
        "review_status_uk": review_status_uk,
        "content_status": content_status,
        "_source_file": "fixture.json",
    }


def test_uk_ready_report_filters_to_m9_eligible_rows():
    inventory, known = _inventory()
    rows = [
        _row(
            "ship",
            "ship",
            "/ʃɪp/",
            "/ʃɪp/",
            ["/ʃ/", "/ɪ/", "/p/"],
            ["/ʃ/", "/ɪ/", "/p/"],
        ),
        _row(
            "draft",
            "draft",
            "/dræft/",
            "/drɑːft/",
            ["/d/", "/r/", "/æ/", "/f/", "/t/"],
            ["/d/", "/r/", "/ɑ/", "/f/", "/t/"],
            review_status_uk="draft",
        ),
        _row(
            "missing_uk",
            "missing",
            "/mɪsɪŋ/",
            "",
            ["/m/", "/ɪ/", "/s/", "/ŋ/"],
            [],
        ),
        _row(
            "disabled",
            "disabled",
            "/dɪsˈeɪbəld/",
            "/dɪsˈeɪbəld/",
            ["/d/", "/ɪ/", "/s/", "/eɪ/", "/b/", "/l/", "/d/"],
            ["/d/", "/ɪ/", "/s/", "/eɪ/", "/b/", "/l/", "/d/"],
            content_status="disabled",
        ),
        _row(
            "unsupported",
            "unsupported",
            "/ʃɪp/",
            "/ʃɪp/",
            ["/ʃ/", "/ɪ/", "/p/"],
            ["/ɸ/"],
        ),
    ]

    report = build_uk_ready_report(
        rows,
        known,
        inventory,
        difficult_contrasts=[],
        accepted_uk_review_statuses={"reviewed"},
    )

    assert report["totals"]["eligible_rows"] == 1
    assert report["eligible_word_ids"] == ["ship"]
    assert report["totals"]["missing_uk_ipa_count"] == 1
    assert report["totals"]["missing_uk_tags_count"] == 1
    assert report["totals"]["unsupported_uk_symbol_count"] == 1
    assert report["unsupported_uk_symbols"] == {"/ɸ/": 1}
    assert len(report["excluded_rows_sample"]) == 4


def test_uk_ready_report_includes_required_sample_table_fields():
    inventory, known = _inventory()
    rows = [
        _row(
            "tomato",
            "tomato",
            "/təˈmeɪtoʊ/",
            "/təmˈɑːtəʊ/",
            ["/t/", "/ə/", "/m/", "/eɪ/", "/t/", "/oʊ/"],
            ["/t/", "/ə/", "/m/", "/ɑ/", "/t/", "/ʊ/"],
            review_status_uk="auto_checked",
        ),
    ]

    report = build_uk_ready_report(
        rows,
        known,
        inventory,
        difficult_contrasts=[],
        accepted_uk_review_statuses={"auto_checked", "reviewed"},
    )
    sample = report["sample_table"][0]
    markdown = render_markdown_report(report)

    assert sample["word"] == "tomato"
    assert sample["us_ipa"] == "/təˈmeɪtoʊ/"
    assert sample["uk_ipa"] == "/təmˈɑːtəʊ/"
    assert "reason_included" in sample
    assert "caveat" in sample
    assert "| word | US IPA | UK IPA | reason included | caveat |" in markdown
    assert "Architect pronunciation acceptance pending" in markdown


def test_uk_ready_report_finds_mechanical_minimal_pair_candidates():
    inventory, known = _inventory()
    contrasts = [{"pair": ["/iː/", "/ɪ/"], "description_zh": "sheep/ship"}]
    rows = [
        _row(
            "ship",
            "ship",
            "/ʃɪp/",
            "/ʃɪp/",
            ["/ʃ/", "/ɪ/", "/p/"],
            ["/ʃ/", "/ɪ/", "/p/"],
        ),
        _row(
            "sheep",
            "sheep",
            "/ʃiːp/",
            "/ʃiːp/",
            ["/ʃ/", "/iː/", "/p/"],
            ["/ʃ/", "/iː/", "/p/"],
        ),
    ]

    report = build_uk_ready_report(rows, known, inventory, contrasts)

    assert report["totals"]["minimal_pair_candidate_count"] == 1
    candidate = report["minimal_pair_candidates"][0]
    assert {candidate["left_word"], candidate["right_word"]} == {"ship", "sheep"}
    assert candidate["basis"] == "one phoneme-tag difference in phoneme_tags_us"


def test_uk_ready_report_counts_target_phoneme_coverage_for_us_and_uk_tags():
    inventory, known = _inventory()
    rows = [
        _row(
            "ship",
            "ship",
            "/ʃɪp/",
            "/ʃɪp/",
            ["/ʃ/", "/ɪ/", "/p/"],
            ["/ʃ/", "/ɪ/", "/p/"],
        ),
        _row(
            "tomato",
            "tomato",
            "/təˈmeɪtoʊ/",
            "/təmˈɑːtəʊ/",
            ["/t/", "/ə/", "/m/", "/eɪ/", "/t/", "/oʊ/"],
            ["/t/", "/ə/", "/m/", "/ɑ/", "/t/", "/ʊ/"],
        ),
    ]

    report = build_uk_ready_report(rows, known, inventory, difficult_contrasts=[])
    coverage = {
        row["phoneme"]: row
        for row in report["target_phoneme_candidate_coverage"]
    }

    assert coverage["/ʃ/"]["eligible_words_us"] == 1
    assert coverage["/ʃ/"]["eligible_words_uk"] == 1
    assert coverage["/oʊ/"]["eligible_words_us"] == 1
    assert coverage["/oʊ/"]["eligible_words_uk"] == 0
    assert coverage["/ʊ/"]["eligible_words_us"] == 0
    assert coverage["/ʊ/"]["eligible_words_uk"] == 1
