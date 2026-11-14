import logging

from sqlalchemy import select

from app import models
from app.database import AsyncSessionLocal
from app.vector import index_chunks

logger = logging.getLogger(__name__)


async def index_events() -> int:
    """Проиндексировать все опубликованные события в векторную БД."""
    async with AsyncSessionLocal.begin() as db:
        result = await db.execute(
            select(models.Event).where(models.Event.status == "published")
        )
        events = result.scalars().all()

    chunks = []
    for event in events:
        parts = [f"Название: {event.title}"]
        if event.description:
            parts.append(f"Описание: {event.description}")
        if event.address:
            parts.append(f"Адрес: {event.address}")
        if event.city:
            parts.append(f"Город: {event.city.name}")
        if event.category:
            parts.append(f"Категория: {event.category.name}")
        if event.price_min is not None:
            parts.append(f"Цена: от {event.price_min} ₽")
        if event.age_limit is not None:
            parts.append(f"Возрастная маркировка: {event.age_limit}+")

        content = "\n".join(parts)
        chunks.append(
            {
                "source_type": "event",
                "source_id": event.id,
                "content": content,
                "metadata": {
                    "title": event.title,
                    "city": event.city.name if event.city else None,
                    "category": event.category.name if event.category else None,
                    "start_at": event.start_at.isoformat() if event.start_at else None,
                    "price_min": event.price_min,
                    "age_limit": event.age_limit,
                },
            }
        )

    if not chunks:
        logger.info("Нет событий для индексации")
        return 0

    async with AsyncSessionLocal.begin() as db:
        # Очищаем старые чанки событий перед переиндексацией
        await db.execute(
            models.DocumentChunk.__table__.delete().where(
                models.DocumentChunk.source_type == "event"
            )
        )
        count = await index_chunks(db, chunks)
    logger.info("Проиндексировано событий: %d", count)
    return count


async def index_knowledge_base() -> int:
    """Проиндексировать текстовые файлы из папки knowledge_base."""
    from pathlib import Path

    kb_dir = Path(__file__).resolve().parent / "knowledge_base"
    if not kb_dir.exists():
        logger.info("Папка knowledge_base не найдена, пропускаем")
        return 0

    chunks = []
    for filepath in sorted(kb_dir.glob("*.txt")):
        content = filepath.read_text(encoding="utf-8").strip()
        if not content:
            continue
        chunks.append(
            {
                "source_type": "kb",
                "source_id": None,
                "content": content,
                "metadata": {"file": filepath.name},
            }
        )

    if not chunks:
        return 0

    async with AsyncSessionLocal.begin() as db:
        await db.execute(
            models.DocumentChunk.__table__.delete().where(
                models.DocumentChunk.source_type == "kb"
            )
        )
        count = await index_chunks(db, chunks)
    logger.info("Проиндексировано документов базы знаний: %d", count)
    return count


async def reindex_all() -> dict:
    """Полная переиндексация событий и базы знаний."""
    events_count = await index_events()
    kb_count = await index_knowledge_base()
    return {"events": events_count, "knowledge_base": kb_count}