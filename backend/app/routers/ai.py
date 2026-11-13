# app/routers/ai.py (MVP-версия)
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/ai", tags=["ai"])

class QueryIn(BaseModel):
    text: str

@router.post("/search")
async def ai_search(payload: QueryIn, db: AsyncSession = Depends(get_db)):
    text = payload.text.lower()
    today = datetime.utcnow()

    # 1. "в субботу" → найти ближайшую субботу
    date_from = date_to = None
    if "суббот" in text:
        # weekday(): Monday=0, Saturday=5
        days_ahead = (5 - today.weekday()) % 7 or 7
        sat = (today + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0)
        date_from = sat
        date_to = sat.replace(hour=23, minute=59, second=59)

    # 2. "до 1000 рублей"
    import re
    price_max = None
    m = re.search(r"до\s+(\d+)", text)
    if m:
        price_max = int(m.group(1))

    # 3. "с ребёнком"
    age_max = None
    if "ребен" in text or "ребён" in text:
        age_max = 12  # по умолчанию до 12 лет

    # 4. Город
    city_id = None
    if "уфа" in text:
        # поиск города по имени
        from sqlalchemy import select
        from app import models
        r = await db.execute(select(models.City).where(models.City.name.ilike("%уфа%")))
        c = r.scalar_one_or_none()
        if c:
            city_id = c.id

    events = await crud.get_events(db, schemas.EventFilter(
        city_id=city_id, date_from=date_from, date_to=date_to,
        price_max=price_max, age_max=age_max,
    ), limit=5)

    # Объяснение подборки
    reasons = []
    if date_from: reasons.append("на ближайшую субботу")
    if price_max: reasons.append(f"с ценой до {price_max} ₽")
    if age_max: reasons.append("подходит для похода с ребёнком")

    return {
        "query": payload.text,
        "filters_applied": {
            "date_from": date_from, "date_to": date_to,
            "price_max": price_max, "age_max": age_max,
        },
        "explanation": "Подобрал события " + ", ".join(reasons) if reasons else "Показал все ближайшие события",
        "events": [schemas.EventOut.model_validate(e) for e in events],
    }