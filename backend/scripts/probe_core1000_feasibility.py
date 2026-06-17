#!/usr/bin/env python3
"""Read-only Core 1000 source feasibility probe for M8."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Optional, Union

VOWEL_NUCLEUS_RE = re.compile(r"[aæɑɒeɛɜəɚɝiɪoɔuʊʌɐ]+|[mnlrŋ][̩]")


def load_word_entries(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("words"), list):
        return data["words"]
    raise ValueError(f"{path} must contain a JSON list or a {{'words': [...]}} object")


def estimate_syllable_count(ipa: Optional[str]) -> int:
    if not ipa:
        return 0
    primary = ipa.split(",", 1)[0].strip()
    if len(primary) >= 2 and primary[0] in "/[" and primary[-1] in "/]":
        primary = primary[1:-1]
    cleaned = primary.replace("ˈ", "").replace("ˌ", "").replace("ː", "")
    return max(1, len(VOWEL_NUCLEUS_RE.findall(cleaned)))


def syllable_bucket(count: int) -> str:
    if count <= 0:
        return "unknown"
    if count == 1:
        return "one"
    if count == 2:
        return "two"
    return "three_plus"


def distribution(entries: list[dict]) -> dict[str, int]:
    counts = Counter(syllable_bucket(estimate_syllable_count(w.get("ipa_us"))) for w in entries)
    return {key: counts.get(key, 0) for key in ("one", "two", "three_plus", "unknown")}


def percent(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(part * 100 / total, 1)


def distribution_with_percent(entries: list[dict]) -> dict[str, dict[str, Union[float, int]]]:
    total = len(entries)
    counts = distribution(entries)
    return {
        key: {"count": value, "percent": percent(value, total)}
        for key, value in counts.items()
    }


def source_traceability(entries: list[dict]) -> dict[str, int]:
    return {
        "missing_ipa_us": sum(1 for w in entries if not w.get("ipa_us")),
        "missing_source_ipa_us": sum(1 for w in entries if not w.get("source_ipa_us")),
        "missing_source_frequency": sum(1 for w in entries if not w.get("source_frequency")),
        "missing_license_notes": sum(1 for w in entries if not w.get("license_notes")),
        "missing_uk_ipa": sum(1 for w in entries if not w.get("ipa_uk")),
    }


def learner_review_flags(entries: list[dict], sample_limit: int) -> dict[str, dict]:
    no_vowel_letters = [
        w.get("word", "")
        for w in entries
        if not re.search(r"[aeiouy]", w.get("word", ""))
    ]
    very_short = [w.get("word", "") for w in entries if len(w.get("word", "")) <= 2]
    missing_meaning = [w.get("word", "") for w in entries if not w.get("meaning_zh")]
    return {
        "no_vowel_letter_words": {
            "count": len(no_vowel_letters),
            "samples": no_vowel_letters[:sample_limit],
        },
        "very_short_words": {
            "count": len(very_short),
            "samples": very_short[:sample_limit],
        },
        "missing_meaning_zh": {
            "count": len(missing_meaning),
            "samples": missing_meaning[:sample_limit],
        },
    }


def frequency_summary(entries: list[dict]) -> dict[str, Optional[float]]:
    values = sorted(
        float(w["frequency_zipf"])
        for w in entries
        if isinstance(w.get("frequency_zipf"), (int, float))
    )
    if not values:
        return {"min": None, "median": None, "max": None}
    return {
        "min": round(values[0], 2),
        "median": round(median(values), 2),
        "max": round(values[-1], 2),
    }


def sample_by_bucket(entries: list[dict], bucket: str, limit: int) -> list[dict]:
    samples = []
    for word in entries:
        count = estimate_syllable_count(word.get("ipa_us"))
        if syllable_bucket(count) != bucket:
            continue
        samples.append({
            "word": word.get("word"),
            "ipa_us": word.get("ipa_us"),
            "ipa_uk": word.get("ipa_uk"),
            "syllables": count,
            "frequency_zipf": word.get("frequency_zipf"),
            "phoneme_tags_us": word.get("phoneme_tags_us", []),
        })
        if len(samples) >= limit:
            break
    return samples


def build_report(
    candidates: list[dict],
    core300: list[dict],
    sample_limit: int,
    core1000_size: int,
) -> dict:
    top_core1000 = candidates[:core1000_size]
    top_dist = distribution(top_core1000)
    core_dist = distribution(core300)
    pool_dist = distribution(candidates)
    multi_top = top_dist["two"] + top_dist["three_plus"]
    multi_core = core_dist["two"] + core_dist["three_plus"]
    multi_pool = pool_dist["two"] + pool_dist["three_plus"]
    top_trace = source_traceability(top_core1000)

    blockers = []
    if len(candidates) < core1000_size:
        blockers.append("candidate_pool_smaller_than_1000")
    if top_trace["missing_ipa_us"] or top_trace["missing_source_ipa_us"]:
        blockers.append("missing_us_ipa_or_source_traceability")
    required_multisyllable_capacity = max(core1000_size // 2, multi_core + 1)
    if multi_pool < required_multisyllable_capacity:
        blockers.append("candidate_pool_has_insufficient_multisyllable_capacity")

    selection_warnings = []
    if multi_top <= multi_core:
        selection_warnings.append(
            "naive_score_top1000_underweights_multisyllable_words; #124 must add "
            "syllable-aware ranking rather than taking candidate_score order directly"
        )

    recommendation_status = (
        "proceed_with_existing_pipeline" if not blockers else "hold_or_redirect"
    )

    return {
        "report_title": "Core 1000 Multi-Syllable Source Feasibility Probe",
        "core1000_probe_size": core1000_size,
        "source_strategy": {
            "recommended_primary": (
                "Reuse wordfreq frequency ordering plus open-dict-data/ipa-dict US/UK IPA, "
                "then add syllable-aware ranking and human curation in #124/#125."
            ),
            "cmudict_role": (
                "Optional US-only cross-check or fallback. Do not make it primary without "
                "an ARPABET-to-IPA conversion gate and UK/accent traceability plan."
            ),
            "runtime_content_changed": False,
        },
        "input_evidence": {
            "candidate_pool_count": len(candidates),
            "core300_runtime_count": len(core300),
            "top1000_count": len(top_core1000),
            "candidate_pool_syllables": distribution_with_percent(candidates),
            "top1000_syllables": distribution_with_percent(top_core1000),
            "core300_syllables": distribution_with_percent(core300),
            "top1000_frequency_zipf": frequency_summary(top_core1000),
            "core300_frequency_zipf": frequency_summary(core300),
            "top1000_traceability": top_trace,
            "top1000_learner_review_flags": learner_review_flags(
                top_core1000, sample_limit
            ),
            "candidate_pool_multisyllable_count": multi_pool,
            "required_multisyllable_capacity": required_multisyllable_capacity,
            "core300_multisyllable_count": multi_core,
            "naive_top1000_multisyllable_count": multi_top,
        },
        "quality_samples": {
            "top1000_two_syllable": sample_by_bucket(top_core1000, "two", sample_limit),
            "top1000_three_plus_syllable": sample_by_bucket(
                top_core1000, "three_plus", sample_limit
            ),
            "core300_two_syllable": sample_by_bucket(core300, "two", sample_limit),
            "core300_three_plus_syllable": sample_by_bucket(core300, "three_plus", sample_limit),
        },
        "risk_evidence": {
            "license_traceability": [
                "ipa-dict repository: MIT unless otherwise specified; English US data derives "
                "from cmudict-ipa/syllabify and English UK data derives from ipacards, so #124 "
                "should preserve per-source license notes.",
                "wordfreq code is Apache-2.0; its NOTICE documents data attribution and "
                "share-alike constraints. Candidate reports should retain source_frequency.",
                "CMUdict license is permissive for research/commercial use with requested "
                "origin acknowledgement, but it is US ARPABET rather than direct US/UK IPA.",
            ],
            "conversion_risks": [
                "Syllable counts are heuristic vowel-nucleus estimates from IPA, suitable for "
                "selection evidence but not final learner-facing syllabification.",
                "ipa-dict STRUT/r-colored vowels already required manual overrides in "
                "Core 100/300.",
                "CMUdict would add ARPABET-to-IPA conversion risk and no UK IPA coverage.",
                "Child/learner appropriateness still requires #125 human sample review and "
                "meaning_zh curation.",
            ],
            "selection_warnings": selection_warnings,
        },
        "recommendation": {
            "status": recommendation_status,
            "blocking_findings": blockers,
            "next_issue": "#124",
            "summary": (
                "Proceed to #124 with the existing wordfreq + ipa-dict pipeline and add "
                "syllable-aware Core 1000 candidate generation/rebalance reporting."
                if not blockers else
                "Do not generate Core 1000 until blocking feasibility findings are resolved."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Core 1000 source feasibility.")
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("content/generated/candidate_words.json"),
    )
    parser.add_argument(
        "--core300",
        type=Path,
        default=Path("content/core_300_words.json"),
    )
    parser.add_argument("--core1000-size", type=int, default=1000)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    args = parser.parse_args()

    candidates = load_word_entries(args.candidates)
    core300 = load_word_entries(args.core300)
    report = build_report(candidates, core300, args.sample_limit, args.core1000_size)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        evidence = report["input_evidence"]
        recommendation = report["recommendation"]
        print(report["report_title"])
        print(f"candidate_pool_count: {evidence['candidate_pool_count']}")
        print(f"top1000_count: {evidence['top1000_count']}")
        print(f"core300_runtime_count: {evidence['core300_runtime_count']}")
        print(f"top1000_syllables: {evidence['top1000_syllables']}")
        print(f"core300_syllables: {evidence['core300_syllables']}")
        print(f"top1000_traceability: {evidence['top1000_traceability']}")
        print(f"recommendation: {recommendation['status']}")
        if recommendation["blocking_findings"]:
            print(f"blocking_findings: {', '.join(recommendation['blocking_findings'])}")
        print(recommendation["summary"])

    return 0 if report["recommendation"]["status"] == "proceed_with_existing_pipeline" else 1


if __name__ == "__main__":
    raise SystemExit(main())
