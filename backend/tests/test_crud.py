import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import crud, models
from app.schemas import EventCreate


@pytest.mark.asyncio
class TestGetOrCreateSource:
    async def test_creates_source(self, db):
        source = await crud.get_or_create_source(db, "Бюро Культуры", "https://ufa.burocultura.ru/api/events")
        assert source.id is not None
        assert source.name == "Бюро Культуры"
        assert source.base_url == "https://ufa.burocultura.ru/api/events"
        assert source.is_active is True

    async def test_returns_existing_source(self, db):
        first = await crud.get_or_create_source(db, "Театр", "https://example.org")
        second = await crud.get_or_create_source(db, "Театр", "https://example.org")
        assert first is second


@pytest.mark.asyncio
class TestUpsertEvent:
    @pytest.fixture
    async def source(self, db):
        source = models.Source(name="Источник", base_url="https://example.org", is_active=True)
        db.add(source)
        await db.flush()
        return source

    @pytest.fixture
    def event_create(self, source):
        return EventCreate(
            title="Щелкунчик",
            description="Балет",
            start_at=datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc),
            price_min=500,
            price_max=1500,
            age_limit=6,
            address="Уфа, пр. Октября 1",
            source_id=source.id,
            external_id="evt-001",
            source_url="https://example.org/1",
            raw_data={},
        )

    async def test_creates_event_and_link(self, db, event_create):
        event, created = await crud.upsert_event(db, event_create)
        assert created is True
        assert event.title == "Щелкунчик"
        assert event.price_min == 500
        assert event.status == "published"

        link = await db.scalar(models.EventSource.select().where(models.EventSource.event_id == event.id))
        assert link is not None
        assert link.source_id == event_create.source_id
        assert link.external_id == "evt-001"
        assert link.source_url == "https://example.org/1"
        assert link.raw_data == {}

    async def test_updates_existing_by_external_id(self, db, source, event_create):
        first, _ = await crud.upsert_event(db, event_create)
        assert first is not None

        updated, created = await crud.upsert_event(
            db,
            event_create.model_copy(update={"external_id": "evt-001", "title": "Щелкунчик-2"}),
        )
        assert created is False
        event = await db.get(models.Event, updated.id)
        assert event.title == "Щелкунчик-2"

        link = await db.scalar(models.EventSource.select().where(models.EventSource.event_id == updated.id))
        assert link is not None
        assert link.source_url == "https://example.org/1"

    async def test_updates_event_preserving_external_id(self, db, source, event_create):
        first, _ = await crud.upsert_event(db, event_create)
        updated, created = await crud.upsert_event(
            db,
            event_create.model_copy(update={"title": "Щелкунчик-2", "price_min": 700}),
        )
        assert created is False
        assert updated.title == "Щелкунчик-2"
        assert updated.price_min == 700

        link = await db.scalar(models.EventSource.select().where(models.EventSource.event_id == updated.id))
        assert link is not None
        assert link.source_url == "https://example.org/1"
        assert link.last_seen_at is not None

    async def test_creates_event_without_external_id(self, db, source):
        data = EventCreate(
            title="Вимбург",
            source_id=source.id,
            external_id=None,
            start_at=datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc),
            price_min=200, price_max=400, age_limit=None, address="Уфа",
            source_url="https://example.org/1",
        )
        event, created = await crud.upsert_event(db, data)
        assert created is True
        assert event.title == "Вимбург"
        link = await db.scalar(models.EventSource.select().where(models.EventSource.event_id == event.id))
        assert link is not None

    async def test_updates_event_by_city_and_address(self, db, source):
        city = models.City(name="Уфа")
        cat = models.Category(name="Театр", slug="theater")
        db.add_all([city, cat])
        await db.flush()

        first = models.Event(
            title="Спектакль",
            description="Балет",
            start_at=datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc),
            price_min=500, price_max=1500, age_limit=6, address="Уфа, пр. Октября 1",
            city_id=city.id, category_id=cat.id, status="published",
        )
        db.add(first)
        await db.flush()

        updated, created = await crud.upsert_event(
            db,
            EventCreate(
                title="Спектакль",
                start_at=datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc),
                price_min=600, price_max=1600, age_limit=6, address="Уфа, пр. Октября 1",
                source_id=source.id, external_id="dup", source_url="https://example.org/2",
            ),
        )
        assert created is False
        assert updated.title == "Спектакль"
        assert updated.price_min == 600

@pytest.mark.asyncio
class TestGetEvents:
    @pytest.fixture
    async def source(self, db):
        source = models.Source(name="Источник", base_url="https://example.org", is_active=True)
        db.add(source)
        await db.flush()
        return source

    @pytest.fixture
    async def cities(self, db):
        city1 = models.City(name="Уфа")
        city2 = models.City(name="Казань")
        db.add_all([city1, city2])
        await db.flush()
        return {city1.name: city1, city2.name: city2}

    @pytest.fixture
    async def categories(self, db):
        cat1 = models.Category(name="Театр", slug="theater")
        cat2 = models.Category(name="Концерт", slug="concert")
        db.add_all([cat1, cat2])
        await db.flush()
        return {cat1.slug: cat1, cat2.slug: cat2}

    @pytest.fixture
    async def events(self, db, source, cities, categories):
        now = datetime.now(timezone.utc)
        payloads = [
            dict(title="A", start_at=now + timedelta(days=1), city_id=cities["Уфа"].id,
                 category_id=categories["theater"].id, price_min=0, price_max=0, age_limit=6),
            dict(title="B", start_at=now + timedelta(days=2), city_id=cities["Казань"].id,
                 category_id=categories["concert"].id, price_min=500, price_max=1000, age_limit=None),
            dict(title="C", start_at=now - timedelta(days=1), city_id=cities["Уфа"].id,
                 category_id=categories["theater"].id, price_min=100, price_max=200, age_limit=None),
        ]
        created = []
        for payload in payloads:
            data = EventCreate(title=payload["title"], start_at=payload["start_at"],
                               city_id=payload["city_id"], category_id=payload["category_id"],
                               price_min=payload["price_min"], price_max=payload["price_max"],
                               age_limit=payload["age_limit"], address="Уфа, пр. Октября 1",
                               source_id=source.id, external_id=payload["title"], source_url="https://example.org/1")
            event, _ = await crud.upsert_event(db, data)
            created.append(event)
        await db.flush()
        return created

    async def test_filters_by_city_and_category(self, db, events, cities, categories):
        results = await crud.get_events(
            models.EventFilter(city_id=cities["Уфа"].id, category_id=categories["theater"].id),
            limit=50, offset=0,
        )
        assert [e.title for e in results] == ["A"]

    async def test_filters_by_date_range(self, db, events):
        results = await crud.get_events(
            models.EventFilter(date_from=events[0].start_at, date_to=events[0].start_at + timedelta(days=1)),
            limit=50, offset=0,
        )
        assert [e.title for e in results] == ["A"]

    async def test_filters_by_price_and_age(self, db, events):
        results = await crud.get_events(
            models.EventFilter(price_max=0, age_max=6),
            limit=50, offset=0,
        )
        assert [e.title for e in results] == ["A"]

    async def test_limit_and_offset(self, db, events):
        results = await crud.get_events(models.EventFilter(), limit=1, offset=1)
        assert [e.title for e in results] == ["B"]


@pytest.mark.asyncio
class TestSourceHelpers:
    async def test_deactivate_sources(self, db):
        source = models.Source(name="X", base_url="https://x.test", is_active=True)
        db.add(source)
        await db.flush()
        await crud.deactivate_sources(db, [source.id])
        refreshed = await db.scalar(models.Source.select().where(models.Source.id == source.id))
        assert refreshed.is_active is False

    async def test_get_active_sources(self, db):
        active = models.Source(name="Active", base_url="https://active.test", is_active=True)
        inactive = models.Source(name="Inactive", base_url="https://inactive.test", is_active=False)
        db.add_all([active, inactive])
        await db.flush()
        result = await crud.get_active_sources(db)
        assert len(result) == 1
        assert result[0].id == active.id

    async def test_get_source_by_base_url(self, db):
        source = models.Source(name="X", base_url="https://x.test", is_active=True)
        db.add(source)
        await db.flush()
        found = await crud.get_source_by_base_url(db, "https://x.test")
        assert found is not None
        assert found.name == "X"


@pytest.mark.asyncio
class TestImportLog:
    async def test_insert_import_log(self, db):
        source = models.Source(name="X", base_url="https://x.test", is_active=True)
        db.add(source)
        await db.flush()
        log = await crud.insert_import_log(db, source.id, 10, "ok", {"err": 1})
        assert log.records_found == 10
        assert log.status == "ok"
        assert log.records_created == 10
        assert log.records_updated == 10
        assert log.errors == {"err": 1}

