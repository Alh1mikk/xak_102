# app/routers/sources.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app import crud, models

router = APIRouter(prefix="/sources", tags=["sources"])

class SourceIn(BaseModel):
    name: str
    base_url: str

@router.post("/", response_model=dict)
async def create_source(payload: SourceIn, db: AsyncSession = Depends(get_db)):
    s = await crud.get_or_create_source(db, payload.name, payload.base_url)
    return {"id": str(s.id), "name": s.name}