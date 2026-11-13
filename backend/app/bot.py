import asyncio
import logging
import os

import httpx


async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Задайте TELEGRAM_BOT_TOKEN в .env")
    offset = 0
    async with httpx.AsyncClient(timeout=65) as client:
        async def telegram(method, **payload):
            response = await client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
            result = response.json()
            if not result.get("ok"):
                raise RuntimeError(f"Telegram {method}: {result.get('description')}")
            return result["result"]

        while True:
            try:
                updates = await telegram("getUpdates", offset=offset, timeout=25, allowed_updates=["message"])
                for update in updates:
                    message = update.get("message", {})
                    query = message.get("text", "").strip()
                    if query:
                        reply = "Напишите, например, «куда пойти в субботу с ребёнком до 1000 рублей»."
                        if not query.startswith("/"):
                            response = await client.post("http://api:8000/ai/search", json={"text": query[:500]})
                            response.raise_for_status()
                            result = response.json()
                            lines = [result["explanation"]]
                            for event in result["events"]:
                                lines.append(event["title"][:200] + "\n" + "\n".join(event["source_urls"][:1]))
                            reply = "\n\n".join(lines)
                        await telegram("sendMessage", chat_id=message["chat"]["id"], text=reply[:4096])
                    offset = update["update_id"] + 1
            except (httpx.HTTPError, RuntimeError, ValueError) as error:
                logging.warning("Ошибка обмена с API (%s)", type(error).__name__)
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
