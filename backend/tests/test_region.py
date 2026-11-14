import pytest

from app.region import inside_ring, verified_location, refresh_verified_sources


class TestInsideRing:
    def test_point_inside_simple_ring(self):
        ring = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        assert inside_ring(5, 5, ring) is True

    def test_point_outside_simple_ring(self):
        ring = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        assert inside_ring(15, 15, ring) is False

    def test_point_on_edge(self):
        ring = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        assert inside_ring(5, 0, ring) is False


class TestVerifiedLocation:
    def test_valid_in_region(self):
        raw = {"venue": {"latitude": 54.73, "longitude": 55.96}}
        assert verified_location(raw) is True

    def test_missing_latitude(self):
        raw = {"venue": {"longitude": 55.96}}
        assert verified_location(raw) is False

    def test_invalid_latitude(self):
        raw = {"venue": {"latitude": "abc", "longitude": 55.96}}
        assert verified_location(raw) is False

    def test_outside_region(self):
        raw = {"venue": {"latitude": 55.65, "longitude": 37.41}}  # Москва
        assert verified_location(raw) is False


@pytest.mark.asyncio
class TestRefreshVerifiedSources:
    @pytest.fixture
    async def db(self):
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal.begin() as session:
            yield session

    async def test_creates_table_and_inserts_approved(self, db):
        source = models.Source(name="X", base_url="https://x.test")
        db.add(source)
        await db.flush()
        approved = {
            "source_id": source.id,
            "raw_data": {"venue": {"latitude": 54.73, "longitude": 55.96}},
        }
        await db.execute(
            models.EventSource.insert().values(
                event_id=uuid4(), source_id=source.id, external_id="ev",
                source_url="https://example.org", raw_data=approved["raw_data"],
            )
        )
        await db.commit()

        await refresh_verified_sources(db)

        from app.models import verified_regional_sources
        count = await db.scalar(models.verified_regional_sources.select())
        assert count == 1
