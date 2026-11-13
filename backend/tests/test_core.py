import os
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from app.routers.ai import interpret, rank_events, RankedEvents
from app.schemas import EventOut
from run_parcer import parse_date, parse_price
from uuid import uuid4


class ImportTests(unittest.TestCase):
    def test_price_normalization(self):
        for value, expected in [(0, 0), ("120.5", 121), (None, None), ("?", None), (-1, None)]:
            with self.subTest(value=value):
                self.assertEqual(parse_price(value), expected)

    def test_timestamp_without_offset_is_local(self):
        self.assertEqual(parse_date("2026-11-14T18:00:00").utcoffset(), timedelta(hours=5))

    def test_timestamp_with_offset_is_preserved(self):
        self.assertEqual(parse_date("2026-11-14T13:00:00Z").utcoffset(), timedelta(0))


class SearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_family_intent(self):
        with patch.dict(os.environ, {"OLLAMA_URL": ""}):
            intent, used = await interpret("В Уфе в субботу с ребёнком до 1 000 рублей", date(2026, 11, 13), ["Уфа"], [])
        self.assertFalse(used)
        self.assertEqual(intent.date_from, date(2026, 11, 14))
        self.assertEqual(intent.budget, 1000)
        self.assertEqual(intent.age, 6)
        self.assertEqual(intent.city, "Уфа")

    async def test_free_search_and_explicit_age(self):
        with patch.dict(os.environ, {"OLLAMA_URL": ""}):
            intent, _ = await interpret("Бесплатный спектакль завтра, ребёнку 8 лет", date(2026, 11, 13), [], [])
        self.assertEqual(intent.budget, 0)
        self.assertEqual(intent.age, 8)
        self.assertEqual(intent.category, "theater")

    async def test_ranking_uses_only_catalog_events(self):
        events = [EventOut(id=uuid4(), title=str(index), start_at="2026-11-14T13:00:00Z") for index in range(3)]
        with patch("app.routers.ai.ask_model", return_value=RankedEvents(positions=[3, 3, 1])):
            ranked, used = await rank_events("поиск", events)
        self.assertTrue(used)
        self.assertEqual(ranked, [events[2], events[0], events[1]])

    async def test_invalid_model_positions_fall_back(self):
        events = [EventOut(id=uuid4(), title="Афиша", start_at="2026-11-14T13:00:00Z")]
        with patch("app.routers.ai.ask_model", return_value=RankedEvents(positions=[0])):
            ranked, used = await rank_events("поиск", events)
        self.assertFalse(used)
        self.assertEqual(ranked, events)


class TelegramSignatureTests(unittest.TestCase):
    def test_signature_and_expiry(self):
        import hashlib
        import hmac
        from app.routers.auth import verified_telegram_user

        payload = {"id": 123, "auth_date": 1000, "first_name": "Имя"}
        check = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
        payload["hash"] = hmac.new(hashlib.sha256(b"token").digest(), check.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(verified_telegram_user(payload, "token", 1050), ("123", "Имя"))
        self.assertIsNone(verified_telegram_user(payload, "token", 1400))
        self.assertIsNone(verified_telegram_user({**payload, "id": 999}, "token", 1050))


class BotTests(unittest.TestCase):
    def test_format_includes_local_time_and_zero_price(self):
        from app.bot import format_results

        reply = format_results({"explanation": "Подборка", "events": [{
            "title": "Спектакль", "start_at": "2026-11-14T13:00:00Z", "price_min": 0,
            "address": "Уфа", "source_urls": ["https://example.org/show"],
        }]})
        self.assertIn("14.11 18:00 · Бесплатно", reply)
        self.assertIn("https://example.org/show", reply)
