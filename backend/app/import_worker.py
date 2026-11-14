import asyncio
import logging

from run_parcer import parse_burocultura
from app.indexer import reindex_all


async def main():
    while True:
        try:
            await parse_burocultura()
            await reindex_all()
        except Exception:
            logging.exception("Импорт Бюро Культуры или индексация завершились ошибкой")
            await asyncio.sleep(300)
        else:
            await asyncio.sleep(24 * 60 * 60)


if __name__ == "__main__":
    asyncio.run(main())
