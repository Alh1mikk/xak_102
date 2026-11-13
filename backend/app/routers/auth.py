import asyncio
import hashlib
import re
import smtplib
import ssl
from email.message import EmailMessage
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import EmailUser, TelegramUser

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
    return {"email_enabled": email_configured()}


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
    set_session_cookie(response, session)
    return {"name": name}


async def find_user(db, session):
    if session:
        for model in (EmailUser, TelegramUser):
            user = await db.scalar(select(model).where(
                model.session_hash == session_digest(session),
                model.session_expires > datetime.now(timezone.utc),
            ))
            if user:
                return user


@router.get("/me")
async def profile(afisha_session: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    user = await find_user(db, afisha_session)
    if isinstance(user, EmailUser):
        return {"name": user.email}
    return {"name": user.name} if user else None


@router.post("/logout")
async def logout(response: Response, afisha_session: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    user = await find_user(db, afisha_session)
    if user:
        user.session_hash = user.session_expires = None
    response.delete_cookie(COOKIE)
    return {"ok": True}

def set_session_cookie(response, session):
    response.set_cookie(COOKIE, session, max_age=SESSION_AGE, httponly=True, samesite="lax",
                        secure=os.getenv("AUTH_SECURE_COOKIE") == "true")


def email_configured():
    return all(os.getenv(key) for key in ("SMTP_HOST", "SMTP_FROM", "EMAIL_CODE_SECRET"))


class EmailRequest(BaseModel):
    email: str = Field(max_length=254)


class EmailConfirmation(EmailRequest):
    code: str = Field(pattern=r"^[0-9]{6}$")


def normalized_email(value):
    email = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z0-9-]+(?:[.][a-z0-9-]+)+", email):
        raise HTTPException(422, "Укажите корректный email")
    return email


def code_digest(email, code):
    key = os.environ["EMAIL_CODE_SECRET"].encode()
    return hmac.new(key, f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def send_login_email(email, code):
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = email
    message["Subject"] = "Код входа во «Вне афиши»"
    message.set_content(f"Код входа: {code}\nОн действует 15 минут. Если вы не запрашивали код, проигнорируйте письмо.")
    context = ssl.create_default_context()
    implicit_tls = os.getenv("SMTP_IMPLICIT_TLS", "false") == "true"
    port = int(os.getenv("SMTP_PORT") or (465 if implicit_tls else 587))
    connection = (smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=context, timeout=10)
                  if implicit_tls else smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=10))
    with connection as smtp:
        if not implicit_tls and os.getenv("SMTP_HOST") != "mailpit":
            smtp.starttls(context=context)
        if username := os.getenv("SMTP_USERNAME"):
            smtp.login(username, os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(message)


@router.post("/email/request")
async def request_email(payload: EmailRequest, db: AsyncSession = Depends(get_db)):
    if not email_configured():
        raise HTTPException(503, "Отправка писем пока не настроена")
    email = normalized_email(payload.email)
    code = f"{secrets.randbelow(1000000):06d}"
    now = datetime.now(timezone.utc)
    fields = dict(login_hash="0:" + code_digest(email, code), login_expires=now + timedelta(minutes=15))
    saved = await db.scalar(insert(EmailUser).values(email=email, **fields).on_conflict_do_update(
        index_elements=[EmailUser.email], set_=fields,
        where=or_(EmailUser.login_expires.is_(None), EmailUser.login_expires <= now + timedelta(minutes=14)),
    ).returning(EmailUser.email))
    if not saved:
        raise HTTPException(429, "Повторите запрос через минуту")
    try:
        await asyncio.to_thread(send_login_email, email, code)
    except (OSError, ValueError, smtplib.SMTPException):
        raise HTTPException(503, "Не удалось отправить письмо. Попробуйте позже.")
    return {"ok": True}


@router.post("/email/confirm")
async def confirm_email(payload: EmailConfirmation, response: Response, db: AsyncSession = Depends(get_db)):
    if not email_configured():
        raise HTTPException(503, "Вход по почте пока не настроен")
    email = normalized_email(payload.email)
    now = datetime.now(timezone.utc)
    user = await db.get(EmailUser, email, with_for_update=True)
    if not user or not user.login_hash or ":" not in user.login_hash or user.login_expires <= now:
        raise HTTPException(401, "Код истёк или уже использован")
    attempts, expected = user.login_hash.split(":", 1)
    if int(attempts) >= 5:
        raise HTTPException(429, "Лимит попыток исчерпан. Запросите новый код.")
    if not secrets.compare_digest(code_digest(email, payload.code), expected):
        user.login_hash = f"{int(attempts) + 1}:{expected}"
        await db.commit()
        raise HTTPException(401, "Неверный код")
    session = secrets.token_urlsafe(32)
    user.login_hash = user.login_expires = None
    user.session_hash = session_digest(session)
    user.session_expires = now + timedelta(seconds=SESSION_AGE)
    set_session_cookie(response, session)
    return {"name": user.email}
