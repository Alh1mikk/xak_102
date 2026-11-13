import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    url = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
    print("Подключаемся...")
    # Убираем параметры, которые не понимает чистый asyncpg
    url = url.split("?")[0] 
    
    conn = await asyncpg.connect(url, ssl="require")
    print("✅ Подключение установлено!")
    
    res = await conn.fetch("SELECT id, name FROM sources LIMIT 5;")
    print("Таблица sources существует! Записи:", res)
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())