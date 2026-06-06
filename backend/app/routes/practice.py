"""Practice endpoints — daily session and item delivery."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from app.services.content_loader import get_enabled_words
from app.services.questions import generate_choose_ipa_question
from app.services.scheduler import select_daily_words

router = APIRouter()


@router.get("/today")
def get_today(
    daily_word_count: int = Query(10, ge=1, le=50),
    primary_accent: str = Query("US", pattern="^(US|UK)$"),
    session_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    """
    Return today's practice session with IPA-first items.

    The session is deterministic by date — same date always returns the
    same word list. No database writes occur; this is a read-only endpoint
    for Milestone 1.
    """
    if session_date is None:
        session_date = date.today().isoformat()

    words = get_enabled_words()
    daily = select_daily_words(words, daily_word_count, session_date)

    items = []
    for i, word in enumerate(daily):
        question = generate_choose_ipa_question(word)

        # Strip stress marks from display IPA for beginner readability
        raw_ipa = word[f"ipa_{primary_accent.lower()}"]
        display_ipa = raw_ipa.replace("ˈ", "").replace("ˌ", "")

        items.append({
            "session_item_id": f"static-{i + 1:03d}",
            "word_id": word["word_id"],
            "display_ipa": display_ipa,
            "word": word["word"],
            "meaning_zh": word.get("meaning_zh"),
            "audio_url": word.get(f"audio_{primary_accent.lower()}"),
            "target_phonemes": word.get(f"phoneme_tags_{primary_accent.lower()}", []),
            "question": question,
        })

    return {
        "session_id": f"static-{session_date}-default",
        "date": session_date,
        "primary_accent": primary_accent,
        "daily_word_count": daily_word_count,
        "status": "in_progress",
        "items": items,
    }
