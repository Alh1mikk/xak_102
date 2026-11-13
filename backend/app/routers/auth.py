import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import TelegramUser

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "afisha_session"
SESSION_AGE = 7 * 86400


def session_digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def verified_telegram_user(payload, token, now):
    data = dict(payload)
    signature = data.pop("hash", "")
    if not isinstance(signature, str) or len(signature) != 64:
        return None
    if not all(isinstance(value, (int, str)) for value in data.values()):
        return None
    check = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    expected = hmac.new(hashlib.sha256(token.encode()).digest(), check.encode(), hashlib.sha256).hexdigest()
    try:
        age = now - int(data["auth_date"])
        user_id = str(int(data["id"]))
    except (KeyError, TypeError, ValueError):
        return None
    if not secrets.compare_digest(signature.encode(), expected.encode()) or not -30 <= age <= 300:
        return None
    return user_id, str(data.get("first_name") or "Пользователь Telegram")[:200]


@router.get("/config")
async def config():
    return {"telegram_bot": os.getenv("TELEGRAM_BOT_USERNAME") if os.getenv("TELEGRAM_BOT_TOKEN") else None}


@router.post("/telegram")
async def login(payload: dict, response: Response, db: AsyncSession = Depends(get_db)):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or not os.getenv("TELEGRAM_BOT_USERNAME"):
        raise HTTPException(503, "Вход через Telegram пока не настроен")
    verified = verified_telegram_user(payload, token, time.time())
    if verified is None:
        raise HTTPException(401, "Подпись Telegram недействительна")
    user_id, name = verified
    session = secrets.token_urlsafe(32)
    fields = dict(name=name, session_hash=session_digest(session),
                  session_expires=datetime.now(timezone.utc) + timedelta(seconds=SESSION_AGE))
    await db.execute(insert(TelegramUser).values(id=user_id, **fields).on_conflict_do_update(
        index_elements=[TelegramUser.id], set_=fields,
    ))
    response.set_cookie(COOKIE, session, max_age=SESSION_AGE, httponly=True, samesite="lax",
                        secure=os.getenv("AUTH_SECURE_COOKIE") == "true")
    return {"name": name}


async def find_user(db, session):
    if session:
        return await db.scalar(select(TelegramUser).where(
            TelegramUser.session_hash == session_digest(session),
            TelegramUser.session_expires > datetime.now(timezone.utc),
        ))


@router.get("/me")
async def profile(afisha_session: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    user = await find_user(db, afisha_session)
    return {"name": user.name} if user else None


@router.post("/logout")
async def logout(response: Response, afisha_session: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    user = await find_user(db, afisha_session)
    if user:
        user.session_hash = user.session_expires = None
    response.delete_cookie(COOKIE)
    return {"ok": True}
