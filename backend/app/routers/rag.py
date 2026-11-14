import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.vector import search_similar

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")


async def ask_roobert(question: str, context_chunks: list[str]) -> str:
    if not context_chunks:
        return "В афише нет подходящих событий по вашему запросу."

    context = "\n\n".join(context_chunks)
    
    # ПРОМПТ: просим написать красивый текст на основе ГОТОВЫХ событий
    prompt = (
        "Ты — ассистент афиши. Ниже список подходящих событий.\n"
        "Напиши короткий, дружелюбный ответ (до 300 символов), используя ТОЛЬКО этот список.\n"
        "Не придумывай события, которых нет в списке. Не пиши лишнего.\n\n"
        f"События:\n{context}\n\n"
        f"Вопрос: {question}\n\n"
        "Ответ:"
    )

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 150},
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.exception("Ollama упала: %s", exc)
        return "Нашлись следующие события: " + ", ".join(context_chunks)

    return (data.get("response") or "").strip()