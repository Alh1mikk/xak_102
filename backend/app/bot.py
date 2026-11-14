"""Telegram-бот «Вне афиши».

Один файл — намеренно, чтобы сохранить структуру исходника,
но с исправленными багами и улучшениями:

- мёртвый код digest перенесён в обработчики;
- reply-кнопки маппятся на команды;
- безопасная работа с source_urls / price / address;
- asyncio.get_running_loop() вместо устаревшего get_event_loop();
- weekly_loop защищён от падений (перезапуск);
- API_URL вынесен в env;
- единый хелпер для запросов к /ai/search и /events/;
- graceful shutdown по SIGTERM/KeyboardInterrupt;
- offset сохраняется в файл, чтобы не дублировать апдейты после рестарта;
- ссылки на задачи typing удерживаются (не собираются GC);
- таймзона вынесена в константу;
- format_results не режет URL посреди строки.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import signal
import zlib
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable
from zoneinfo import ZoneInfo

import httpx

from app.digest import connect_chat, weekly_loop

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

API_URL = os.environ.get("API_URL", "http://api:8000").rstrip("/")
TZ = ZoneInfo("Asia/Yekaterinburg")
OFFSET_FILE = Path(os.environ.get("TELEGRAM_OFFSET_FILE", ".telegram_offset.json"))

RATE_LIMIT_WINDOW = 2.0
RATE_LIMIT_MAX_CHATS = 1000

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_RATE_LIMIT: dict[int, float] = {}


def _rate_limited(chat_id: int) -> bool:
    now = asyncio.get_running_loop().time()
    last = _RATE_LIMIT.get(chat_id, 0.0)
    if now - last < RATE_LIMIT_WINDOW:
        return True
    _RATE_LIMIT[chat_id] = now
    if len(_RATE_LIMIT) > RATE_LIMIT_MAX_CHATS:
        cutoff = now - 60.0
        for cid in [c for c, t in _RATE_LIMIT.items() if t < cutoff]:
            del _RATE_LIMIT[cid]
    return False


# ---------------------------------------------------------------------------
# Форматирование
# ---------------------------------------------------------------------------


def _event_start(event: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(event["start_at"]).astimezone(TZ)


def _event_cost(event: dict[str, Any]) -> str:
    price = event.get("price_min")
    if price is None:
        return "Цена уточняется"
    if price == 0:
        return "Бесплатно"
    return f"от {price} ₽"


def _event_urls(event: dict[str, Any]) -> list[str]:
    urls = event.get("source_urls") or []
    return [u for u in urls if isinstance(u, str) and u.startswith(("https://", "http://"))]


def format_results(result: dict[str, Any]) -> str:
    """Текстовая версия результата, укладывается в лимит Telegram (4096)."""
    limit = 4096
    parts: list[str] = [result.get("explanation", "")[:600]]
    used = len(parts[0])

    for event in result.get("events", []):
        try:
            start = _event_start(event)
        except (KeyError, ValueError):
            continue
        block_lines = [
            (event.get("title") or "")[:200],
            f"{start:%d.%m %H:%M} · {_event_cost(event)}",
        ]
        if event.get("address"):
            block_lines.append((event["address"] or "")[:200])
        urls = _event_urls(event)
        if urls:
            block_lines.append(urls[0])

        block = "\n".join(block_lines)
        # +2 на разделитель "\n\n"
        if used + len(block) + 2 > limit:
            break
        parts.append(block)
        used += len(block) + 2

    return "\n\n".join(parts)


def results_widget(result: dict[str, Any]) -> str | None:
    """HTML-виджет для sendWidget. Возвращает None, если не влезает."""
    cards: list[str] = []
    for event in result.get("events", [])[:5]:
        try:
            start = _event_start(event)
        except (KeyError, ValueError):
            continue
        title = escape(str(event.get("title") or "")[:200])
        address = escape(str(event.get("address") or "")[:160])
        cards.append(
            f"<article><strong>{title}</strong>"
            f"<p>{start:%d.%m %H:%M} · {escape(_event_cost(event))}</p>"
            f"<p>{address}</p></article>"
        )

    explanation = escape(str(result.get("explanation") or "")[:400])
    html = (
        "<!doctype html><meta charset=\"utf-8\"><style>"
        "body{font:15px system-ui;margin:10px;color:#173d2c}"
        "article{background:#e4ece3;border-radius:12px;padding:12px;margin:8px 0}"
        "p{margin:4px 0}</style>"
        f"<h3>Вне афиши</h3><p>{explanation}</p>"
        + "".join(cards)
    )
    raw = html.encode()
    if len(raw) > 32768 or len(zlib.compress(raw, 9)) > 4096:
        return None
    return html


def results_inline_keyboard(result: dict[str, Any]) -> dict[str, Any]:
    buttons: list[list[dict[str, str]]] = []
    if result.get("events"):
        buttons.append([{"text": "🔄 Другое событие", "callback_data": "random"}])
    buttons.append([{"text": "🔙 Главное меню", "callback_data": "start"}])
    return {"inline_keyboard": buttons}


# ---------------------------------------------------------------------------
# Клавиатуры и тексты
# ---------------------------------------------------------------------------

COMMANDS: dict[str, str] = {
    "start": "Открыть афишу",
    "random": "Случайное событие",
    "family": "Куда сходить с детьми",
    "weekend": "Афиша на выходные",
    "ask": "Задать вопрос Roobert",
    "roobert": "Поговорить с Roobert",
    "digest": "Моя подборка на неделю",
    "help": "Список команд",
}

HELP = "Вне афиши ✦\n" + "\n".join(
    f"/{name} — {label}" for name, label in COMMANDS.items() if name != "start"
)

PRESETS: dict[str, tuple[str, str]] = {
    "family": ("family", "Куда сходить с ребёнком?"),
    "weekend": ("friends", "Куда сходить на выходных?"),
}

MAIN_MENU_REPLY_KEYBOARD: dict[str, Any] = {
    "keyboard": [
        [{"text": "🎲 Случайное событие"}, {"text": "👨‍👩‍👧 С детьми"}],
        [{"text": "🗓️ На выходные"}, {"text": "📋 Подборка недели"}],
        [{"text": "Помощь"}],
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False,
}

# Маппинг текста reply-кнопок на команды.
BUTTON_TO_COMMAND: dict[str, str] = {
    "🎲 Случайное событие": "/random",
    "👨‍👩‍👧 С детьми": "/family",
    "🗓️ На выходные": "/weekend",
    "📋 Подборка недели": "/digest",
    "Помощь": "/help",
}

# Команды, которые обрабатывает этот модуль (остальные -> HELP).
KNOWN_COMMANDS = {"/random", "/family", "/weekend", "/ask", "/roobert", "/digest", "/help"}

WELCOME_HTML = (
    "<!doctype html><meta charset=\"utf-8\"><main>"
    "<h2>Вне афиши ✦</h2>"
    "<p>Культурные события Башкортостана.</p></main>"
)

# ---------------------------------------------------------------------------
# Обёртка над Telegram API
# ---------------------------------------------------------------------------

TelegramCall = Callable[..., Awaitable[Any]]


def make_telegram(client: httpx.AsyncClient, token: str) -> TelegramCall:
    async def telegram(method: str, **payload: Any) -> Any:
        response = await client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Telegram {method}: invalid JSON") from exc
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method}: {data.get('description')}")
        return data["result"]

    return telegram


# ---------------------------------------------------------------------------
# API-хелперы
# ---------------------------------------------------------------------------


async def fetch_events_random(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get(
        f"{API_URL}/events/",
        params={"date_from": datetime.now(timezone.utc).isoformat(), "limit": 200},
        timeout=15.0,
    )
    response.raise_for_status()
    events = response.json()
    return {
        "explanation": "Случайное событие 🎲" if events else "Предстоящих событий пока нет.",
        "events": [secrets.choice(events)] if events else [],
    }


async def fetch_ai_search(
    client: httpx.AsyncClient, text: str, preset: str | None
) -> dict[str, Any]:
    response = await client.post(
        f"{API_URL}/ai/search", json={"text": text, "preset": preset}, timeout=30.0
    )
    response.raise_for_status()
    return response.json()


async def fetch_ai_ask(client: httpx.AsyncClient, question: str) -> dict[str, Any]:
    response = await client.post(
        f"{API_URL}/ai/ask", json={"text": question}, timeout=30.0
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Отправка сообщений
# ---------------------------------------------------------------------------


async def send_chat_action(telegram: TelegramCall, chat_id: int, action: str = "typing") -> None:
    try:
        await telegram("sendChatAction", chat_id=chat_id, action=action)
    except (RuntimeError, ValueError, httpx.HTTPError):
        pass


async def send_results(
    telegram: TelegramCall,
    chat_id: int,
    result: dict[str, Any],
    allow_widget: bool,
) -> None:
    if allow_widget and result.get("events"):
        html = results_widget(result)
        if html:
            links = [
                [{"text": event["title"][:48], "url": _event_urls(event)[0]}]
                for event in result["events"][:5]
                if _event_urls(event)
            ]
            try:
                await telegram(
                    "sendWidget",
                    chat_id=chat_id,
                    html=html,
                    reply_markup={"inline_keyboard": links} if links else None,
                )
                return
            except (RuntimeError, ValueError, httpx.HTTPError):
                logger.info("HTML-виджет недоступен, отправляем текст")

    try:
        await telegram(
            "sendMessage",
            chat_id=chat_id,
            text=format_results(result),
            reply_markup=results_inline_keyboard(result),
        )
    except (RuntimeError, ValueError, httpx.HTTPError):
        logger.exception("Не удалось отправить текст результата в чат %s", chat_id)


async def send_help(telegram: TelegramCall, chat_id: int) -> None:
    await telegram(
        "sendMessage", chat_id=chat_id, text=HELP, reply_markup=MAIN_MENU_REPLY_KEYBOARD
    )


async def send_welcome_widget(telegram: TelegramCall, chat_id: int) -> None:
    try:
        await telegram("sendWidget", chat_id=chat_id, html=WELCOME_HTML)
    except (RuntimeError, ValueError, httpx.HTTPError):
        logger.info("Приветственный виджет недоступен")


# ---------------------------------------------------------------------------
# Удержание фоновых задач (чтобы их не собрал GC)
# ---------------------------------------------------------------------------

_BACKGROUND: set[asyncio.Task[Any]] = set()


def _spawn(coro: Awaitable[Any]) -> None:
    task = asyncio.create_task(coro)
    _BACKGROUND.add(task)
    task.add_done_callback(_BACKGROUND.discard)


# ---------------------------------------------------------------------------
# Обработчики
# ---------------------------------------------------------------------------


async def _run_search_and_send(
    telegram: TelegramCall,
    client: httpx.AsyncClient,
    chat_id: int,
    text: str,
    preset: str | None,
    allow_widget: bool,
) -> None:
    try:
        result = await fetch_ai_search(client, text, preset)
    except (httpx.HTTPError, ValueError, asyncio.TimeoutError):
        await telegram(
            "sendMessage",
            chat_id=chat_id,
            text="Афиша сейчас недоступна. Попробуйте чуть позже.",
            reply_markup=MAIN_MENU_REPLY_KEYBOARD,
        )
        return
    await send_results(telegram, chat_id, result, allow_widget)


async def _run_random_and_send(
    telegram: TelegramCall,
    client: httpx.AsyncClient,
    chat_id: int,
    allow_widget: bool,
) -> None:
    try:
        result = await fetch_events_random(client)
    except (httpx.HTTPError, ValueError, asyncio.TimeoutError):
        await telegram(
            "sendMessage",
            chat_id=chat_id,
            text="Афиша сейчас недоступна. Попробуйте чуть позже.",
            reply_markup=MAIN_MENU_REPLY_KEYBOARD,
        )
        return
    await send_results(telegram, chat_id, result, allow_widget)


async def _run_digest_and_send(
    telegram: TelegramCall,
    client: httpx.AsyncClient,
    chat_id: int,
    allow_widget: bool,
) -> None:
    await _run_search_and_send(
        telegram, client, chat_id, "недельная подборка событий", "family", allow_widget
    )


async def handle_message(
    telegram: TelegramCall,
    client: httpx.AsyncClient,
    message: dict[str, Any],
) -> None:
    query = (message.get("text") or "").strip()
    if not query:
        return

    chat_id = message["chat"]["id"]
    private = message["chat"].get("type") == "private"

    if _rate_limited(chat_id):
        await telegram(
            "sendMessage",
            chat_id=chat_id,
            text="Пожалуйста, не присылайте сообщения так часто. Подождите пару секунд.",
        )
        return

    # Reply-кнопки присылают текст -> маппим на команду
    if query in BUTTON_TO_COMMAND:
        query = BUTTON_TO_COMMAND[query]

    head, _, argument = query.partition(" ")
    command: str | None
    if head.startswith("/"):
        command = head.split("@", 1)[0].lower()
    else:
        command = None

    # Привязка чата
    if command == "/start" and argument and private:
        linked = await connect_chat(argument.strip(), chat_id)
        reply = (
            "Telegram привязан. Настройте подписку в профиле сайта."
            if linked
            else "Ссылка недействительна. Создайте новую в профиле."
        )
        await telegram("sendMessage", chat_id=chat_id, text=reply)
        return

    # Неизвестная команда или /help
    if command is not None and command not in KNOWN_COMMANDS:
        if command == "/start" and private:
            await send_welcome_widget(telegram, chat_id)
        await send_help(telegram, chat_id)
        return

    if command == "/help":
        await send_help(telegram, chat_id)
        return

    # Индикатор набора для «долгих» команд
    if command in ("/ask", "/roobert", "/family", "/weekend", "/digest", None):
        _spawn(send_chat_action(telegram, chat_id, "typing"))

    if command == "/random":
        await _run_random_and_send(telegram, client, chat_id, private)
        return

    if command == "/digest":
        await _run_digest_and_send(telegram, client, chat_id, private)
        return

    if command in ("/ask", "/roobert"):
        question = argument.strip()
        if not question:
            await telegram(
                "sendMessage",
                chat_id=chat_id,
                text=(
                    "Напишите вопрос после команды, например:\n"
                    "/ask куда пойти с детьми в субботу бесплатно"
                ),
            )
            return
        try:
            data = await fetch_ai_ask(client, question)
        except (httpx.HTTPError, ValueError, asyncio.TimeoutError):
            await telegram(
                "sendMessage",
                chat_id=chat_id,
                text="Roobert сейчас недоступен. Попробуйте чуть позже.",
            )
            return
        answer = str(data.get("answer") or "Не удалось получить ответ.")
        sources = data.get("sources") or []
        if sources:
            answer += "\n\nИсточники:\n" + "\n".join(
                f"• {str(s.get('content') or '')[:120]}" for s in sources[:3]
            )
        await telegram("sendMessage", chat_id=chat_id, text=answer[:4000])
        return

    # /family, /weekend или свободный текст
    if command in ("/family", "/weekend"):
        preset, text = PRESETS[command[1:]]
    else:
        preset, text = None, query[:500]
    await _run_search_and_send(telegram, client, chat_id, text, preset, private)


async def handle_callback(
    telegram: TelegramCall,
    client: httpx.AsyncClient,
    callback_query: dict[str, Any],
) -> None:
    chat_id = callback_query["message"]["chat"]["id"]
    data = callback_query.get("data", "")
    callback_id = callback_query["id"]

    try:
        await telegram("answerCallbackQuery", callback_query_id=callback_id)
    except (httpx.HTTPError, RuntimeError, ValueError):
        pass

    if data == "start":
        await send_welcome_widget(telegram, chat_id)
        await send_help(telegram, chat_id)
        return

    if data == "random":
        await _run_random_and_send(telegram, client, chat_id, allow_widget=False)
        return


# ---------------------------------------------------------------------------
# Offset-персистентность
# ---------------------------------------------------------------------------


def _load_offset() -> int:
    try:
        return int(json.loads(OFFSET_FILE.read_text())["offset"])
    except (FileNotFoundError, KeyError, ValueError, OSError):
        return 0


def _save_offset(offset: int) -> None:
    try:
        OFFSET_FILE.write_text(json.dumps({"offset": offset}))
    except OSError:
        logger.warning("Не удалось сохранить offset в %s", OFFSET_FILE)


# ---------------------------------------------------------------------------
# Поллинг и weekly_loop
# ---------------------------------------------------------------------------


async def poll(
    telegram: TelegramCall,
    client: httpx.AsyncClient,
    stop_event: asyncio.Event,
) -> None:
    offset = _load_offset()
    while not stop_event.is_set():
        try:
            updates = await telegram(
                "getUpdates",
                offset=offset,
                timeout=25,
                allowed_updates=["message", "callback_query"],
            )
        except (httpx.HTTPError, RuntimeError, ValueError) as error:
            logger.warning("Ошибка обмена с API (%s)", type(error).__name__)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            continue

        for update in updates:
            offset = update["update_id"] + 1
            try:
                if "callback_query" in update:
                    await handle_callback(telegram, client, update["callback_query"])
                elif update.get("message"):
                    await handle_message(telegram, client, update["message"])
            except (httpx.HTTPError, RuntimeError, ValueError):
                logger.warning(
                    "Не удалось обработать обновление (%s)",
                    update.get("update_id"),
                    exc_info=True,
                )

        if updates:
            _save_offset(offset)


async def safe_weekly_loop(
    send: Callable[[int, dict[str, Any]], Awaitable[None]],
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            # weekly_loop должен сам по себе крутиться; если упадёт — перезапускаем
            await weekly_loop(send)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("weekly_loop упал, перезапуск через 60с")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                pass


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------


async def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Задайте TELEGRAM_BOT_TOKEN в .env")

    logging.basicConfig(level=logging.INFO)

    stop_event = asyncio.Event()

    def _request_stop(*_: Any) -> None:
        logger.info("Получен сигнал остановки")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # Windows или среда без loop.add_signal_handler
            pass

    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    async with httpx.AsyncClient(timeout=65, limits=limits) as client:
        telegram = make_telegram(client, token)

        try:
            await telegram(
                "setMyCommands",
                commands=[{"command": n, "description": d} for n, d in COMMANDS.items()],
            )
        except (httpx.HTTPError, RuntimeError, ValueError):
            logger.warning("Не удалось обновить меню команд Telegram")

        async def _send_via(chat_id: int, result: dict[str, Any]) -> None:
            await send_results(telegram, chat_id, result, allow_widget=True)

        poll_task = asyncio.create_task(poll(telegram, client, stop_event))
        weekly_task = asyncio.create_task(safe_weekly_loop(_send_via, stop_event))

        try:
            await stop_event.wait()
        finally:
            for task in (poll_task, weekly_task):
                task.cancel()
            for task in (poll_task, weekly_task):
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass


if __name__ == "__main__":
    asyncio.run(main())