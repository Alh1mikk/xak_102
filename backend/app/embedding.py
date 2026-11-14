import logging
import os

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


async def get_embedding(text: str) -> list[float]:
    """Получить эмбеддинг одного текста через Ollama."""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
        )
        response.raise_for_status()
        data = response.json()
    return data["embedding"]


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Получить эмбеддинги списка текстов (последовательно, чтобы не перегружать Ollama)."""
    results: list[list[float]] = []
    for text in texts:
        results.append(await get_embedding(text))
    return results