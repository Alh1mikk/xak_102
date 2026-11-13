from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Category, City
from datetime import datetime
from zoneinfo import ZoneInfo
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
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    zone = ZoneInfo("Asia/Yekaterinburg")
    if date_from and date_from.tzinfo is None:
        date_from = date_from.replace(tzinfo=zone)
    if date_to and date_to.tzinfo is None:
        date_to = date_to.replace(tzinfo=zone)
    filters = schemas.EventFilter(
        city_id=city_id, category_id=category_id,
        date_from=date_from, date_to=date_to,
        price_max=price_max, age_max=age_max, q=q,
    )
    return await crud.get_events(filters, limit=limit, offset=offset)

@router.get("/cities", response_model=list[schemas.CityOut])
async def list_cities(db: AsyncSession = Depends(get_db)):
    return list(await db.scalars(select(City).order_by(City.name)))


@router.get("/categories", response_model=list[schemas.CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    return list(await db.scalars(select(Category).order_by(Category.name)))
