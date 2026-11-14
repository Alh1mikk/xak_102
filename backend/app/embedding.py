import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# nomic-embed-text имеет контекстное окно 8192 токена.
# Для русского текста 1 токен ≈ 2-3 символа, поэтому 4000 символов — безопасный лимит.
MAX_TEXT_LENGTH = 1200


async def get_embedding(text: str, max_retries: int = 5) -> list[float]:
    """Получить эмбеддинг одного текста через Ollama с повторами при сбоях."""
    # Обрезаем текст, чтобы не превысить контекстное окно модели (иначе Ollama даёт 500)
    safe_text = text[:MAX_TEXT_LENGTH]
    if len(text) > MAX_TEXT_LENGTH:
        logger.debug("Текст обрезан с %d до %d символов", len(text), MAX_TEXT_LENGTH)

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/embeddings",
                    json={"model": EMBED_MODEL, "prompt": safe_text},
                )
                response.raise_for_status()
                data = response.json()
                return data["embedding"]
        except (httpx.HTTPStatusError, httpx.RequestError, KeyError) as exc:
            last_error = exc
            wait = min(2 ** attempt, 10)  # 2, 4, 8, 10, 10
            logger.warning(
                "Ollama embeddings упала (попытка %d/%d, длина текста %d): %s. Ждём %d сек.",
                attempt, max_retries, len(safe_text), type(exc).__name__, wait,
            )
            await asyncio.sleep(wait)

    raise RuntimeError(
        f"Не удалось получить эмбеддинг после {max_retries} попыток"
    ) from last_error


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Получить эмбеддинги списка текстов (последовательно, с паузами)."""
    results: list[list[float]] = []
    total = len(texts)

    for i, text in enumerate(texts, 1):
        # Небольшая пауза, чтобы Ollama успевала "дышать"
        if i > 1:
            await asyncio.sleep(0.3)

        try:
            embedding = await get_embedding(text)
            results.append(embedding)
        except RuntimeError:
            # Если конкретный текст не удалось обработать даже после 5 попыток,
            # логируем и пропускаем — лучше проиндексировать 205 из 206, чем упасть целиком.
            logger.error(
                "Пропускаю текст #%d (длина %d): не удалось получить эмбеддинг",
                i, len(text),
            )
            # Возвращаем нулевой вектор той же размерности (768 для nomic-embed-text),
            # чтобы zip() в reindex.py не разъехался.
            results.append([0.0] * 768)

        # Логируем прогресс каждые 20 событий, чтобы видеть движение
        if i % 20 == 0 or i == total:
            logger.info("Эмбеддинги: %d/%d", i, total)

    return results