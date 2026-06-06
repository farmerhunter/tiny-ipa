#!/usr/bin/env python3
"""
Tiny IPA content auto-selection feasibility spike.

Generates candidate word lists with US/UK IPA, phoneme tags, and a coverage report
from open word-frequency data and the open-dict-data/ipa-dict dataset.

Usage:
    python select_candidates.py [--top-n 5000] [--ipa-dict-dir /path/to/ipa-dict/data]

Before running:
    pip install -e ".[content]"

If ipa-dict data is not available locally, download en_US.txt and en_UK.txt from
https://github.com/open-dict-data/ipa-dict/tree/master/data and place them in a
directory, then pass --ipa-dict-dir.

Outputs go to content/generated/ (gitignored).
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# IPA PARSER
# ---------------------------------------------------------------------------

# Known IPA phoneme symbols in Tiny IPA, ordered longest-first for greedy tokenization.
# This is a US-first inventory covering General American.
KNOWN_PHONEMES_BY_LENGTH = sorted(
    [
        # Affricates (must come before their components)
        "/tʃ/",
        "/dʒ/",
        # Diphthongs (must come before monophthongs)
        "/eɪ/",
        "/aɪ/",
        "/oʊ/",
        "/aʊ/",
        "/ɔɪ/",
        # Long vowels with length mark
        "/iː/",
        "/uː/",
        # R-colored vowels
        "/ɝ/",
        "/ɚ/",
        # Short / lax vowels
        "/ɪ/",
        "/ʊ/",
        "/æ/",
        "/ʌ/",
        "/ə/",
        "/ɛ/",
        "/ɔ/",
        "/ɑ/",
        "/ɒ/",
        # Consonants — fricatives
        "/θ/",
        "/ð/",
        "/ʃ/",
        "/ʒ/",
        # Consonants — stops, nasals, liquids, glides
        "/p/",
        "/b/",
        "/t/",
        "/d/",
        "/k/",
        "/g/",
        "/f/",
        "/v/",
        "/s/",
        "/z/",
        "/h/",
        "/m/",
        "/n/",
        "/ŋ/",
        "/l/",
        "/r/",
        "/w/",
        "/j/",
        # Syllabic consonants
        "/n̩/",
        "/l̩/",
        "/m̩/",
        # Dark l
        "/ɫ/",
        # Glottal stop
        "/ʔ/",
        # Length mark (not a phoneme but appears in IPA strings)
        "/ː/",
        # Stress marks
        "/ˈ/",
        "/ˌ/",
        # ipa-dict specific symbols
        "/ɹ/",   # alveolar approximant (American r)
        "/i/",   # plain i (short/tense)
        "/u/",   # plain u (short/tense)
        "/ɡ/",   # script g
        "/ɛ/",   # open-mid front unrounded
        "/ɒ/",   # open back rounded
    ],
    key=lambda s: -len(s),
)

# A secondary decoder for raw IPA strings using the same inventory but
# without the / delimiters, used as a fallback.
RAW_PHONEMES_BY_LENGTH = sorted(
    [p.strip("/") for p in KNOWN_PHONEMES_BY_LENGTH],
    key=lambda s: -len(s),
)

# Phonemes that should be treated as "supported" by our inventory.
SUPPORTED_PHONEMES = {p for p in [
    "/iː/", "/ɪ/", "/e/", "/æ/", "/ʌ/", "/ɑ/", "/ɔ/", "/ʊ/", "/uː/", "/ə/",
    "/eɪ/", "/aɪ/", "/oʊ/", "/aʊ/", "/ɔɪ/", "/ɝ/", "/ɚ/",
    "/p/", "/b/", "/t/", "/d/", "/k/", "/g/",
    "/f/", "/v/", "/θ/", "/ð/", "/s/", "/z/", "/ʃ/", "/ʒ/", "/h/",
    "/tʃ/", "/dʒ/",
    "/m/", "/n/", "/ŋ/", "/l/", "/r/", "/w/", "/j/",
    # ipa-dict specific symbols that map to our canonical set
    "/ɹ/",  # alveolar approximant (American r)
    "/i/",  # short/tense i (map to /ɪ/ for phoneme stats)
    "/u/",  # short/tense u (map to /ʊ/ for phoneme stats)
    "/ɡ/",  # script g (map to /g/ for phoneme stats)
    "/ɛ/",  # open-mid front unrounded (map to /e/ for phoneme stats)
    "/ɒ/",  # open back rounded (map to /ɑ/ for phoneme stats)
    "/ɫ/",  # dark l (map to /l/ for phoneme stats)
    "/e/",  # plain e (map to /e/)
]}

# Normalization map: ipa-dict symbols → canonical phoneme tags
PHONEME_NORMALIZE = {
    "/ɹ/": "/r/",    # alveolar approximant → canonical r
    "/i/": "/iː/",    # tense i (FLEECE) → long iː
    "/u/": "/uː/",    # tense u (GOOSE) → long uː
    "/ɡ/": "/g/",    # script g → canonical g
    "/ɛ/": "/e/",    # open-mid e → canonical e
    "/ɒ/": "/ɑ/",    # open back rounded → canonical ɑ
    "/ɫ/": "/l/",    # dark l → canonical l
}


def parse_ipa_to_phonemes(ipa_str: str):
    """
    Parse a raw IPA string (e.g. \"/ʃɪp/\") into a list of phoneme tags
    (e.g. [\"/ʃ/\", \"/ɪ/\", \"/p/\"]).

    Handles:
    - Slash-delimited IPA: /ʃɪp/
    - Multiple variants: /ʃɪp/, /ʃɪp̚/
    - Bracketed: [ʃɪp]
    - Raw IPA: ʃɪp

    Returns (phoneme_tags, unknown_symbols).
    """
    if not ipa_str:
        return [], []

    # Take the first variant only (before comma)
    raw = ipa_str.split(",")[0].strip()

    # Strip /.../ or [...] delimiters
    if raw.startswith("/") and raw.endswith("/"):
        raw = raw[1:-1]
    elif raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]

    phonemes = []
    unknown = []
    i = 0
    while i < len(raw):
        matched = False
        for sym in RAW_PHONEMES_BY_LENGTH:
            if raw[i:].startswith(sym):
                # Wrap back in / / for consistency
                tag = f"/{sym}/"
                if tag not in phonemes or tag not in ["/ː/", "/ˈ/", "/ˌ/"]:
                    if tag in SUPPORTED_PHONEMES:
                        phonemes.append(tag)
                    # Skip stress marks and length marks from tag output
                matched = True
                i += len(sym)
                break
        if not matched:
            # Unknown single character
            ch = raw[i]
            unknown.append(ch)
            i += 1

    # Deduplicate while preserving order (first occurrence)
    seen = set()
    result = []
    for p in phonemes:
        # Normalize ipa-dict symbols to canonical phoneme tags
        canonical = PHONEME_NORMALIZE.get(p, p)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result, unknown


# ---------------------------------------------------------------------------
# WORD FREQUENCY
# ---------------------------------------------------------------------------

def get_top_words_from_wordfreq(top_n: int = 5000) -> list:
    """
    Get top N English words from wordfreq, returning list of (word, zipf_frequency).
    Uses wordfreq's built-in wordlist which is pre-filtered and sorted.
    """
    try:
        from wordfreq import iter_wordlist, zipf_frequency
    except ImportError:
        print(
            "Error: wordfreq not installed. Run: pip install -e '.[content]'",
            file=sys.stderr,
        )
        sys.exit(1)

    words = []
    for i, w in enumerate(iter_wordlist("en", wordlist="best")):
        if i >= top_n * 3:  # Over-sample since we'll filter heavily
            break
        freq = zipf_frequency(w, "en")
        words.append((w, freq))

    # Sort by frequency descending, take top_n
    words.sort(key=lambda x: -x[1])
    return words[:top_n]


# ---------------------------------------------------------------------------
# IPA DICT LOADER
# ---------------------------------------------------------------------------

def load_ipa_dict(ipa_dir: str) -> dict:
    """
    Load IPA dictionary from a directory containing en_US.txt and en_UK.txt
    (tab-separated files from open-dict-data/ipa-dict).

    Returns: {
        "US": {word: [ipa1, ipa2, ...]},
        "UK": {word: [ipa1, ipa2, ...]},
    }
    """
    ipa_data = {"US": {}, "UK": {}}
    accent_files = {"US": "en_US.txt", "UK": "en_UK.txt"}

    for accent, filename in accent_files.items():
        filepath = os.path.join(ipa_dir, filename)
        if not os.path.exists(filepath):
            print(f"Warning: {filepath} not found, skipping {accent} IPA data")
            continue
        with open(filepath, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                word = parts[0].strip().lower()
                ipa_raw = parts[1].strip()
                # Split multiple pronunciations
                ipa_variants = [v.strip() for v in ipa_raw.split(",") if v.strip()]
                if word not in ipa_data[accent]:
                    ipa_data[accent][word] = []
                ipa_data[accent][word].extend(ipa_variants)
    return ipa_data


def _is_likely_proper_noun(word: str, freq_zipf: float) -> bool:
    """Heuristic: frequent words that are proper nouns are rare in wordfreq
    top lists, but we explicitly reject obvious ones."""
    # Words that start with capital in source but are lowercased
    # This is hard to detect post-lowercase; rely on wordfreq's filtering
    return False  # wordfreq already filters most proper nouns


# ---------------------------------------------------------------------------
# Built-in function word blocklist
# ---------------------------------------------------------------------------

# Common English function words that are poor candidates for phonetic training.
# These words often have reduced/weak forms, behave irregularly, or don't
# provide clear phoneme-contrast value for beginners.
FUNCTION_WORDS = {
    # Determiners
    "the", "a", "an", "this", "that", "these", "those", "some", "any", "no",
    "every", "each", "all", "both", "few", "many", "much", "such", "several",
    # Prepositions
    "in", "on", "at", "of", "to", "for", "with", "by", "from", "up", "out",
    "off", "over", "under", "into", "onto", "upon", "than", "as", "like",
    "through", "after", "before", "between", "during", "since", "until",
    "without", "within", "along", "across", "behind", "beyond", "among",
    "toward", "towards",
    # Conjunctions
    "and", "but", "or", "if", "so", "yet", "nor", "for", "while", "because",
    "although", "though", "unless", "since", "until", "when", "where",
    "whether",
    # Auxiliary / modal verbs
    "be", "am", "is", "are", "was", "were", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "doing",
    "can", "could", "will", "would", "shall", "should", "may", "might", "must",
    "get", "got", "go", "goes", "going", "went", "gone",
    # Pronouns
    "i", "me", "my", "mine", "myself",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself",
    "she", "her", "hers", "herself",
    "it", "its", "itself",
    "we", "us", "our", "ours", "ourselves",
    "they", "them", "their", "theirs", "themselves",
    "who", "whom", "whose", "what", "which", "whatever",
    "anyone", "someone", "everyone", "nobody", "nothing",
    # Other function particles
    "not", "n't", "to", "too", "very", "just", "only", "also", "now",
    "then", "here", "there", "well", "even", "still", "again", "already",
    "quite", "rather", "really", "almost", "enough", "perhaps", "maybe",
    "please", "yes", "yeah", "no", "nope", "oh", "ah", "um", "er",
}


# ---------------------------------------------------------------------------
# HARD FILTERS
# ---------------------------------------------------------------------------

def apply_hard_filters(word: str, freq_zipf: float, ipa_us: list, ipa_uk: list,
                       config: dict) -> tuple:
    """
    Apply hard rejection filters. Returns (reject_reason: str | None, ipa_us_variants, ipa_uk_variants).
    """
    filters = config.get("hard_filters", {})

    # Lowercase ASCII only
    if filters.get("lowercase_ascii_only", True):
        if not re.match(r"^[a-z]+$", word):
            return "non_ascii_lowercase", [], []

    # Too short / too long
    min_len = config.get("input", {}).get("min_word_length", 2)
    max_len = config.get("input", {}).get("max_word_length", 8)
    if len(word) < min_len:
        return "too_short", [], []
    if len(word) > max_len:
        return "too_long", [], []

    # Contains spaces, hyphens, apostrophes, digits
    if filters.get("no_spaces_hyphens_apostrophes", True):
        if any(c in word for c in " -'"):
            return "has_punctuation", [], []

    if filters.get("no_digits", True):
        if any(c.isdigit() for c in word):
            return "has_digits", [], []

    # Reject function words (weak forms, poor phonetic value)
    if filters.get("reject_function_words", True):
        if word in FUNCTION_WORDS:
            return "function_word", [], []

    # Missing US IPA (required)
    if filters.get("require_ipa_us", True):
        if not ipa_us:
            return "missing_ipa_us", [], []

    # Too many pronunciation variants
    max_variants = filters.get("max_pronunciation_variants", 2)
    if len(ipa_us) > max_variants:
        return "too_many_us_variants", ipa_us[:max_variants], ipa_uk[:max_variants]

    # Low frequency
    min_freq = config.get("input", {}).get("min_frequency_zipf", 2.0)
    if freq_zipf < min_freq:
        return "low_frequency", ipa_us, ipa_uk

    # Unknown IPA symbols in US
    unsupported_ipa_symbols = config.get("unsupported_ipa_symbols", set())
    for ipa in ipa_us[:max_variants]:
        phonemes, unknown = parse_ipa_to_phonemes(ipa)
        if unknown:
            return "unsupported_ipa_symbols", ipa_us[:max_variants], ipa_uk[:max_variants]

    return None, ipa_us, ipa_uk


# ---------------------------------------------------------------------------
# SCORING
# ---------------------------------------------------------------------------

def score_candidate(word: str, freq_zipf: float, phoneme_tags_us: list,
                    ipa_us: str, ipa_uk: str, config: dict,
                    phoneme_counts: dict) -> float:
    """
    Score a candidate word for selection priority.
    Higher score = better candidate for Tiny IPA.
    """
    scoring = config.get("scoring", {})

    # Frequency score (normalize: typical zipf range is 1-7 for common words)
    freq_score = min(freq_zipf / 7.0, 1.0) * scoring.get("frequency_score_weight", 0.15) * 100

    # Phoneme coverage: how many target phonemes does this word contribute?
    # Words with rarer phonemes score higher
    targets = config.get("phoneme_coverage_targets_us", {})
    cov_score = 0.0
    for tag in phoneme_tags_us:
        target_count = targets.get(tag, 5)
        current = phoneme_counts.get(tag, 0)
        # Higher value if target not yet met
        if current < target_count:
            cov_score += (target_count - current) / max(target_count, 1)
    cov_score = cov_score * scoring.get("phoneme_coverage_score_weight", 0.40) * 100

    # Spelling simplicity (shorter = better for beginners)
    spell_score = max(0, 1 - (len(word) - 3) / 10) * scoring.get("spelling_simplicity_score_weight", 0.10) * 100

    # Accent stability (same IPA in US and UK = bonus)
    accent_stab = 0
    if ipa_uk:
        accent_stab = 1.0 if ipa_us == ipa_uk else 0.5
    accent_score = accent_stab * scoring.get("accent_stability_score_weight", 0.05) * 100

    # IPA complexity penalty (fewer phonemes = simpler)
    ipa_penalty = len(phoneme_tags_us) * scoring.get("ipa_complexity_penalty_per_phoneme", 2.0)

    score = freq_score + cov_score + spell_score + accent_score - ipa_penalty
    return max(0, score)


# ---------------------------------------------------------------------------
# GREEDY SELECTION
# ---------------------------------------------------------------------------

def greedy_select(candidates: list, target_size: int, config: dict) -> list:
    """
    Select up to target_size words using greedy phoneme coverage.
    Returns selected candidates in priority order.
    """
    targets = config.get("phoneme_coverage_targets_us", {})
    greedy_cfg = config.get("greedy_selection", {})
    max_rhyme = greedy_cfg.get("max_same_rhyme_group", 3)
    max_diff = greedy_cfg.get("max_same_difficulty_tag", 5)

    selected = []
    phoneme_counts = defaultdict(int)
    rhyme_counts = defaultdict(int)
    diff_counts = defaultdict(int)

    remaining = list(candidates)
    # Pre-sort by candidate_score descending
    remaining.sort(key=lambda c: c.get("candidate_score", 0), reverse=True)

    while len(selected) < target_size and remaining:
        # Find best candidate that fills coverage gaps
        best_idx = 0
        best_gain = -1
        for i, c in enumerate(remaining[:500]):  # Check top 500 per iteration
            gain = 0
            for tag in c.get("phoneme_tags_us", []):
                target = targets.get(tag, 5)
                current = phoneme_counts.get(tag, 0)
                if current < target:
                    gain += (target - current) / max(target, 1)
            # Apply soft constraints
            rhyme = c.get("minimal_pair_group", "")
            if rhyme_counts.get(rhyme, 0) >= max_rhyme and rhyme:
                gain *= 0.3
            if gain > best_gain:
                best_gain = gain
                best_idx = i

        chosen = remaining.pop(best_idx)

        # Update counts
        for tag in chosen.get("phoneme_tags_us", []):
            phoneme_counts[tag] += 1
        rhyme_counts[chosen.get("minimal_pair_group", "")] += 1
        for dt in chosen.get("difficulty_tags", []):
            diff_counts[dt] += 1

        selected.append(chosen)

    return selected


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Tiny IPA content auto-selection feasibility spike"
    )
    parser.add_argument("--top-n", type=int, default=5000,
                        help="Number of top frequency words to consider (default: 5000)")
    parser.add_argument("--ipa-dict-dir", type=str, default=None,
                        help="Directory containing en_US.txt and en_UK.txt from ipa-dict")
    parser.add_argument("--selection-config", type=str, default=None,
                        help="Path to selection_config.json")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory for generated files")
    args = parser.parse_args()

    # Paths
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = repo_root / "content" / "generated"

    if args.selection_config:
        config_path = Path(args.selection_config)
    else:
        config_path = repo_root / "content" / "selection_config.json"

    if args.ipa_dict_dir:
        ipa_dir = args.ipa_dict_dir
    else:
        # Default: look for ipa-dict data in a sibling directory or content/sources/
        ipa_dir = repo_root / "content" / "sources" / "ipa-dict"

    os.makedirs(output_dir, exist_ok=True)

    # Load config
    with open(config_path, "r") as fh:
        config = json.load(fh)

    print("=" * 60)
    print("Tiny IPA Content Auto-Selection")
    print("=" * 60)
    print()

    # Step 1: Load frequency data
    print("[1/6] Loading word frequency data...")
    freq_words = get_top_words_from_wordfreq(args.top_n)
    print(f"  Loaded {len(freq_words)} words from wordfreq")
    print(f"  Top 5: {[w for w, _ in freq_words[:5]]}")
    print(f"  Frequency range: {freq_words[-1][1]:.1f} – {freq_words[0][1]:.1f} zipf")

    # Step 2: Load IPA data
    print("\n[2/6] Loading IPA dictionary data...")
    if not os.path.isdir(ipa_dir):
        print(f"  ERROR: IPA dict directory not found: {ipa_dir}")
        print(f"  Download en_US.txt and en_UK.txt from:")
        print(f"    https://github.com/open-dict-data/ipa-dict/tree/master/data")
        print(f"  Place them in: {ipa_dir}")
        sys.exit(1)

    ipa_data = load_ipa_dict(str(ipa_dir))
    us_count = len(ipa_data["US"])
    uk_count = len(ipa_data["UK"])
    print(f"  Loaded US IPA entries: {us_count}")
    print(f"  Loaded UK IPA entries: {uk_count}")

    # Step 3: Join and filter
    print("\n[3/6] Joining frequency + IPA data and applying hard filters...")
    candidates = []
    rejection_reasons = Counter()
    joined_us = 0
    joined_uk = 0
    dual_accent = 0
    unknown_ipa_symbols = set()
    source_ipa_us_counts = Counter()
    source_ipa_uk_counts = Counter()

    for word, freq in freq_words:
        ipa_us = ipa_data["US"].get(word, [])
        ipa_uk = ipa_data["UK"].get(word, [])

        if ipa_us:
            joined_us += 1
            source_ipa_us_counts["open-dict-data/ipa-dict en_US"] += 1
        if ipa_uk:
            joined_uk += 1
            source_ipa_uk_counts["open-dict-data/ipa-dict en_UK"] += 1
        if ipa_us and ipa_uk:
            dual_accent += 1

        reason, ipa_us_filtered, ipa_uk_filtered = apply_hard_filters(
            word, freq, ipa_us, ipa_uk, config
        )

        if reason:
            rejection_reasons[reason] += 1
            continue

        # Use first US variant as primary
        primary_ipa_us = ipa_us_filtered[0] if ipa_us_filtered else ""
        primary_ipa_uk = ipa_uk_filtered[0] if ipa_uk_filtered else ""

        # Parse phoneme tags
        phoneme_tags_us, unknown_us = parse_ipa_to_phonemes(primary_ipa_us)
        phoneme_tags_uk = []
        if primary_ipa_uk:
            phoneme_tags_uk, unknown_uk = parse_ipa_to_phonemes(primary_ipa_uk)
            for u in unknown_uk:
                unknown_ipa_symbols.add(u)
        for u in unknown_us:
            unknown_ipa_symbols.add(u)

        if not phoneme_tags_us:
            rejection_reasons["no_parsable_phonemes_us"] += 1
            continue

        entry = {
            "word_id": word,
            "word": word,
            "level": "beginner",
            "ipa_us": primary_ipa_us,
            "ipa_uk": primary_ipa_uk or None,
            "phoneme_tags_us": phoneme_tags_us,
            "phoneme_tags_uk": phoneme_tags_uk if phoneme_tags_uk else None,
            "meaning_zh": None,
            "difficulty_tags": [],
            "minimal_pair_group": None,
            "frequency_zipf": round(freq, 2),
            "candidate_score": 0.0,
            "audio_us": None,
            "audio_uk": None,
            "source_ipa_us": "open-dict-data/ipa-dict en_US",
            "source_ipa_uk": "open-dict-data/ipa-dict en_UK" if ipa_uk else None,
            "source_frequency": "wordfreq",
            "license_notes": "open-data (wordfreq: MIT/Apache-2.0, ipa-dict: see repo)",
            "content_status": "candidate",
            "review_status_us": "auto_checked",
            "review_status_uk": "auto_checked" if ipa_uk else "draft",
        }
        candidates.append(entry)

    print(f"  Input words:             {len(freq_words)}")
    print(f"  Joined with US IPA:      {joined_us}")
    print(f"  Joined with UK IPA:      {joined_uk}")
    print(f"  Dual accent available:   {dual_accent}")
    print(f"  After hard filters:      {len(candidates)}")
    print(f"  Rejection reasons:")
    for reason, count in rejection_reasons.most_common():
        print(f"    {reason}: {count}")
    print(f"  Unknown IPA symbols:     {len(unknown_ipa_symbols)}")

    # Step 4: Score candidates
    print("\n[4/6] Scoring candidates...")
    phoneme_counts = Counter()
    for c in candidates:
        for tag in c["phoneme_tags_us"]:
            phoneme_counts[tag] += 1

    for c in candidates:
        c["candidate_score"] = round(
            score_candidate(
                c["word"], c["frequency_zipf"], c["phoneme_tags_us"],
                c["ipa_us"], c["ipa_uk"] or "", config, phoneme_counts
            ),
            1,
        )

    # Sort by score
    candidates.sort(key=lambda c: c["candidate_score"], reverse=True)

    if candidates:
        print(f"  Score range: {candidates[-1]['candidate_score']:.1f} – {candidates[0]['candidate_score']:.1f}")
    else:
        print("  No candidates to score — all words were filtered out.")
        print("  Consider relaxing hard filters in selection_config.json (e.g. lower min_frequency_zipf).")
        sys.exit(1)

    # Step 5: Greedy select Core 100 and Core 300
    print("\n[5/6] Greedy phoneme-coverage selection...")
    core_100 = greedy_select(list(candidates), 100, config)
    core_300 = greedy_select(list(candidates), 300, config)

    # Mark selection status
    core_100_ids = {c["word_id"] for c in core_100}
    core_300_ids = {c["word_id"] for c in core_300}
    for c in candidates:
        if c["word_id"] in core_100_ids:
            c["content_status"] = "auto_selected"
        elif c["word_id"] in core_300_ids:
            c["content_status"] = "auto_selected"

    print(f"  Core 100: {len(core_100)} words selected")
    print(f"  Core 300: {len(core_300)} words selected")

    # Step 6: Build report
    print("\n[6/6] Writing output files...")

    # Coverage analysis
    targets = config.get("phoneme_coverage_targets_us", {})
    phoneme_cov_100 = Counter()
    for c in core_100:
        for tag in c["phoneme_tags_us"]:
            phoneme_cov_100[tag] += 1
    phoneme_cov_300 = Counter()
    for c in core_300:
        for tag in c["phoneme_tags_us"]:
            phoneme_cov_300[tag] += 1

    # UK coverage (Core 300 words that have UK phoneme tags)
    phoneme_cov_uk = Counter()
    uk_tagged_words = 0
    for c in core_300:
        uk_tags = c.get("phoneme_tags_uk")
        if uk_tags:
            uk_tagged_words += 1
            for tag in uk_tags:
                phoneme_cov_uk[tag] += 1

    top_missing = []
    for phoneme, target in sorted(targets.items(), key=lambda x: -x[1]):
        actual = phoneme_cov_300.get(phoneme, 0)
        if actual < target:
            top_missing.append({"phoneme": phoneme, "target": target, "actual": actual, "gap": target - actual})

    # Build report
    sample_selected = [c["word"] for c in candidates if c["content_status"] == "auto_selected"][:10]
    sample_rejected = []
    for word, freq in freq_words:
        if word not in {c["word"] for c in candidates}:
            sample_rejected.append(word)
        if len(sample_rejected) >= 10:
            break

    # Known gaps that need manual curation for M1 seed pack
    known_manual_gaps = {
        "/ʌ/": "ipa-dict uses /ə/ for STRUT vowel; word-stress analysis needed to distinguish",
        "/ɚ/": "ipa-dict uses /ɝ/ for r-colored vowels including unstressed positions",
        "/ʒ/": "genuinely rare phoneme; only ~24 words in Core 300 have it",
    }

    report = {
        "input_word_count": len(freq_words),
        "joined_us_count": joined_us,
        "joined_uk_count": joined_uk,
        "dual_accent_count": dual_accent,
        "selected_count": len(candidates),
        "core_100_count": len(core_100),
        "core_300_count": len(core_300),
        "rejection_reasons": dict(rejection_reasons),
        "phoneme_coverage_us": dict(phoneme_cov_300),
        "phoneme_coverage_uk": dict(phoneme_cov_uk),
        "uk_tagged_in_core_300": uk_tagged_words,
        "unknown_ipa_symbols": sorted(list(unknown_ipa_symbols)),
        "top_missing_phonemes": top_missing[:10],
        "known_manual_gaps": known_manual_gaps,
        "license_summary": "open-data (wordfreq: MIT/Apache-2.0, ipa-dict: see repo license)",
        "sample_selected_words": sample_selected,
        "sample_rejected_words": sample_rejected,
        "curation_note": (
            "Core 300 candidates are auto-selected for phoneme coverage, not curated for classroom use. "
            "M1 seed pack (Issue #5) requires human review: (1) remove remaining function words or "
            "age-inappropriate words, (2) manually add words for /ʌ/, /ɚ/, /ʒ/ gaps, "
            "(3) verify minimal-pair suitability, and (4) add Chinese short meanings."
        ),
    }

    # Write outputs
    with open(output_dir / "candidate_words.json", "w", encoding="utf-8") as fh:
        json.dump(candidates, fh, indent=2, ensure_ascii=False)
    with open(output_dir / "core_100_candidates.json", "w", encoding="utf-8") as fh:
        json.dump(core_100, fh, indent=2, ensure_ascii=False)
    with open(output_dir / "core_300_candidates.json", "w", encoding="utf-8") as fh:
        json.dump(core_300, fh, indent=2, ensure_ascii=False)
    with open(output_dir / "content_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n  Output files written to {output_dir}/")
    print(f"\n{'=' * 60}")
    print("CONTENT REPORT SUMMARY")
    print(f"{'=' * 60}")
    print(f"Input words:          {report['input_word_count']}")
    print(f"Joined US IPA:        {report['joined_us_count']}")
    print(f"Joined UK IPA:        {report['joined_uk_count']}")
    print(f"Dual accent:          {report['dual_accent_count']}")
    print(f"After filters:        {report['selected_count']}")
    print(f"Core 100:             {report['core_100_count']}")
    print(f"Core 300:             {report['core_300_count']}")
    print(f"Unknown IPA symbols:  {len(report['unknown_ipa_symbols'])}")
    if report["unknown_ipa_symbols"]:
        print(f"  Symbols: {', '.join(report['unknown_ipa_symbols'][:20])}")
    print(f"Core 300 UK-tagged:    {report['uk_tagged_in_core_300']}")
    print(f"\nTop missing phonemes (Core 300 vs targets):")
    for m in top_missing[:5]:
        print(f"  {m['phoneme']}: have {m['actual']}, need {m['target']} (gap: {m['gap']})")
    if top_missing:
        print(f"\nKnown manual gaps (need human curation for M1 seed pack):")
        for phoneme, note in report["known_manual_gaps"].items():
            print(f"  {phoneme}: {note}")
    print(f"\nSample selected: {', '.join(sample_selected)}")
    print(f"Sample rejected: {', '.join(sample_rejected[:8])}")
    print(f"\nCURATION NOTE:")
    print(f"  {report['curation_note']}")

    # Feasibility answer
    print(f"\n{'=' * 60}")
    print("FEASIBILITY ASSESSMENT")
    print(f"{'=' * 60}")
    if report["selected_count"] >= 300:
        print("PASS: ≥300 candidates produced. Core 300 is feasible from these sources.")
    elif report["selected_count"] >= 150:
        print("MARGINAL: 150-299 candidates. Core 300 may need supplemental sources or relaxed filters.")
    else:
        print("FAIL: <150 candidates. Auto-selection from wordfreq + ipa-dict alone is insufficient.")
        print("  Consider adding SUBTLEX-US, CEFR-J, or relaxing hard filters.")


if __name__ == "__main__":
    main()
