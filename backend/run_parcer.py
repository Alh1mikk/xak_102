import asyncio
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select, text

from app import crud, models, schemas
from app.database import AsyncSessionLocal
from app.region import refresh_verified_sources

SOURCE_URL = "https://ufa.burocultura.ru/api/events"
LOCAL_ZONE = ZoneInfo("Asia/Yekaterinburg")
CATEGORIES = {
    "concert": "Концерты", "theater": "Театр", "lecture": "Лекции",
    "children": "Детям", "museum_visit": "Музеи", "excursion": "Экскурсии",
}


def parse_price(value):
    try:
        price = math.ceil(float(value))
    except (ValueError, TypeError, OverflowError):
        return None
    return price if price >= 0 else None


def parse_date(value):
    if not value:
        return None
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return date if date.tzinfo else date.replace(tzinfo=LOCAL_ZONE)


async def fetch_events_data() -> list:
    """Получает свежий список событий с повторными попытками."""
    url = SOURCE_URL
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://ufa.burocultura.ru/api/events",
        "Origin": "https://ufa.burocultura.ru/api/events",
    }

    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        for attempt in range(1, 4):
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
                    raise ValueError("Ожидался список карточек")
                return data
            except (httpx.HTTPError, ValueError) as error:
                print(f"Бюро Культуры, попытка {attempt}: {error}")
                if attempt == 3:
                    raise
                await asyncio.sleep(5 * attempt)


async def parse_burocultura():
    data = await fetch_events_data()
    async with AsyncSessionLocal.begin() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(102)"))
        source = await crud.get_or_create_source(db, "Бюро Культуры", SOURCE_URL)
        cities = {city.name: city for city in await db.scalars(select(models.City))}
        categories = {category.slug: category for category in await db.scalars(select(models.Category))}
        created = updated = 0
        seen = set()
        for item in data:
            external_id = item.get("slug") or item.get("id")
            title = (item.get("title") or "").strip()
            if not external_id or not title or external_id in seen:
                continue
            try:
                start = parse_date(item.get("kassirNextShowAt") or item.get("dateStart"))
            except ValueError:
                continue
            if start is None:
                continue
            seen.add(external_id)

            city = None
            if item.get("cityId") == "ufa":
                city = cities.get("Уфа")
                if city is None:
                    city = cities["Уфа"] = models.City(name="Уфа")
                    db.add(city)
            slug = item.get("type")
            category = categories.get(slug)
            if category is None and slug in CATEGORIES:
                category = categories[slug] = models.Category(slug=slug, name=CATEGORIES[slug])
                db.add(category)
            await db.flush()

            venue = item.get("venue") or {}
            organizer = item.get("organizer") or {}
            matching_show = next(
                (show for show in item.get("kassirShowsCard") or []
                 if parse_date(show.get("dateStart")) == start),
                {},
            )
            price = parse_price(matching_show.get("priceMin"))
            if price is None:
                price = parse_price(item.get("priceFrom"))
            price_max = parse_price(matching_show.get("priceMax"))
            if item.get("isFree"):
                price = price_max = 0
            if price is not None and price_max is not None and price_max < price:
                price_max = None
            age = str(item.get("ageRestriction") or "").rstrip("+")
            if item.get("ageRestriction") == 0:
                age = "0"
            _, inserted = await crud.upsert_event(db, schemas.EventCreate(
                title=title, description=item.get("description"), start_at=start,
                price_min=price, price_max=price_max,
                age_limit=int(age) if age.isdecimal() else None,
                address=item.get("meetingPointAddress") or venue.get("address") or venue.get("name"),
                organizer=organizer.get("name"), image_url=item.get("imageUrl"),
                city_id=city.id if city else None, category_id=category.id if category else None,
                status="published" if item.get("status") == "published" and item.get("isVisible") is not False else "draft",
                source_id=source.id, external_id=str(external_id),
                source_url=f"https://ufa.burocultura.ru/events/{external_id}", raw_data=item,
            ))
            created += inserted
            updated += not inserted
        await refresh_verified_sources(db)
        print(f"Бюро Культуры: получено {len(data)}, добавлено {created}, обновлено {updated}")


if __name__ == "__main__":
    asyncio.run(parse_burocultura())
