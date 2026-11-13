import asyncio
import hashlib
import hmac
import time
import unittest
from datetime import datetime, timedelta, timezone

import httpx

from app import crud, models, schemas
from app.database import AsyncSessionLocal
from app.region import refresh_verified_sources


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async with AsyncSessionLocal.begin() as db:
            source = await crud.get_or_create_source(db, "Fixture", "https://example.org")
            city = models.City(name="Уфа")
            category = models.Category(name="Театр", slug="theater")
            db.add_all([city, category])
            await db.flush()
            self.city_id = str(city.id)
            self.category_id = str(category.id)
            event = schemas.EventCreate(
                title="Детский спектакль", address="Театр", city_id=city.id,
                category_id=category.id, start_at=datetime.now(timezone.utc) + timedelta(days=1),
                age_limit=6, price_min=0, price_max=0, source_id=source.id,
                source_url="https://example.org/show", external_id="show",
                raw_data={"isSchoolFriendly": True, "venue": {"latitude": 54.73, "longitude": 55.96}},
            )
            _, created = await crud.upsert_event(db, event)
            self.assertTrue(created)
            _, created = await crud.upsert_event(db, event)
            self.assertFalse(created)
            await crud.upsert_event(db, event.model_copy(update={
                "external_id": "adult", "title": "Взрослый концерт", "raw_data": {"venue": {"latitude": 54.73, "longitude": 55.96}},
            }))
            await crud.upsert_event(db, event.model_copy(update={
                "external_id": "draft", "title": "Скрытый", "status": "draft",
            }))

            await crud.upsert_event(db, event.model_copy(update={
                "external_id": "moscow", "title": "Москва", "raw_data": {"venue": {"latitude": 55.65, "longitude": 37.41}},
            }))
            await refresh_verified_sources(db)

    async def test_catalog_and_search_through_web_proxy(self):
        async with httpx.AsyncClient(base_url="http://web") as client:
            for attempt in range(10):
                try:
                    homepage = await client.get("/")
                    homepage.raise_for_status()
                    break
                except httpx.HTTPError:
                    if attempt == 9:
                        raise
                    await asyncio.sleep(1)
            self.assertIn("Вне афиши", homepage.text)
            self.assertEqual((await client.get("/api/health")).json(), {"status": "ok"})
            self.assertEqual((await client.get("/api/events/cities")).json()[0]["id"], self.city_id)
            self.assertEqual((await client.get("/api/events/categories")).json()[0]["id"], self.category_id)

            response = await client.get("/api/events/", params={
                "city_id": self.city_id, "category_id": self.category_id, "price_max": 0,
            })
            response.raise_for_status()
            events = response.json()
            self.assertEqual(len(events), 2)
            events = [event for event in events if event["title"] == "Детский спектакль"]
            self.assertEqual(events[0]["latitude"], 54.73)
            self.assertEqual(events[0]["source_urls"], ["https://example.org/show"])
            self.assertEqual((await client.get("/api/events/?limit=0")).status_code, 422)
            self.assertEqual((await client.post("/api/sources/", json={"name": "X", "base_url": "https://x.test"})).status_code, 403)
            answer = (await client.post("/api/ai/search", json={"text": "Бесплатный спектакль в Уфе с ребёнком"})).json()
            self.assertEqual(answer["events"][0]["id"], events[0]["id"])
            self.assertEqual(answer["filters_applied"]["price_max"], 0)
            self.assertFalse(answer["model_used"])
            self.assertTrue(answer["filters_applied"]["family_only"])
            self.assertEqual(len(answer["events"]), 1)
            self.assertIsNone((await client.get("/api/auth/me")).json())
            self.assertEqual((await client.post("/api/auth/telegram", json={})).status_code, 401)
            payload = {"id": 123, "auth_date": int(time.time()), "first_name": "Тест"}
            check = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
            key = hashlib.sha256(b"fixture-token").digest()
            payload["hash"] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
            login = await client.post("/api/auth/telegram", json=payload)
            login.raise_for_status()
            self.assertIn("HttpOnly", login.headers["set-cookie"])
            self.assertEqual((await client.get("/api/auth/me")).json(), {"name": "Тест"})
            self.assertEqual((await client.post("/api/auth/logout")).status_code, 200)
            self.assertIsNone((await client.get("/api/auth/me")).json())


if __name__ == "__main__":
    unittest.main(verbosity=2)
