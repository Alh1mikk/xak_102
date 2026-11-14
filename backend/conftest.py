import os

# НЕ импортируем app.database здесь, чтобы тесты без БД не падали.
# DATABASE_URL задаётся окружением (TEST_DATABASE_URL для локальных SQLite, DATABASE_URL для CI).
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test"),
)

import pytest  # noqa: E402
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.models import Base  # noqa: E402

engine = create_async_engine(
    os.environ["DATABASE_URL"],
    echo=False,
    poolclass=NullPool,
    future=True,
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(autouse=True)
async def _isolated_db():
    """Каждый тест работает в чистой БД: создаём таблицы, падаем в конце."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db() -> AsyncSession:
    """Автоматически откатывает транзакцию после теста."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()

