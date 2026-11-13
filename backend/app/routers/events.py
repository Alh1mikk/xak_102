from fastapi import APIRouter, Query
from datetime import datetime
from uuid import UUID
from typing import Optional
from app import crud, schemas

router = APIRouter(prefix="/events", tags=["events"])

@router.get("/", response_model=list[schemas.EventOut])
async def list_events(
    city_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    price_max: Optional[int] = None,
    age_max: Optional[int] = None,
    q: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = schemas.EventFilter(
        city_id=city_id, category_id=category_id,
        date_from=date_from, date_to=date_to,
        price_max=price_max, age_max=age_max, q=q,
    )
    return await crud.get_events(filters, limit=limit, offset=offset)