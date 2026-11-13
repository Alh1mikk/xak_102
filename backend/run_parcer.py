import asyncio
import httpx
import asyncpg
import os
import json
import math
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

async def parse_burocultura():
    print("1. Начинаем запрос к API...")
    url = "https://ufa.burocultura.ru/api/events"
    
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
    print(f"2. Данные получены! Событий в JSON: {len(data)}")

    # Подключаемся напрямую через asyncpg
    db_url = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
    print("3. Подключаемся к базе данных через asyncpg...")
    conn = await asyncpg.connect(db_url, ssl="require", command_timeout=60)
    print("4. Подключение установлено!")

    try:
        # 1. Получаем или создаем источник
        source_row = await conn.fetchrow("SELECT id FROM sources WHERE base_url = $1", "https://ufa.burocultura.ru")
        if source_row:
            source_id = source_row['id']
            print(f"5. Источник найден: {source_id}")
        else:
            source_id = await conn.fetchval(
                "INSERT INTO sources (name, base_url, is_active) VALUES ($1, $2, true) RETURNING id",
                "burocultura", "https://ufa.burocultura.ru"
            )
            print(f"5. Источник создан: {source_id}")

        # 2. Обрабатываем события
        count = 0

        async def get_new_conn():
            nonlocal conn
            try:
                await conn.close()
            except Exception:
                pass
            return await asyncpg.connect(db_url, ssl="require", command_timeout=60)

        for i, item in enumerate(data[:5]): # Берем первые 5 для теста
            try:
                # Безопасный парсинг даты (убираем tzinfo, так как asyncpg может ругаться)
                date_str = item.get("dateStart")
                if date_str:
                    start_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    start_at = datetime.now()
                
                # Безопасный парсинг возраста ("12+" -> 12)
                age_str = item.get("ageRestriction", "")
                age_limit = int(''.join(filter(str.isdigit, str(age_str)))) if age_str else None
                
                # Безопасный парсинг цен (может прийти строка "1500.50" или float)
                def parse_price(val):
                    if not val: return None
                    try: return int(math.ceil(float(val)))
                    except: return None

                price_min = parse_price(item.get("priceFrom"))
                price_max = parse_price(item.get("priceTo"))
                
                title = item.get("title") or "Без названия"
                external_id = item.get("slug")
                source_url = f"https://ufa.burocultura.ru/events/{external_id}"

                print(f"6. Сохраняем: {title[:30]}...")

                # Проверяем, есть ли уже такое событие (дедупликация)
                exists = await conn.fetchval("SELECT id FROM event_sources WHERE external_id = $1 AND source_id = $2", external_id, source_id)
                
                if exists:
                    print("   Уже существует, пропускаем.")
                    continue

                try:
                    event_id = await conn.fetchval(
                        """INSERT INTO events (title, description, start_at, price_min, price_max, age_limit, image_url, status) 
                           VALUES ($1::text, $2::text, $3::timestamptz, $4::int, $5::int, $6::int, $7::text, 'published') RETURNING id""",
                        str(title), str(item.get("description") or ""), start_at, 
                        price_min, price_max, age_limit, str(item.get("imageUrl") or "")
                    )
                    print(f"   ID события: {event_id}")
                except Exception as e:
                    print(f"❌ ОШИБКА INSERT events: {type(e).__name__}: {e}")
                    conn = await get_new_conn()
                    continue
                # --- Вставляем связь ---
                try:
                    await conn.execute(
                        """INSERT INTO event_sources (event_id, source_id, external_id, source_url, raw_data) 
                           VALUES ($1, $2, $3, $4, $5)""",
                        event_id, source_id, external_id, source_url, json.dumps(item)
                    )
                    count += 1
                    print("   Успешно!")
                except Exception as e:
                    print(f"❌ ОШИБКА INSERT event_sources: {type(e).__name__}: {e}")

            except Exception as e:
                print(f"❌ Критическая ошибка при парсинге {item.get('title')}: {type(e).__name__}: {e}")
                if "connection" in str(e).lower() or "closed" in str(e).lower():
                    conn = await get_new_conn()

        print(f"✅ Успешно добавлено новых событий: {count}")
        
    except Exception as global_e:
        print(f"❌ ГЛОБАЛЬНАЯ ОШИБКА: {global_e}")
    finally:
        try:
            await conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(parse_burocultura())