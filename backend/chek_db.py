import asyncio
from app.database import engine
from sqlalchemy import text

async def main():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version();"))
        print(result.scalar())

if __name__ == "__main__":
    asyncio.run(main())