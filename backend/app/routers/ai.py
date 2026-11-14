from typing import Literal
import json
import logging
import os
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, models, schemas
from app.database import get_db

router = APIRouter(prefix="/ai", tags=["ai"])
ZONE = ZoneInfo("Asia/Yekaterinburg")


class QueryIn(BaseModel):
    preset: Literal["family", "friends", "free"] | None = None
    previous_text: str | None = Field(default=None, max_length=500)
    text: str = Field(min_length=1, max_length=500)


class SearchIntent(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    budget: int | None = Field(default=None, ge=0)
    age: int | None = Field(default=None, ge=0, le=120)
    city: str | None = None
    category: str | None = None


async def interpret(query: str, today: date, cities: dict, categories: dict) -> SearchIntent:
    normalized = query.lower().replace("ё", "е")
    intent = SearchIntent()

    # 1. Распознавание конкретной даты (16.11)
    explicit_date = re.search(r"\b(\d{1,2})[./](\d{1,2})\b", normalized)
    if explicit_date:
        day, month = int(explicit_date[1]), int(explicit_date[2])
        try:
            d = date(today.year, month, day)
            if d < today:
                d = date(today.year + 1, month, day)
            intent.date_from = intent.date_to = d
        except ValueError:
            pass

    # 2. Относительные даты
    if not intent.date_from:
        for pattern, offset in (
            ("сегодня", 0), ("завтра", 1), ("суббот", (5 - today.weekday()) % 7),
        ):
            if pattern in normalized:
                intent.date_from = intent.date_to = today + timedelta(days=offset)
                break

    # 3. Возраст (жестко)
    user_age = re.search(r"мне\s+(\d{1,2})\b", normalized)
    if user_age:
        intent.age = int(user_age[1])
    else:
        child_age = re.search(r"\b(\d{1,2})\s*(?:лет|года|год)\b", normalized)
        if child_age:
            intent.age = int(child_age[1])
        elif any(w in normalized for w in ("ребен", "детьми", "семейн")):
            intent.age = 6

    # 4. Бюджет
    if "бесплатн" in normalized:
        intent.budget = 0

    return intent


@router.post("/search")
async def ai_search(payload: QueryIn, db: AsyncSession = Depends(get_db)):
    now = datetime.now(ZONE)
    today = now.date()
    cities = {city.name: city.id for city in await db.scalars(select(models.City))}
    categories = {category.slug: category for category in await db.scalars(select(models.Category))}
    
    # 1. ПАРСЕР: получаем точные фильтры
    if payload.preset:
        intent = SearchIntent(age=6 if payload.preset == "family" else None)
    else:
        intent = await interpret(payload.text, today, cities, categories)

    # 2. БАЗА: достаем события строго по фильтрам
    start = datetime.combine(intent.date_from, time.min, ZONE) if intent.date_from else now
    end = datetime.combine(intent.date_to, time.max, ZONE) if intent.date_to else None
    category = categories.get(intent.category)

    filters = schemas.EventFilter(
        date_from=max(start, now), date_to=end, 
        price_max=intent.budget, age_max=intent.age,
        city_id=cities.get(intent.city), category_id=category.id if category else None
    )
    events = await crud.get_events(filters, limit=5)

    # 3. НЕЙРОСЕТЬ: генерируем красивый ответ на основе найденных событий
    from app.routers.rag import ask_roobert
    
    if not events:
        explanation = "К сожалению, по вашему запросу ничего не нашлось. Попробуйте изменить даты или возраст."
    else:
        context = [
            f"{e.title} (Дата: {e.start_at.strftime('%d.%m')}, Адрес: {e.address or 'не указан'}, Цена: {e.price_min or 0} руб.)" 
            for e in events
        ]
        # Модель напишет текст, но НЕ будет выбирать события (они уже выбраны)
        explanation = await ask_roobert(payload.text, context)

    return {
        "query": payload.text,
        "explanation": explanation,  # <--- Это пойдет в сайт/бота
        "events": events,            # <--- Это пойдет в карточки
        "model_used": True,
        "model_ranked": True,
    }