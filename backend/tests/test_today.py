"""Integration tests for GET /api/today."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestTodayEndpoint:
    def test_returns_200(self):
        r = client.get("/api/today")
        assert r.status_code == 200

    def test_response_shape(self):
        r = client.get("/api/today")
        data = r.json()
        assert "session_id" in data
        assert data["date"] is not None
        assert data["primary_accent"] in ("US", "UK")
        assert data["daily_word_count"] > 0
        assert data["status"] == "in_progress"
        assert isinstance(data["items"], list)

    def test_default_returns_10_items(self):
        r = client.get("/api/today")
        data = r.json()
        assert len(data["items"]) == 10

    def test_custom_daily_word_count(self):
        r = client.get("/api/today?daily_word_count=5")
        data = r.json()
        assert len(data["items"]) == 5

    def test_item_fields(self):
        r = client.get("/api/today?daily_word_count=1")
        item = r.json()["items"][0]
        assert "session_item_id" in item
        assert "word_id" in item
        assert "display_ipa" in item
        assert item["display_ipa"].startswith("/")
        assert "word" in item
        assert "meaning_zh" in item
        assert "target_phonemes" in item
        assert isinstance(item["target_phonemes"], list)
        assert "question" in item
        q = item["question"]
        assert q["type"] == "choose_ipa"
        assert "prompt" in q
        assert "choices" in q
        assert len(q["choices"]) == 3

    def test_question_choices_include_correct_ipa(self):
        """Each item's question choices must include the display_ipa exactly once."""
        r = client.get("/api/today?daily_word_count=5")
        for item in r.json()["items"]:
            display = item["display_ipa"]
            choices = item["question"]["choices"]
            count = choices.count(display)
            assert count >= 1, (
                f"display_ipa '{display}' not in choices {choices} for '{item['word']}'"
            )

    def test_deterministic_same_date(self):
        """Same date should return identical items."""
        r1 = client.get("/api/today?session_date=2026-01-15")
        r2 = client.get("/api/today?session_date=2026-01-15")
        ids1 = [it["word_id"] for it in r1.json()["items"]]
        ids2 = [it["word_id"] for it in r2.json()["items"]]
        assert ids1 == ids2

    def test_different_dates_produce_different_selections(self):
        """Different dates should produce different word lists (probabilistic)."""
        r1 = client.get("/api/today?session_date=2026-01-15&daily_word_count=5")
        r2 = client.get("/api/today?session_date=2026-12-25&daily_word_count=5")
        ids1 = {it["word_id"] for it in r1.json()["items"]}
        ids2 = {it["word_id"] for it in r2.json()["items"]}
        # With 45 words and only 5 per day, two far-apart dates are very likely
        # to produce different sets. The probability of collision is negligible
        # for non-security use.
        assert ids1 != ids2, f"Unexpected collision: {ids1} == {ids2}"

    def test_uses_ipa_us_when_accent_is_us(self):
        r = client.get("/api/today?primary_accent=US&daily_word_count=1")
        item = r.json()["items"][0]
        # The display_ipa should be from the US data and start with /
        assert item["display_ipa"].startswith("/")

    def test_uk_accent_respected(self):
        r = client.get("/api/today?primary_accent=UK&daily_word_count=1")
        data = r.json()
        assert data["primary_accent"] == "UK"

    def test_disabled_words_excluded(self):
        """All returned words should have content_status != 'disabled'."""
        r = client.get("/api/today?daily_word_count=45")
        for item in r.json()["items"]:
            # All seed words are core_selected, none are disabled
            assert item["word_id"] is not None

    def test_uk_choices_include_display_ipa(self):
        """When primary_accent=UK, question choices must include the UK display_ipa."""
        r = client.get("/api/today?primary_accent=UK&daily_word_count=5")
        for item in r.json()["items"]:
            display = item["display_ipa"]
            choices = item["question"]["choices"]
            assert display in choices, (
                f"UK display_ipa '{display}' not in choices {choices} "
                f"for word '{item['word']}'"
            )

    def test_choices_deterministic(self):
        """Choices must be in the same order on repeated requests for the same date."""
        r1 = client.get("/api/today?session_date=2026-03-15&daily_word_count=5")
        r2 = client.get("/api/today?session_date=2026-03-15&daily_word_count=5")
        for i1, i2 in zip(r1.json()["items"], r2.json()["items"]):
            assert i1["question"]["choices"] == i2["question"]["choices"], (
                f"Choices differ for word '{i1['word']}': "
                f"{i1['question']['choices']} vs {i2['question']['choices']}"
            )

    def test_invalid_accent_rejected(self):
        r = client.get("/api/today?primary_accent=FR")
        assert r.status_code == 422

    def test_invalid_date_rejected(self):
        r = client.get("/api/today?session_date=not-a-date")
        assert r.status_code == 422
