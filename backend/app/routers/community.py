import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx

from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import get_db
from app.routers.auth import find_user, session_digest

router = APIRouter(tags=["community"])


async def account(afisha_session: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    user = await find_user(db, afisha_session)
    if not isinstance(user, models.EmailUser):
        raise HTTPException(401, "Войдите по почте")
    return user.email


class PreferenceInput(BaseModel):
    city_id: UUID | None = None
    category_id: UUID | None = None
    price_max: int | None = Field(default=None, ge=0, le=1000000)
    family_only: bool = False
    weekly: bool = False


@router.get("/preferences")
async def get_preferences(email: str = Depends(account), db: AsyncSession = Depends(get_db)):
    prefs = await db.get(models.Preferences, email)
    return {**(prefs.filters if prefs else {}), "weekly": bool(prefs and prefs.weekly),
            "linked": bool(prefs and prefs.telegram_chat)}


@router.put("/preferences")
async def save_preferences(payload: PreferenceInput, email: str = Depends(account), db: AsyncSession = Depends(get_db)):
    fields = dict(filters=payload.model_dump(mode="json", exclude={"weekly"}), weekly=payload.weekly)
    await db.execute(insert(models.Preferences).values(email=email, **fields).on_conflict_do_update(
        index_elements=[models.Preferences.email], set_=fields,
    ))
    return {"ok": True}


@router.post("/preferences/telegram")
async def link_telegram(email: str = Depends(account), db: AsyncSession = Depends(get_db)):
    bot = os.getenv("TELEGRAM_BOT_USERNAME", "")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if bot_token and not bot:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                result = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
                result.raise_for_status()
                bot = result.json().get("result", {}).get("username", "")
        except (httpx.HTTPError, ValueError):
            pass
    if not bot_token or not re.fullmatch(r"[a-zA-Z0-9_]{5,32}", bot):
        raise HTTPException(503, "Telegram-бот пока не настроен")
    token = secrets.token_urlsafe(24)
    fields = dict(link_hash=session_digest(token), link_expires=datetime.now(timezone.utc) + timedelta(minutes=10))
    await db.execute(insert(models.Preferences).values(email=email, filters={}, **fields).on_conflict_do_update(
        index_elements=[models.Preferences.email], set_=fields,
    ))
    return {"url": f"https://t.me/{bot}?start={token}"}


@router.delete("/preferences/telegram")
async def unlink_telegram(email: str = Depends(account), db: AsyncSession = Depends(get_db)):
    await db.execute(update(models.Preferences).where(models.Preferences.email == email).values(
        telegram_chat=None, weekly=False, link_hash=None, link_expires=None,
    ))
    return {"ok": True}
