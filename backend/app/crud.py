import asyncpg
import os
import re
from dotenv import load_dotenv

from sqlalchemy import select, or_, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime
import uuid
from uuid import UUID
from app import models, schemas

load_dotenv()

_asyncpg_pool = None


async def _get_asyncpg_pool():
    global _asyncpg_pool
    if _asyncpg_pool is None:
        dsn = os.getenv("DATABASE_URL")
        if dsn and dsn.startswith("postgresql+asyncpg://"):
            dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
        # min_size=0 — не соединяться при создании пула,
        # коннект устанавливается только при первом pool.acquire()
        _asyncpg_pool = await asyncpg.create_pool(
            dsn,
            ssl="require",
            statement_cache_size=0,
            min_size=0,
            max_size=5,
        )
    return _asyncpg_pool


# ---------- Источники ----------
async def get_or_create_source(db: AsyncSession, name: str, base_url: str) -> models.Source:
    from sqlalchemy import select
    # 1. Ищем источник
    result = await db.execute(select(models.Source).where(models.Source.base_url == base_url))
    source = result.scalar_one_or_none()

    # 2. Если нашли — возвращаем
    if source:
        return source

    # 3. Если нет — создаем
    import uuid
    source = models.Source(
        id=uuid.uuid4(),  # Генерируем ID на стороне Python, чтобы не ждать БД
        name=name,
        base_url=base_url,
        is_active=True
    )
    db.add(source)

    try:
        await db.flush()
    except Exception as e:
        print(f"❌ Ошибка при создании источника: {e}")
        await db.rollback()
        raise

    return source


# ---------- Upsert события ----------
async def upsert_event(db: AsyncSession, data: schemas.EventCreate) -> tuple[models.Event, bool]:
    """
    Возвращает (event, created: bool).
    Логика дедупликации:
      1. Ищем в event_sources по (source_id, external_id).
      2. Если нашли — обновляем event + last_seen_at.
      3. Если нет — ищем «похожее» событие (title + start_at в том же дне + address).
         - Если нашли — создаем только связь event_sources.
         - Если нет — создаем event + связь.
    """
    # 1. Проверка связки source/external_id
    if data.external_id:
        q = select(models.EventSource).where(
            models.EventSource.source_id == data.source_id,
            models.EventSource.external_id == data.external_id,
        )
        existing_link = (await db.execute(q)).scalar_one_or_none()
        if existing_link:
            event = await db.get(models.Event, existing_link.event_id)
            # обновляем изменяемые поля
            for field in ("title", "description", "price_min", "price_max",
                          "age_limit", "image_url", "start_at", "end_at", "address"):
                val = getattr(data, field, None)
                if val is not None:
                    setattr(event, field, val)
            existing_link.last_seen_at = datetime.utcnow()
            await db.flush()
            return event, False

    # 2. Поиск «похожего» события (дедупликация между источниками)
    # Условие: тот же день, тот же title (без учета регистра), адрес совпадает
    from sqlalchemy import func
    day_start = data.start_at.replace(hour=0, minute=0, second=0)

    similar_q = (
        select(models.Event)
        .where(
            func.date(data.start_at) == func.date(day_start),
            func.lower(models.Event.title) == func.lower(data.title),
            models.Event.address == data.address,
        )
    )
    existing = (await db.execute(similar_q)).scalar_one_or_none()
    if existing and data.external_id:
        # уже есть похожее — создаем связь источника
        link = models.EventSource(
            event_id=existing.id,
            source_id=data.source_id,
            source_url=data.source_url or "",
            last_seen_at=datetime.utcnow(),
            external_id=data.external_id,
        )
        db.add(link)
        await db.flush()
        return existing, False

    # 3. Создаем новое событие
    event = models.Event(
        title=data.title,
        description=data.description,
        start_at=data.start_at,
        end_at=data.end_at,
        price_min=data.price_min,
        price_max=data.price_max,
        age_limit=data.age_limit,
        image_url=data.image_url,
        organizer=data.organizer,
        status="published",
    )
    db.add(event)
    await db.flush()

    if data.external_id:
        link = models.EventSource(
            event_id=event.id,
            source_id=data.source_id,
            source_url=data.source_url or "",
            last_seen_at=datetime.utcnow(),
            external_id=data.external_id,
        )
        db.add(link)

    await db.flush()

    if not data.external_id and data.title:
        # найти похожие уже существующие события
        similar = await db.execute(
            select(models.Event).where(
                func.lower(models.Event.title) == func.lower(data.title),
                func.date(models.Event.start_at) == func.date(data.start_at),
                models.Event.address == (data.address or ""),
            )
        )
        similar_events = similar.scalars().all()
        for se in similar_events:
            if se.id != event.id:
                link = models.EventSource(
                    event_id=se.id,
                    source_id=data.source_id,
                    source_url=data.source_url or "",
                    last_seen_at=datetime.utcnow(),
                    external_id=data.external_id or f"dup-{se.id}-{data.title}",
                )
                db.add(link)

    await db.flush()
    return event, True


# ---------- Получение списка событий с фильтрами (чистый asyncpg) ----------
async def get_events(f: schemas.EventFilter, limit: int = 50, offset: int = 0):
    """
    Получение списка событий с фильтрами через чистый asyncpg (без SQLAlchemy ORM),
    чтобы обойти зависание SQLAlchemy + PgBouncer (Supabase).
    Возвращает список schemas.EventOut с вложенными city/category.
    """
    conditions: list[str] = []
    params: dict = {"limit": limit, "offset": offset}

    if f.city_id is not None:
        conditions.append("e.city_id = :city_id")
        params["city_id"] = f.city_id
    if f.category_id is not None:
        conditions.append("e.category_id = :category_id")
        params["category_id"] = f.category_id
    if f.date_from is not None:
        conditions.append("e.start_at >= :date_from")
        params["date_from"] = f.date_from
    if f.date_to is not None:
        conditions.append("e.start_at <= :date_to")
        params["date_to"] = f.date_to
    if f.price_max is not None:
        conditions.append("(e.price_min IS NULL OR e.price_min <= :price_max)")
        params["price_max"] = f.price_max
    if f.age_max is not None:
        conditions.append("(e.age_limit IS NULL OR e.age_limit <= :age_max)")
        params["age_max"] = f.age_max
    if f.q:
        conditions.append("e.title ILIKE :q")
        params["q"] = f"%{f.q}%"

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    sql = text(
        f"""
        SELECT
            e.id AS id,
            e.title AS title,
            e.description AS description,
            e.address AS address,
            e.start_at AS start_at,
            e.end_at AS end_at,
            e.price_min AS price_min,
            e.price_max AS price_max,
            e.age_limit AS age_limit,
            e.image_url AS image_url,
            e.organizer AS organizer,
            e.status AS status,
            e.city_id AS city_id,
            e.category_id AS category_id,
            c.id AS _city_id,
            c.name AS _city_name,
            c.district AS _city_district,
            cat.id AS _category_id,
            cat.name AS _category_name,
            cat.slug AS _category_slug
        FROM events AS e
        LEFT JOIN cities AS c ON c.id = e.city_id
        LEFT JOIN categories AS cat ON cat.id = e.category_id
        WHERE {where_clause}
        ORDER BY e.start_at
        LIMIT :limit
        OFFSET :offset
        """
    )

    # asyncpg поддерживает только позиционные параметры ($1, $2...),
    # заменяем :param на $1, $2... и вызываем raw asyncpg fetch.
    query_str = str(sql)
    param_names = re.findall(r":(\w+)", query_str)

    counter = [0]

    def replace_param(m):
        counter[0] += 1
        return f"${counter[0]}"

    query_str = re.sub(r":(\w+)", replace_param, query_str)
    args = [params[name] for name in param_names]

    # Чистый asyncpg пул — без SQLAlchemy ORM execution.
    pool = await _get_asyncpg_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch(query_str, *args)

    items = []
    for record in records:
        city = (
            {
                "id": record["_city_id"],
                "name": record["_city_name"],
                "district": record["_city_district"],
            }
            if record["_city_id"] is not None
            else None
        )
        category = (
            {
                "id": record["_category_id"],
                "name": record["_category_name"],
                "slug": record["_category_slug"],
            }
            if record["_category_id"] is not None
            else None
        )
        items.append(
            {
                "id": record["id"],
                "title": record["title"],
                "description": record["description"],
                "address": record["address"],
                "start_at": record["start_at"],
                "end_at": record["end_at"],
                "price_min": record["price_min"],
                "price_max": record["price_max"],
                "age_limit": record["age_limit"],
                "image_url": record["image_url"],
                "organizer": record["organizer"],
                "status": record["status"],
                "city": city,
                "category": category,
            }
        )

    return [schemas.EventOut.model_validate(item) for item in items]


# ---------- Вставка/обновление импорта ----------
async def insert_import_log(db: AsyncSession, source_id: uuid.UUID, records: int, status: str, errors: dict | None = None) -> models.ImportLog:
    """Создание записи лога импорта."""
    importlog = models.ImportLog(
        source_id=source_id,
        status=status,
        records_found=records,
        records_created=records,
        records_updated=records,
        errors=errors,
    )
    db.add(importlog)
    await db.flush()
    return importlog


# ---------- Вспомогательные функции для источников ----------
async def deactivate_sources(db: AsyncSession, source_ids: list[uuid.UUID]) -> None:
    """Помечает источники как неактивные."""
    await db.execute(
        models.Source.update()
        .where(models.Source.id.in_(source_ids))
        .values(is_active=False)
    )


async def get_active_sources(db: AsyncSession) -> list[models.Source]:
    """Возвращает все активные источники."""
    result = await db.execute(
        select(models.Source).where(models.Source.is_active == True)  # noqa: E712
    )
    return result.scalars().all()


async def get_source_by_base_url(db: AsyncSession, base_url: str) -> models.Source | None:
    """Возвращает активный источник по базовому URL."""
    result = await db.execute(
        select(models.Source).where(
            models.Source.base_url == base_url,
            models.Source.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()
