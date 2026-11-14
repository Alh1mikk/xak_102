import asyncio
import logging

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Event, DocumentChunk
from app.embedding import get_embeddings_batch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reindex")


async def reindex_events():
    async with AsyncSessionLocal() as db:
        # 1. Удаляем старые чанки
        await db.execute(DocumentChunk.__table__.delete())
        await db.commit()

        # 2. Берем все события
        result = await db.execute(select(Event))
        events = result.scalars().all()
        logger.info(f"Найдено событий для индексации: {len(events)}")

        if not events:
            return

        # 3. Формируем тексты для эмбеддинга
        texts = []
        for event in events:
            parts = [event.title]
            if event.description:
                parts.append(event.description)
            if event.address:
                parts.append(f"Адрес: {event.address}")
            if event.price_min is not None:
                parts.append(f"Цена: от {event.price_min} руб.")
            texts.append(". ".join(parts))

        # 4. Получаем эмбеддинги
        logger.info("Генерируем эмбеддинги (это может занять пару минут)...")
        embeddings = await get_embeddings_batch(texts)

        # 5. Сохраняем в document_chunks
        for event, content, emb in zip(events, texts, embeddings):
            chunk = DocumentChunk(
                source_type="event",
                source_id=event.id,
                content=content,
                embedding=emb,
                meta={"title": event.title, "address": event.address}
            )
            db.add(chunk)

        await db.commit()
        logger.info(f"Готово. Проиндексировано {len(events)} событий.")


if __name__ == "__main__":
    asyncio.run(reindex_events())