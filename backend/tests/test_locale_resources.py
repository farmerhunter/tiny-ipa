"""Validate M11 locale resources and fallback contract."""

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = (
    REPO_ROOT / "frontend" / "tests" / "fixtures" / "ui-language-copy-inventory.json"
)
LOCALES_DIR = REPO_ROOT / "frontend" / "src" / "locales"
DEFAULT_LOCALE = "zh-CN"
FALLBACK_LOCALE = "en-US"
SUPPORTED_LOCALES = ["zh-CN", "en-US"]
PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z][a-zA-Z0-9_]*)\}")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_resources():
    return {
        locale: load_json(LOCALES_DIR / f"{locale}.json")
        for locale in SUPPORTED_LOCALES
    }


def missing_marker(locale: str, key: str) -> str:
    return f"⟦missing:{locale}:{key}⟧"


def translate(
    locale: str,
    key: str,
    *,
    environment: str = "test",
    resources: dict[str, dict[str, str]] | None = None,
) -> str:
    resolved_locale = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    resources = resources or load_resources()
    text = resources[resolved_locale].get(key)
    if text is not None:
        return text

    fallback = resources[FALLBACK_LOCALE].get(key)
    if environment == "production" and fallback is not None:
        return fallback

    return missing_marker(resolved_locale, key)


def test_supported_locale_resource_files_match_contract():
    inventory = load_json(INVENTORY_PATH)

    assert inventory["default_locale"] == DEFAULT_LOCALE
    assert inventory["selectable_locales"] == SUPPORTED_LOCALES
    assert sorted(path.name for path in LOCALES_DIR.glob("*.json")) == [
        "en-US.json",
        "zh-CN.json",
    ]


def test_locale_resources_are_complete_for_translatable_inventory():
    inventory = load_json(INVENTORY_PATH)
    expected_keys = {
        entry["key"]
        for entry in inventory["entries"]
        if entry["classification"] == "translatable"
    }
    resources = load_resources()

    for locale, resource in resources.items():
        resource_keys = set(resource)
        assert expected_keys <= resource_keys, locale
        assert not resource_keys - expected_keys, locale
        assert all(resource[key].strip() for key in expected_keys)


def test_locale_resource_placeholders_match_between_supported_locales():
    resources = load_resources()
    en_us = resources["en-US"]
    zh_cn = resources["zh-CN"]

    for key, text in en_us.items():
        assert set(PLACEHOLDER_RE.findall(zh_cn[key])) == set(
            PLACEHOLDER_RE.findall(text)
        ), key


def test_default_unknown_locale_and_missing_key_behavior():
    assert translate("fr-FR", "app.nav.today") == "今日"
    assert translate("zh-CN", "missing.action") == "⟦missing:zh-CN:missing.action⟧"
    assert translate("zh-CN", "missing.action", environment="production") == (
        "⟦missing:zh-CN:missing.action⟧"
    )


def test_production_missing_key_falls_back_to_en_us_when_available():
    resources = load_resources()
    resources["zh-CN"] = dict(resources["zh-CN"])
    resources["zh-CN"].pop("app.nav.today")

    assert (
        translate(
            "zh-CN",
            "app.nav.today",
            environment="test",
            resources=resources,
        )
        == "⟦missing:zh-CN:app.nav.today⟧"
    )
    assert (
        translate(
            "zh-CN",
            "app.nav.today",
            environment="production",
            resources=resources,
        )
        == "Today"
    )
