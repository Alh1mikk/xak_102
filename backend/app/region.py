import json
from pathlib import Path

from sqlalchemy import select, text

from app.models import EventSource

# OpenStreetMap contributors, relation 77677, ODbL.
RINGS = json.loads((Path(__file__).parent / "data/bashkortostan.geojson").read_text())["coordinates"]


def inside_ring(x, y, ring):
    inside = False
    for (ax, ay), (bx, by) in zip(ring, ring[1:]):
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
    return inside


def verified_location(raw):
    venue = raw.get("venue") or {}
    try:
        lat = float(venue["latitude"])
        lon = float(venue["longitude"])
    except (KeyError, TypeError, ValueError):
        return False
    return inside_ring(lon, lat, RINGS[0]) and not any(
        inside_ring(lon, lat, hole) for hole in RINGS[1:]
    )


async def refresh_verified_sources(db):
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS verified_regional_sources (
            source_link_id uuid PRIMARY KEY REFERENCES event_sources(id) ON DELETE CASCADE,
            raw_data jsonb NOT NULL
        )
    """))
    await db.execute(text("SELECT pg_advisory_xact_lock(102)"))
    await db.execute(text("DELETE FROM verified_regional_sources"))
    rows = await db.execute(select(EventSource.id, EventSource.raw_data).where(EventSource.raw_data.is_not(None)))
    approved = [{"id": row.id, "raw": json.dumps(row.raw_data)}
                for row in rows if verified_location(row.raw_data)]
    if approved:
        await db.execute(text("""
            INSERT INTO verified_regional_sources (source_link_id, raw_data)
            VALUES (:id, CAST(:raw AS jsonb))
        """), approved)
