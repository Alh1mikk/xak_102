import asyncio
from datetime import datetime, timedelta
from app.database import AsyncSessionLocal
from app import crud, schemas

async def main():
    async with AsyncSessionLocal() as db:
        # 1. Создаем источник
        src = await crud.get_or_create_source(db, "Театр", "https://example.com")
        await db.commit()
        print("Source:", src.id)

        # 2. Вставляем событие
        ev, created = await crud.upsert_event(db, schemas.EventCreate(
            title="Щелкунчик",
            description="Балет",
            start_at=datetime.utcnow() + timedelta(days=3),
            price_min=500, price_max=1500,
            age_limit=6,
            address="Уфа, пр. Октября 1",
            source_id=src.id,
            external_id="evt-001",
            source_url="https://example.com/1",
        ))
        await db.commit()
        print("Event:", ev.id, "created:", created)

        # 3. Пробуем вставить ДУБЛЬ — должно вернуться created=False
        ev2, created2 = await crud.upsert_event(db, schemas.EventCreate(
            title="Щелкунчик",
            start_at=ev.start_at,
            address="Уфа, пр. Октября 1",
            source_id=src.id,
            external_id="evt-001",
        ))
        await db.commit()
        print("Dup event:", ev2.id, "created:", created2)  # должно быть False

asyncio.run(main())