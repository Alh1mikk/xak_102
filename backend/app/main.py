from contextlib import asynccontextmanager
from sqlalchemy import text
from app.database import engine
from app.models import Base
from app.region import refresh_verified_sources
from app.database import AsyncSessionLocal

@asynccontextmanager
async def lifespan(app):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal.begin() as db:
        await refresh_verified_sources(db)
    try:
        yield
    finally:
        await engine.dispose()

# backend/app/main.py
from fastapi import FastAPI
from app.routers import events, sources, ai, auth, community

app = FastAPI(
    title="Афиша культуры Башкортостана",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(events.router)
app.include_router(sources.router)
app.include_router(ai.router)
app.include_router(auth.router)
app.include_router(community.router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "afisha-rb"}

@app.get("/health")
async def health():
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ok"}
