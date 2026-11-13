import asyncio
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.digest import connect_chat, weekly_loop


def format_results(result):
    lines = [result["explanation"]]
    for event in result["events"]:
        start = datetime.fromisoformat(event["start_at"]).astimezone(ZoneInfo("Asia/Yekaterinburg"))
        price = event["price_min"]
        cost = "Цена уточняется" if price is None else "Бесплатно" if price == 0 else f"от {price} ₽"
        details = [event["title"][:200], f"{start:%d.%m %H:%M} · {cost}"]
        if event.get("address"):
            details.append(event["address"][:200])
        details.extend(event["source_urls"][:1])
        lines.append("\n".join(details))
    return "\n\n".join(lines)[:4096]


async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Задайте TELEGRAM_BOT_TOKEN в .env")
    async with httpx.AsyncClient(timeout=65) as client:
        async def telegram(method, **payload):
            response = await client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
            result = response.json()
            if not result.get("ok"):
                raise RuntimeError(f"Telegram {method}: {result.get('description')}")
            return result["result"]

        async with asyncio.TaskGroup() as group:
            group.create_task(weekly_loop(telegram, format_results))
            await poll(telegram, client)


async def poll(telegram, client):
    offset = 0
    while True:
        try:
            updates = await telegram("getUpdates", offset=offset, timeout=25, allowed_updates=["message"])
            for update in updates:
                message = update.get("message", {})
                query = message.get("text", "").strip()
                if query:
                    reply = "Это «Вне афиши» — культурные события Башкортостана. Напишите, например, «куда пойти в субботу с ребёнком до 1000 рублей»."
                    if query.startswith("/start ") and message["chat"]["type"] == "private":
                        linked = await connect_chat(query.split(maxsplit=1)[1], message["chat"]["id"])
                        reply = "Telegram привязан. Настройте подписку в профиле сайта." if linked else "Ссылка недействительна. Создайте новую в профиле."
                    elif not query.startswith("/"):
                        response = await client.post("http://api:8000/ai/search", json={"text": query[:500]})
                        response.raise_for_status()
                        result = response.json()
                        reply = format_results(result)
                    await telegram("sendMessage", chat_id=message["chat"]["id"], text=reply[:4096])
                offset = update["update_id"] + 1
        except (httpx.HTTPError, RuntimeError, ValueError) as error:
            logging.warning("Ошибка обмена с API (%s)", type(error).__name__)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
