"""Domain models for the Tiny IPA runtime data layer.

Plain dataclasses that mirror the SQLite tables defined in the DDL schema.
They are used as return types from repositories — not as ORM entities.
Callers construct them from ``sqlite3.Row`` dicts or raw kwargs.
"""

from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------

@dataclass
class Word:
    """A single word entry in the runtime database."""

    id: str
    word: str
    level: str
    ipa_us: str
    phoneme_tags_us: List[str]
    content_status: str
    ipa_uk: Optional[str] = None
    phoneme_tags_uk: Optional[List[str]] = None
    meaning_zh: Optional[str] = None
    audio_us: Optional[str] = None
    audio_uk: Optional[str] = None
    difficulty_tags: Optional[List[str]] = None
    minimal_pair_group: Optional[str] = None


# ---------------------------------------------------------------------------
# Phonemes
# ---------------------------------------------------------------------------

@dataclass
class Phoneme:
    """A phoneme entry imported from ``content/phonemes.json``."""

    id: str
    symbol: str
    accent_scope: str  # "US" | "UK" | "both"
    category: str
    priority: int
    example_word: Optional[str] = None
    description_zh: Optional[str] = None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    """Per-user settings row. MVP has only user_id="default"."""

    user_id: str = "default"
    primary_accent: str = "US"
    daily_word_count: int = 10
    show_translation: bool = True
    show_accent_compare: bool = False
    practice_mode: str = "ipa_first"
    review_strength: str = "normal"
    learner_level: str = "entry"
    ui_language: str = "zh-CN"
    focus_phonemes: List[str] = field(default_factory=list)
    updated_at: str = ""


# ---------------------------------------------------------------------------
# Daily sessions (defined for M2 completeness; tested in later issues)
# ---------------------------------------------------------------------------

@dataclass
class DailySession:
    id: str
    user_id: str
    session_date: str
    primary_accent: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    group_index: int = 1
    group_type: str = "normal"
    learner_level: str = "entry"
    source_session_item_ids: List[str] = field(default_factory=list)
    source_scope: Optional[str] = None
    source_group_id: Optional[str] = None
    focus_phonemes: List[str] = field(default_factory=list)


@dataclass
class SessionItem:
    id: str
    session_id: str
    word_id: str
    order_index: int
    target_phonemes: List[str]
    question_type: str
    status: str


@dataclass
class Attempt:
    id: str
    user_id: str
    session_item_id: str
    word_id: str
    primary_accent: str
    question_type: str
    correct_answer: str
    is_correct: bool
    created_at: str
    target_phoneme: Optional[str] = None
    selected_answer: Optional[str] = None


@dataclass
class PhonemeStat:
    user_id: str
    primary_accent: str
    phoneme_id: str
    attempt_count: int
    correct_count: int
    mastery_status: str
    last_attempt_at: Optional[str] = None
    last_wrong_at: Optional[str] = None
