import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app import crud, models, schemas
from app.database import AsyncSessionLocal
from app.routers.auth import session_digest

ZONE = ZoneInfo("Asia/Yekaterinburg")


async def connect_chat(token, chat_id):
    try:
        async with AsyncSessionLocal.begin() as db:
            return bool(await db.scalar(update(models.Preferences).where(
                models.Preferences.link_hash == session_digest(token),
                models.Preferences.link_expires > datetime.now(timezone.utc),
            ).values(telegram_chat=str(chat_id), link_hash=None, link_expires=None).returning(models.Preferences.email)))
    except IntegrityError:
        return False


async def weekly_round(telegram, format_results):
    now = datetime.now(ZONE)
    week = now.strftime("%G-%V")
    if now.weekday() != 3 or now.hour < 18:
        return
    async with AsyncSessionLocal() as db:
        emails = list(await db.scalars(select(models.Preferences.email).where(
            models.Preferences.weekly.is_(True), models.Preferences.telegram_chat.is_not(None),
        )))
    for email in emails:
        try:
            async with AsyncSessionLocal.begin() as db:
                prefs = await db.get(models.Preferences, email, with_for_update=True)
                if not prefs or not prefs.weekly or not prefs.telegram_chat or prefs.sent_week == week:
                    continue
                events = await crud.get_events(schemas.EventFilter(
                    **prefs.filters, date_from=now, date_to=now + timedelta(days=7),
                ), limit=5)
                if events:
                    await telegram("sendMessage", chat_id=prefs.telegram_chat, text=format_results({
                        "explanation": "Ваша подборка на неделю",
                        "events": [event.model_dump(mode="json") for event in events],
                    }))
                    prefs.sent_week = week
        except Exception as error:
            logging.warning("Сбой доставки подборки (%s)", type(error).__name__)


async def weekly_loop(telegram, format_results):
    while True:
        try:
            await weekly_round(telegram, format_results)
        except Exception as error:
            logging.warning("Сбой еженедельной подборки (%s)", type(error).__name__)
        await asyncio.sleep(300)
