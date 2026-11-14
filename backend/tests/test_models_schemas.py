import uuid
from datetime import datetime, timezone

import pytest

from app import models, schemas
from app.schemas import EventCreate, EventFilter, EventOut


class TestEventCreate:
    def test_base_fields_from_event(self):
        event = models.Event(
            id=uuid.uuid4(),
            title="Щелкунчик",
            description="Балет",
            start_at=datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc),
            price_min=500,
            price_max=1500,
            age_limit=6,
            image_url="https://example.org/poster.jpg",
            status="published",
            city_id=uuid.uuid4(),
            category_id=uuid.uuid4(),
        )
        data = schemas.EventCreate.model_validate(event)
        assert data.title == "Щелкунчик"
        assert data.price_min == 500
        assert data.price_max == 1500
        assert data.age_limit == 6
        assert data.status == "published"

    def test_from_dict(self):
        data = EventCreate(
            title="Концерт",
            start_at=datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc),
            source_id=uuid.uuid4(),
        )
        assert data.title == "Концерт"
        assert data.price_min is None
        assert data.price_max is None
        assert data.age_limit is None

    def test_event_out_from_event(self):
        event = models.Event(
            id=uuid.uuid4(),
            title="Концерт",
            description="Байкал",
            start_at=datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc),
            latitude=54.73,
            longitude=55.96,
            source_urls=["https://example.org/1"],
            status="published",
            city_id=uuid.uuid4(),
            category_id=uuid.uuid4(),
        )
        out = schemas.EventOut.model_validate(event)
        assert out.id is not None
        assert out.title == "Концерт"
        assert out.latitude == 54.73
        assert out.longitude == 55.96
        assert out.source_urls == ["https://example.org/1"]

    def test_event_filter_defaults(self):
        filters = EventFilter()
        assert filters.family_only is False
        assert filters.city_id is None
        assert filters.category_id is None
        assert filters.price_max is None
        assert filters.age_max is None
        assert filters.q is None
        assert filters.date_from is None
        assert filters.date_to is None

    def test_event_filter_from_dict(self):
        filters = EventFilter(
            city_id=uuid.uuid4(),
            price_max=1000,
            age_max=6,
            q="концерт",
            family_only=True,
        )
        assert filters.price_max == 1000
        assert filters.age_max == 6
        assert filters.q == "концерт"
        assert filters.family_only is True


class TestValidation:
    def test_event_create_missing_source_id(self):
        with pytest.raises(Exception):
            EventCreate(
                title="Концерт",
                source_id=None,
            )

    def test_event_filter_price_max_negative(self):
        with pytest.raises(Exception):
            EventFilter(price_max=-1)
