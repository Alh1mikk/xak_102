# app/routers/sources.py
import os
from secrets import compare_digest

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app import crud, models

router = APIRouter(prefix="/sources", tags=["sources"])

class SourceIn(BaseModel):
    name: str
    base_url: str

@router.post("/", response_model=dict)
async def create_source(payload: SourceIn, db: AsyncSession = Depends(get_db), x_admin_token: str = Header(default="")):
    token = os.getenv("SOURCE_ADMIN_TOKEN")
    if not token or not compare_digest(token.encode(), x_admin_token.encode()):
        raise HTTPException(status_code=403, detail="Требуется токен администратора")
    s = await crud.get_or_create_source(db, payload.name, payload.base_url)
    return {"id": str(s.id), "name": s.name}