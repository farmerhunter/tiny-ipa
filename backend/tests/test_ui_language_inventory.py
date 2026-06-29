"""Validate the M11 UI language copy inventory fixture."""

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = (
    REPO_ROOT / "frontend" / "tests" / "fixtures" / "ui-language-copy-inventory.json"
)
REQUIRED_SURFACES = {
    "app_shell",
    "today",
    "today_hub",
    "practice",
    "practice_summary",
    "review_focus",
    "audio",
    "progress",
    "settings",
    "loading_error",
    "domain_tokens",
    "content_data",
    "developer_only",
}
REQUIRED_CLASSIFICATIONS = {
    "translatable",
    "domain_token",
    "content_data",
    "developer_only",
}


def test_ui_language_inventory_schema_and_coverage():
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))

    assert inventory["default_locale"] == "zh-CN"
    assert inventory["selectable_locales"] == ["zh-CN", "en-US"]
    assert set(inventory["classifications"]) == REQUIRED_CLASSIFICATIONS

    entries = inventory["entries"]
    assert entries

    keys = [entry["key"] for entry in entries]
    assert len(keys) == len(set(keys))
    assert all(key == key.lower() for key in keys)
    assert all(" " not in key for key in keys)

    surfaces = {entry["surface"] for entry in entries}
    assert REQUIRED_SURFACES <= surfaces

    for entry in entries:
        assert entry["classification"] in REQUIRED_CLASSIFICATIONS
        assert entry["surface"] in REQUIRED_SURFACES
        assert entry["source"]
        assert entry["current"]


def test_ui_language_inventory_preserves_domain_and_content_boundaries():
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    by_key = {entry["key"]: entry for entry in inventory["entries"]}

    assert by_key["token.ipa_symbols"]["classification"] == "domain_token"
    assert by_key["token.accent_identifiers"]["classification"] == "domain_token"
    assert by_key["token.api_enums"]["classification"] == "domain_token"
    assert by_key["token.error_codes"]["classification"] == "domain_token"
    assert by_key["content.word_values"]["classification"] == "content_data"
    assert by_key["content.word_values"]["current"].find("meaning_zh") != -1
