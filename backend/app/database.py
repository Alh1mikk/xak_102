import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Важно для Supabase: передаем ssl="require" и настраиваем пул
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Поставьте False на проде, True удобно для отладки SQL
    connect_args={"ssl": "require"},  # Supabase требует SSL
    pool_size=5,
    max_overflow=10,
)

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

# Зависимость для FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()