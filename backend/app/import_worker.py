import asyncio
import logging

from run_parcer import parse_burocultura


async def main():
    while True:
        try:
            await parse_burocultura()
        except Exception:
            logging.exception("Импорт Бюро Культуры завершился ошибкой")
            await asyncio.sleep(300)
        else:
            await asyncio.sleep(24 * 60 * 60)


if __name__ == "__main__":
    asyncio.run(main())
