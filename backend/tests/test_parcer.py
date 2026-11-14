from datetime import datetime, timezone

import pytest

from app.parcer import extract_event_fields, parse_price


class TestParsePrice:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, 0),
            ("120.5", 121),
            (("-3",), None),
            (None, None),
            ("", None),
            ("?", None),
            (10.2, 11),
            ("0", 0),
        ],
    )
    def test_normalization(self, value, expected):
        assert parse_price(value) == expected


class TestExtractEventFields:
    def _base(self, **overrides):
        item = {
            "kassirNextShowAt": "2026-11-14T13:00:00Z",
            "ageRestriction": "6+",
            "isFree": False,
            "kassirShowsCard": [
                {"priceMax": "600", "priceMin": "400"},
                {"priceMax": "1000", "priceMin": "800"},
            ],
            "title": "  Концерт  ",
            "description": "  Байкал  ",
            "imageUrl": "https://example.org/poster.jpg",
            "slug": "slug-1",
            "id": 42,
        }
        item.update(overrides)
        return item

    def test_free_event(self):
        item = self._base(isFree=True, priceFrom="500", kassirShowsCard=[])
        result = extract_event_fields(item)
        assert result["price_min"] == 0
        assert result["price_max"] == 0

    def test_free_forces_zero(self):
        item = self._base(isFree=True, priceFrom="0")
        result = extract_event_fields(item)
        assert result["price_min"] == 0
        assert result["price_max"] == 0

    def test_min_from_price_from(self):
        item = self._base(isFree=False, kassirShowsCard=[], priceFrom="700")
        result = extract_event_fields(item)
        assert result["price_min"] == 700
        assert result["price_max"] == 700

    def test_max_from_shows(self):
        item = self._base(isFree=False, priceFrom="100", kassirShowsCard=[{"priceMax": "400", "priceMin": "300"}])
        result = extract_event_fields(item)
        assert result["price_min"] == 100
        assert result["price_max"] == 400

    def test_age_digits(self):
        item = self._base(ageRestriction="6+")
        result = extract_event_fields(item)
        assert result["age_limit"] == 6

    def test_age_with_letters(self):
        item = self._base(ageRestriction="12 лет")
        result = extract_event_fields(item)
        assert result["age_limit"] == 12

    def test_age_without_digits(self):
        item = self._base(ageRestriction="ревные")
        result = extract_event_fields(item)
        assert result["age_limit"] is None

    def test_start_at_from_kassirNextShowAt(self):
        item = self._base(kassirNextShowAt="2026-11-14T13:00:00Z")
        result = extract_event_fields(item)
        assert result["start_at"] == datetime(2026, 11, 14, 13, 0, tzinfo=timezone.utc)

    def test_start_at_from_dateStart(self):
        item = self._base(kassirNextShowAt=None, dateStart="2026-11-15T10:00:00+03:00")
        result = extract_event_fields(item)
        assert result["start_at"] == datetime(2026, 11, 15, 10, 0, tzinfo=timezone(timedelta(hours=3)))

    def test_start_at_now_when_absent(self):
        item = self._base(kassirNextShowAt=None, dateStart=None)
        result = extract_event_fields(item)
        assert result["start_at"] is not None

    def test_title_and_description_stripped(self):
        item = self._base(title="  Щелкунчик  ", description="  Балет  ")
        result = extract_event_fields(item)
        assert result["title"] == "Щелкунчик"
        assert result["description"] == "Балет"

    def test_external_id_from_slug(self):
        item = self._base(slug="abc-123")
        result = extract_event_fields(item)
        assert result["external_id"] == "abc-123"
        assert result["source_url"] == "https://burocultura.ruabc-123"

    def test_external_id_from_id(self):
        item = self._base(slug=None, id=99)
        result = extract_event_fields(item)
        assert result["external_id"] == "99"

    def test_empty_values(self):
        item = {}
        result = extract_event_fields(item)
        assert result["title"] == "Без названия"
        assert result["description"] == ""
        assert result["price_min"] is None
        assert result["price_max"] is None
        assert result["age_limit"] is None
