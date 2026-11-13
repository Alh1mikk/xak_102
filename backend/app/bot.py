import asyncio
import logging
import os
import secrets
import zlib
from html import escape
from datetime import datetime, timezone
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


def results_widget(result):
    cards = []
    for event in result["events"][:5]:
        title = escape(event["title"][:200])
        address = escape((event.get("address") or "")[:160])
        start = datetime.fromisoformat(event["start_at"]).astimezone(ZoneInfo("Asia/Yekaterinburg"))
        price = event["price_min"]
        cost = "Цена уточняется" if price is None else "Бесплатно" if price == 0 else f"от {price} ₽"
        cards.append(f"<article><strong>{title}</strong><p>{start:%d.%m %H:%M} · {cost}</p><p>{address}</p></article>")
    html = ('<!doctype html><meta charset="utf-8"><style>'
            'body{font:15px system-ui;margin:10px;color:#173d2c}article{background:#e4ece3;'
            'border-radius:12px;padding:12px;margin:8px 0}p{margin:4px 0}</style>'
            f'<h3>Вне афиши</h3><p>{escape(result["explanation"][:400])}</p>' + "".join(cards))
    data = html.encode()
    return html if len(data) <= 32768 and len(zlib.compress(data, 9)) <= 4096 else None


async def send_results(telegram, chat_id, result, widget):
    if widget and result["events"] and (html := results_widget(result)):
        try:
            links = [[{"text": event["title"][:48], "url": event["source_urls"][0]}]
                     for event in result["events"][:5] if event["source_urls"]
                     and event["source_urls"][0].startswith(("https://", "http://"))]
            await telegram("sendWidget", chat_id=chat_id, html=html, reply_markup={"inline_keyboard": links})
            return
        except (RuntimeError, ValueError):
            logging.info("HTML-виджет недоступен, отправляем текст")
    await telegram("sendMessage", chat_id=chat_id, text=format_results(result))


COMMANDS = {
    "start": "Открыть афишу",
    "random": "Случайное событие",
    "family": "Куда сходить с детьми",
    "weekend": "Афиша на выходные",
    "help": "Список команд",
}
HELP = "Вне афиши ✦\n" + "\n".join(f"/{name} — {label}" for name, label in COMMANDS.items())
PRESETS = {"family": ("family", "Куда сходить с ребёнком?"),
           "weekend": ("friends", "Куда сходить на выходных?")}


async def handle_message(telegram, client, message):
    query = message.get("text", "").strip()
    if not query:
        return
    chat_id = message["chat"]["id"]
    private = message["chat"]["type"] == "private"
    head, _, argument = query.partition(" ")
    command = head.split("@", 1)[0].lower() if head.startswith("/") else None
    if command == "/start" and argument and private:
        linked = await connect_chat(argument.strip(), chat_id)
        reply = "Telegram привязан. Настройте подписку в профиле сайта." if linked else "Ссылка недействительна. Создайте новую в профиле."
        await telegram("sendMessage", chat_id=chat_id, text=reply)
        return
    if command and command not in ("/random", "/family", "/weekend"):
        if command == "/start" and private:
            html = '<!doctype html><meta charset="utf-8"><main><h2>Вне афиши ✦</h2><p>Культурные события Башкортостана.</p></main>'
            try:
                await telegram("sendWidget", chat_id=chat_id, html=html)
            except (RuntimeError, ValueError):
                logging.info("Приветственный виджет недоступен")
        await telegram("sendMessage", chat_id=chat_id, text=HELP)
        return
    try:
        if command == "/random":
            response = await client.get("http://api:8000/events/", params={
                "date_from": datetime.now(timezone.utc).isoformat(), "limit": 200,
            })
            response.raise_for_status()
            events = response.json()
            result = {"explanation": "Случайное событие 🎲" if events else "Предстоящих событий пока нет.",
                      "events": [secrets.choice(events)] if events else []}
        else:
            preset, text = PRESETS[command[1:]] if command else (None, query[:500])
            response = await client.post("http://api:8000/ai/search", json={"text": text, "preset": preset})
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError):
        await telegram("sendMessage", chat_id=chat_id, text="Афиша сейчас недоступна. Попробуйте чуть позже.")
        return
    await send_results(telegram, chat_id, result, private)


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

        try:
            await telegram("setMyCommands", commands=[
                {"command": name, "description": label} for name, label in COMMANDS.items()
            ])
        except (httpx.HTTPError, RuntimeError, ValueError):
            logging.warning("Не удалось обновить меню команд Telegram")

        async with asyncio.TaskGroup() as group:
            group.create_task(weekly_loop(lambda chat_id, result: send_results(telegram, chat_id, result, True)))
            await poll(telegram, client)


async def poll(telegram, client):
    offset = 0
    while True:
        try:
            updates = await telegram("getUpdates", offset=offset, timeout=25, allowed_updates=["message"])
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    await handle_message(telegram, client, update.get("message", {}))
                except (httpx.HTTPError, RuntimeError, ValueError) as error:
                    logging.warning("Не удалось обработать сообщение (%s)", type(error).__name__)

        except (httpx.HTTPError, RuntimeError, ValueError) as error:
            logging.warning("Ошибка обмена с API (%s)", type(error).__name__)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
