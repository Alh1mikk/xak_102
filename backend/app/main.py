
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.connection import get_db, close_db
from app import models


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_db()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API культурной афиши Республики Башкортостан",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/api/v1/health")
async def health():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/api/v1/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("SELECT 1"))
        return {
            "database": "connected",
            "result": result.scalar(),
        }
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
