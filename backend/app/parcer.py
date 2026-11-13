import asyncio
import httpx
import asyncpg
import os
import json
import math
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


def parse_price(val):
    """Безопасный парсинг цены с сохранением нуля для бесплатных событий."""
    if val is None or val == "":
        return None
    try:
        return int(math.ceil(float(val)))
    except (ValueError, TypeError):
        return None


def extract_event_fields(item: dict) -> dict:
    """Извлекает и нормализует поля из JSON-объекта события."""
    date_str = item.get("kassirNextShowAt") or item.get("dateStart")
    if date_str:
        start_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    else:
        start_at = datetime.now(timezone.utc)

    age_str = item.get("ageRestriction")
    digits = "".join(filter(str.isdigit, str(age_str))) if age_str else ""
    age_limit = int(digits) if digits else None

    shows = item.get("kassirShowsCard") or []
    max_prices = [
        p for s in shows if (p := parse_price(s.get("priceMax"))) is not None
    ]
    min_prices = [
        p for s in shows if (p := parse_price(s.get("priceMin"))) is not None
    ]

    price_min = parse_price(item.get("priceFrom"))
    if price_min is None and min_prices:
        price_min = min(min_prices)

    if item.get("isFree") is True:
        price_min = 0
        price_max = 0
    else:
        price_max = max(max_prices) if max_prices else price_min

    title = (item.get("title") or "Без названия").strip()
    description = (item.get("description") or "").strip()
    image_url = (item.get("imageUrl") or "").strip()
    external_id = item.get("slug") or str(item.get("id"))
    source_url = f"https://burocultura.ru{external_id}"

    return {
        "title": title,
        "description": description,
        "start_at": start_at,
        "price_min": price_min,
        "price_max": price_max,
        "age_limit": age_limit,
        "image_url": image_url,
        "external_id": external_id,
        "source_url": source_url,
        "raw_json": json.dumps(item, ensure_ascii=False),
    }


async def parse_burocultura():
    print("1. Начинаем запрос к API...")
    url = "https://burocultura.ru"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://burocultura.ru",
    }

    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        if not r.text.strip():
            raise RuntimeError(f"Сервер вернул пустой ответ (Status: {r.status_code})")
        data = r.json()

    print(f"2. Данные получены! Событий в JSON: {len(data)}")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("Не задана переменная окружения DATABASE_URL")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    print("3. Подключаемся к базе данных через asyncpg...")
    conn = await asyncpg.connect(
        db_url,
        ssl=os.getenv("DATABASE_SSL", "require"),
        timeout=60,
        command_timeout=60,
        statement_cache_size=0,  # Важно для Supabase / Neon / PgBouncer
    )
    print("4. Подключение установлено!")

    try:
        # Получаем или создаем источник
        source_id = await conn.fetchval(
            "SELECT id FROM sources WHERE base_url = $1",
            "https://burocultura.ru",
        )
        if not source_id:
            source_id = await conn.fetchval(
                "INSERT INTO sources (name, base_url, is_active) VALUES ($1, $2, true) RETURNING id",
                "burocultura",
                "https://burocultura.ru",
            )
            print(f"5. Источник создан: {source_id}")
        else:
            print(f"5. Источник найден: {source_id}")

        # Загружаем все существующие external_id для этого источника одним запросом
        existing_rows = await conn.fetch(
            "SELECT external_id, event_id FROM event_sources WHERE source_id = $1",
            source_id,
        )
        existing_map = {row["external_id"]: row["event_id"] for row in existing_rows}
        print(f"6. Найдено в базе существующих событий: {len(existing_map)}")

        to_update_events = []
        to_update_sources = []
        to_insert = []

        # Подготавливаем данные в памяти (без сетевых задержек)
        for item in data:
            try:
                f = extract_event_fields(item)
                ext_id = f["external_id"]

                if ext_id in existing_map:
                    ev_id = existing_map[ext_id]
                    to_update_events.append((
                        f["title"],
                        f["description"],
                        f["start_at"],
                        f["price_min"],
                        f["price_max"],
                        f["age_limit"],
                        f["image_url"],
                        ev_id,
                    ))
                    to_update_sources.append((
                        f["raw_json"],
                        f["source_url"],
                        ext_id,
                        source_id,
                    ))
                else:
                    to_insert.append(f)
            except Exception as e:
                print(f"⚠️ Пропуск при разборе '{item.get('title')}': {e}")

        # Выполняем запись в БД пакетно
        async with conn.transaction():
            if to_update_events:
                print(f"7. Обновляем {len(to_update_events)} существующих событий...")
                await conn.executemany(
                    """
                    UPDATE events
                    SET title = $1,
                        description = $2,
                        start_at = $3,
                        price_min = $4,
                        price_max = $5,
                        age_limit = $6,
                        image_url = $7,
                        status = 'published'
                    WHERE id = $8
                    """,
                    to_update_events,
                )
                await conn.executemany(
                    """
                    UPDATE event_sources
                    SET raw_data = $1,
                        source_url = $2
                    WHERE external_id = $3 AND source_id = $4
                    """,
                    to_update_sources,
                )

            if to_insert:
                print(f"8. Добавляем {len(to_insert)} новых событий...")
                # Вставляем новые события и получаем их сгенерированные ID
                insert_event_sql = """
                    INSERT INTO events (
                        title, description, start_at, price_min, price_max, age_limit, image_url, status
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'published')
                    RETURNING id
                """
                sources_batch = []
                for f in to_insert:
                    new_event_id = await conn.fetchval(
                        insert_event_sql,
                        f["title"],
                        f["description"],
                        f["start_at"],
                        f["price_min"],
                        f["price_max"],
                        f["age_limit"],
                        f["image_url"],
                    )
                    sources_batch.append((
                        new_event_id,
                        source_id,
                        f["external_id"],
                        f["source_url"],
                        f["raw_json"],
                    ))

                await conn.executemany(
                    """
                    INSERT INTO event_sources (
                        event_id, source_id, external_id, source_url, raw_data
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    sources_batch,
                )

        print(f"✅ Готово! Добавлено: {len(to_insert)}, обновлено: {len(to_update_events)}.")

    except Exception as global_e:
        print(f"❌ ГЛОБАЛЬНАЯ ОШИБКА: {type(global_e).__name__}: {global_e}")
        raise
    finally:
        if not conn.is_closed():
            await conn.close()


if __name__ == "__main__":
    asyncio.run(parse_burocultura())
