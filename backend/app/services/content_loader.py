"""Load and cache static content from seed_words.json."""

import json
from pathlib import Path
from typing import Dict, List, Optional

# Cache loaded words so we don't re-read the file on every request.
_cache: Optional[List[dict]] = None
_cache_by_id: Optional[Dict[str, dict]] = None


def _find_seed_file() -> Path:
    """Locate seed_words.json relative to the repo root."""
    # Start from this file's location and walk up to find content/seed_words.json
    here = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = here / "content" / "seed_words.json"
        if candidate.exists():
            return candidate
        here = here.parent
    raise FileNotFoundError("Cannot locate content/seed_words.json from project root")


def load_words() -> List[dict]:
    """Load all words from the seed pack. Results are cached in memory."""
    global _cache, _cache_by_id
    if _cache is not None:
        return _cache

    path = _find_seed_file()
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    words = data.get("words", data) if isinstance(data, dict) else data
    _cache = words
    _cache_by_id = {w["word_id"]: w for w in words}
    return words


def get_word(word_id: str) -> Optional[dict]:
    """Get a single word by its word_id."""
    if _cache_by_id is None:
        load_words()
    return _cache_by_id.get(word_id)


def get_enabled_words() -> List[dict]:
    """Return only words whose content_status is not 'disabled'."""
    return [w for w in load_words() if w.get("content_status") != "disabled"]
