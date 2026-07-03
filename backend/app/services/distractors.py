"""Runtime distractor scoring for reverse word-choice questions."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from app.models import Word

_VOWEL_NUCLEUS_RE = re.compile(
    r"(?:iː|uː|eɪ|aɪ|oʊ|aʊ|ɔɪ|ɪ|ʊ|e|æ|ɑ|ɔ|ʌ|ə|ɝ|ɚ|ɒ|ɐ|ɜ|i|u)"
)


@dataclass(frozen=True)
class DistractorCandidate:
    word: Word
    score: float
    shared_phonemes: int
    ipa_similarity: float
    syllable_delta: int
    word_length_delta: int
    difficulty_overlap: int
    fallback: bool


def active_ipa(word: Word, accent: str = "US") -> str:
    if accent.upper() == "UK" and word.ipa_uk:
        return word.ipa_uk
    return word.ipa_us


def active_phonemes(word: Word, accent: str = "US") -> list[str]:
    if accent.upper() == "UK" and word.phoneme_tags_uk:
        return word.phoneme_tags_uk
    return word.phoneme_tags_us


def estimate_syllable_count(ipa: str) -> int:
    if not ipa:
        return 0
    return len(_VOWEL_NUCLEUS_RE.findall(ipa.replace("/", "")))


def _stable_jitter(seed: int | None, value: str) -> float:
    digest = hashlib.md5(f"{seed or 0}:{value}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _same_level(target: Word, candidate: Word) -> bool:
    return bool(target.level and candidate.level and target.level == candidate.level)


def score_choose_word_candidate(
    target: Word,
    candidate: Word,
    *,
    accent: str = "US",
) -> DistractorCandidate | None:
    if candidate.id == target.id or candidate.word == target.word:
        return None
    if candidate.content_status == "disabled":
        return None
    if not _same_level(target, candidate):
        return None

    target_ipa = active_ipa(target, accent)
    candidate_ipa = active_ipa(candidate, accent)
    if not target_ipa or not candidate_ipa:
        return None
    if candidate_ipa == target_ipa:
        return None

    target_phonemes = set(active_phonemes(target, accent))
    candidate_phonemes = set(active_phonemes(candidate, accent))
    shared_phonemes = len(target_phonemes & candidate_phonemes)
    similarity = SequenceMatcher(None, target_ipa, candidate_ipa).ratio()
    syllable_delta = abs(
        estimate_syllable_count(target_ipa) - estimate_syllable_count(candidate_ipa)
    )
    word_length_delta = abs(len(target.word) - len(candidate.word))
    target_tags = set(target.difficulty_tags or [])
    candidate_tags = set(candidate.difficulty_tags or [])
    difficulty_overlap = len(target_tags & candidate_tags)

    score = (
        shared_phonemes * 4.0
        + similarity * 3.0
        + max(0, 3 - syllable_delta) * 1.25
        + max(0, 6 - word_length_delta) * 0.35
        + difficulty_overlap * 1.5
    )
    fallback = shared_phonemes == 0 and difficulty_overlap == 0 and similarity < 0.45
    return DistractorCandidate(
        word=candidate,
        score=round(score, 4),
        shared_phonemes=shared_phonemes,
        ipa_similarity=round(similarity, 4),
        syllable_delta=syllable_delta,
        word_length_delta=word_length_delta,
        difficulty_overlap=difficulty_overlap,
        fallback=fallback,
    )


def choose_word_distractors(
    target: Word,
    candidates: Iterable[Word],
    *,
    accent: str = "US",
    seed: int | None = None,
    limit: int = 3,
) -> list[DistractorCandidate]:
    scored = [
        score
        for candidate in candidates
        if (score := score_choose_word_candidate(target, candidate, accent=accent))
        is not None
    ]
    return sorted(
        scored,
        key=lambda item: (
            -item.score,
            _stable_jitter(seed, item.word.id),
            item.word.word,
        ),
    )[:limit]


def build_choose_word_quality_report(
    words: Iterable[Word],
    *,
    accent: str = "US",
    choice_count: int = 4,
    sample_limit: int = 10,
) -> dict:
    usable = [
        word
        for word in words
        if word.content_status != "disabled" and word.word and active_ipa(word, accent)
    ]
    distractor_limit = max(choice_count - 1, 1)
    by_level: dict[str, dict] = {}
    exact_ipa_groups: dict[tuple[str, str], list[Word]] = {}
    target_samples = []

    for word in usable:
        level = word.level or "unknown"
        level_summary = by_level.setdefault(
            level,
            {
                "targets": 0,
                "full_choice_targets": 0,
                "sparse_targets": 0,
                "fallback_distractors": 0,
                "same_ipa_excluded_pairs": 0,
                "sparse_samples": [],
            },
        )
        level_summary["targets"] += 1
        key = (level, active_ipa(word, accent))
        exact_ipa_groups.setdefault(key, []).append(word)

        choices = choose_word_distractors(
            word,
            usable,
            accent=accent,
            seed=0,
            limit=distractor_limit,
        )
        if len(choices) >= distractor_limit:
            level_summary["full_choice_targets"] += 1
        else:
            level_summary["sparse_targets"] += 1
            if len(level_summary["sparse_samples"]) < sample_limit:
                level_summary["sparse_samples"].append(
                    {
                        "word_id": word.id,
                        "word": word.word,
                        "level": level,
                        "ipa": active_ipa(word, accent),
                        "distractor_count": len(choices),
                    }
                )
        fallback_count = sum(1 for choice in choices if choice.fallback)
        level_summary["fallback_distractors"] += fallback_count
        if len(target_samples) < sample_limit:
            target_samples.append(
                {
                    "word_id": word.id,
                    "word": word.word,
                    "level": level,
                    "ipa": active_ipa(word, accent),
                    "distractors": [
                        {
                            "word_id": choice.word.id,
                            "word": choice.word.word,
                            "score": choice.score,
                            "shared_phonemes": choice.shared_phonemes,
                            "ipa_similarity": choice.ipa_similarity,
                            "fallback": choice.fallback,
                        }
                        for choice in choices
                    ],
                }
            )

    ambiguous_groups = [
        {
            "level": level,
            "ipa": ipa,
            "words": [word.word for word in group],
            "word_ids": [word.id for word in group],
        }
        for (level, ipa), group in sorted(exact_ipa_groups.items())
        if len(group) > 1
    ]
    for group in ambiguous_groups:
        count = len(group["word_ids"])
        by_level[group["level"]]["same_ipa_excluded_pairs"] += count * (count - 1)

    for level_summary in by_level.values():
        targets = level_summary["targets"]
        level_summary["full_choice_rate"] = _rate(
            level_summary["full_choice_targets"], targets
        )
        level_summary["sparse_target_rate"] = _rate(
            level_summary["sparse_targets"], targets
        )
        expected_distractors = targets * distractor_limit
        level_summary["fallback_distractor_rate"] = _rate(
            level_summary["fallback_distractors"], expected_distractors
        )

    totals = {
        "targets": sum(level["targets"] for level in by_level.values()),
        "full_choice_targets": sum(
            level["full_choice_targets"] for level in by_level.values()
        ),
        "sparse_targets": sum(level["sparse_targets"] for level in by_level.values()),
        "fallback_distractors": sum(
            level["fallback_distractors"] for level in by_level.values()
        ),
        "same_ipa_excluded_pairs": sum(
            level["same_ipa_excluded_pairs"] for level in by_level.values()
        ),
    }
    expected_total_distractors = totals["targets"] * distractor_limit
    totals["full_choice_rate"] = _rate(totals["full_choice_targets"], totals["targets"])
    totals["sparse_target_rate"] = _rate(totals["sparse_targets"], totals["targets"])
    totals["fallback_distractor_rate"] = _rate(
        totals["fallback_distractors"], expected_total_distractors
    )
    return {
        "report_name": "M13 choose_word distractor quality report",
        "accent": accent.upper(),
        "choice_count": choice_count,
        "scoring_signals": [
            "shared_target_phonemes",
            "ipa_similarity",
            "syllable_count_delta",
            "difficulty_tag_overlap",
            "word_length_delta",
            "learner_level_partition",
        ],
        "totals": totals,
        "by_level": by_level,
        "ambiguous_same_ipa_groups": ambiguous_groups[:sample_limit],
        "samples": target_samples,
        "residual_risks": [
            (
                "Runtime scoring is heuristic; curated confusable metadata remains "
                "a possible follow-up."
            ),
            (
                "Exact same active-accent IPA alternatives are excluded rather "
                "than treated as multi-correct."
            ),
        ],
    }


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)
