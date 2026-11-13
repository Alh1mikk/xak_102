from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime
from uuid import UUID
from app import models, schemas

# ---------- Источники ----------
async def get_or_create_source(db: AsyncSession, name: str, base_url: str) -> models.Source:
    result = await db.execute(select(models.Source).where(models.Source.base_url == base_url))
    source = result.scalar_one_or_none()
    if source:
        return source
    source = models.Source(name=name, base_url=base_url, is_active=True)
    db.add(source)
    await db.flush()  # чтобы получить id
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
    day_start = data.start_at.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start.replace(hour=23, minute=59, second=59)
    similar_q = select(models.Event).where(
        func.lower(models.Event.title) == data.title.lower(),
        models.Event.start_at >= day_start,
        models.Event.start_at <= day_end,
    )
    if data.address:
        similar_q = similar_q.where(models.Event.address == data.address)
    similar = (await db.execute(similar_q)).scalar_one_or_none()

    if similar:
        event = similar
        created = False
    else:
        event = models.Event(
            title=data.title,
            description=data.description,
            start_at=data.start_at,
            end_at=data.end_at,
            price_min=data.price_min,
            price_max=data.price_max,
            age_limit=data.age_limit,
            image_url=data.image_url,
            address=data.address,
            organizer=data.organizer,
            status=data.status or "published",
        )
        db.add(event)
        await db.flush()
        created = True

    # 3. Создаем связь event_sources
    link = models.EventSource(
        event_id=event.id,
        source_id=data.source_id,
        external_id=data.external_id,
        source_url=data.source_url,
        raw_data=data.raw_data,
        last_seen_at=datetime.utcnow(),
    )
    db.add(link)
    await db.flush()
    return event, created

# ---------- Получение списка событий с фильтрами ----------
async def get_events(db: AsyncSession, f: schemas.EventFilter, limit: int = 50, offset: int = 0):
    q = select(models.Event).options(
        selectinload(models.Event.city),
        selectinload(models.Event.category),
    )

    if f.city_id:
        q = q.where(models.Event.city_id == f.city_id)
    if f.category_id:
        q = q.where(models.Event.category_id == f.category_id)
    if f.date_from:
        q = q.where(models.Event.start_at >= f.date_from)
    if f.date_to:
        q = q.where(models.Event.start_at <= f.date_to)
    if f.price_max is not None:
        # Событие подходит, если его минимальная цена <= фильтра (или цена не указана)
        q = q.where(or_(models.Event.price_min.is_(None), models.Event.price_min <= f.price_max))
    if f.age_max is not None:
        q = q.where(or_(models.Event.age_limit.is_(None), models.Event.age_limit <= f.age_max))
    if f.q:
        q = q.where(models.Event.title.ilike(f"%{f.q}%"))

    q = q.order_by(models.Event.start_at).limit(limit).offset(offset)
    return (await db.execute(q)).scalars().all()