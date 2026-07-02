"""Settings endpoint — GET/PUT /api/settings."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth_dependencies import require_current_user
from app.db import get_db
from app.models import Settings, User
from app.services.db_store import get_settings, upsert_settings

router = APIRouter()

_VALID_ACCENTS = {"US", "UK"}
_VALID_MODES = {"ipa_first", "reveal_first"}
_VALID_STRENGTHS = {"normal", "extra_review", "quick"}
_VALID_LEARNER_LEVELS = {"entry", "mid"}
_VALID_UI_LANGUAGES = {"zh-CN", "en-US"}


@router.get("/settings")
def settings_get(current_user: User = Depends(require_current_user)):
    """Return current settings for the default user."""
    with get_db() as conn:
        s = get_settings(conn, current_user.id)
        if s is None:
            # Return defaults if never initialised
            return {
                "primary_accent": "US",
                "daily_word_count": 10,
                "show_translation": True,
                "show_accent_compare": False,
                "practice_mode": "ipa_first",
                "review_strength": "normal",
                "learner_level": "entry",
                "ui_language": "zh-CN",
                "focus_phonemes": [],
            }
        return {
            "primary_accent": s.primary_accent,
            "daily_word_count": s.daily_word_count,
            "show_translation": s.show_translation,
            "show_accent_compare": s.show_accent_compare,
            "practice_mode": s.practice_mode,
            "review_strength": s.review_strength,
            "learner_level": s.learner_level,
            "ui_language": s.ui_language,
            "focus_phonemes": s.focus_phonemes,
        }


@router.put("/settings")
async def settings_put(
    request: Request,
    current_user: User = Depends(require_current_user),
):
    """Update settings for the default user.

    Accepts a partial update — only provided fields are changed.
    """
    body = await request.json()

    with get_db() as conn:
        existing = get_settings(conn, current_user.id)
        if existing is None:
            existing = Settings(user_id=current_user.id)

        # Validate and apply each field
        errors = []

        if "primary_accent" in body:
            v = body["primary_accent"]
            if v not in _VALID_ACCENTS:
                errors.append(f"primary_accent must be one of {_VALID_ACCENTS}")
            else:
                existing.primary_accent = v

        if "daily_word_count" in body:
            v = body["daily_word_count"]
            if not isinstance(v, int) or v < 1 or v > 50:
                errors.append("daily_word_count must be an integer between 1 and 50")
            else:
                existing.daily_word_count = v

        if "show_translation" in body:
            v = body["show_translation"]
            if not isinstance(v, bool):
                errors.append("show_translation must be a boolean")
            else:
                existing.show_translation = v

        if "show_accent_compare" in body:
            v = body["show_accent_compare"]
            if not isinstance(v, bool):
                errors.append("show_accent_compare must be a boolean")
            else:
                existing.show_accent_compare = v

        if "practice_mode" in body:
            v = body["practice_mode"]
            if v not in _VALID_MODES:
                errors.append(f"practice_mode must be one of {_VALID_MODES}")
            else:
                existing.practice_mode = v

        if "review_strength" in body:
            v = body["review_strength"]
            if v not in _VALID_STRENGTHS:
                errors.append(f"review_strength must be one of {_VALID_STRENGTHS}")
            else:
                existing.review_strength = v

        if "learner_level" in body:
            v = body["learner_level"]
            if v not in _VALID_LEARNER_LEVELS:
                errors.append(f"learner_level must be one of {_VALID_LEARNER_LEVELS}")
            else:
                existing.learner_level = v

        if "ui_language" in body:
            v = body["ui_language"]
            if v not in _VALID_UI_LANGUAGES:
                errors.append(f"ui_language must be one of {_VALID_UI_LANGUAGES}")
            else:
                existing.ui_language = v

        if "focus_phonemes" in body:
            v = body["focus_phonemes"]
            if not isinstance(v, list) or any(
                not isinstance(item, str) or not item.strip() for item in v
            ):
                errors.append("focus_phonemes must be a list of non-empty strings")
            else:
                existing.focus_phonemes = [item.strip() for item in v]

        if errors:
            raise HTTPException(
                status_code=400,
                detail={"error": "SETTINGS_INVALID", "detail": "; ".join(errors)},
            )

        existing.updated_at = datetime.now(timezone.utc).isoformat()
        upsert_settings(conn, existing)

        return {
            "primary_accent": existing.primary_accent,
            "daily_word_count": existing.daily_word_count,
            "show_translation": existing.show_translation,
            "show_accent_compare": existing.show_accent_compare,
            "practice_mode": existing.practice_mode,
            "review_strength": existing.review_strength,
            "learner_level": existing.learner_level,
            "ui_language": existing.ui_language,
            "focus_phonemes": existing.focus_phonemes,
        }
