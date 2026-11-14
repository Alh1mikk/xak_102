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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "roobert")


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    source_type: str | None = Field(default=None)


class SourceOut(BaseModel):
    source_type: str
    source_id: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AskOut(BaseModel):
    answer: str
    sources: list[SourceOut]
    model_used: str


async def ask_roobert(question: str, context_chunks: list[str]) -> str:
    """Задать вопрос модели roobert с контекстом из найденных чанков."""
    context = "\n\n".join(context_chunks) if context_chunks else "Контекст не найден."
    prompt = (
        "Ты — Roobert, ИИ-ассистент афиши культуры Башкортостана. "
        "Отвечай на русском языке, опираясь только на предоставленный контекст. "
        "Если информации в контексте недостаточно, скажи об этом честно. "
        "Не придумывай факты. В конце ответа укажи, на каких источниках основаны сведения.\n\n"
        f"Контекст:\n{context}\n\n"
        f"Вопрос: {question}\n\n"
        "Ответ:"
    )

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.exception("Ollama недоступна: %s", exc)
        raise HTTPException(status_code=503, detail="LLM временно недоступна") from exc
    except ValueError as exc:
        logger.exception("Ollama вернула невалидный JSON")
        raise HTTPException(status_code=502, detail="Некорректный ответ LLM") from exc

    return (data.get("response") or "").strip()


@router.post("/ask", response_model=AskOut)
async def ask(
    payload: AskIn,
    db: AsyncSession = Depends(get_db),
):
    """RAG-эндпоинт: векторный поиск + ответ от модели roobert."""
    # 1. Векторный поиск релевантных чанков
    found = await search_similar(
        db,
        query=payload.text,
        top_k=payload.top_k,
        source_type=payload.source_type,
    )

    if not found:
        # fallback: ответим без контекста
        answer = await ask_roobert(payload.text, [])
        return AskOut(
            answer=answer,
            sources=[],
            model_used=OLLAMA_MODEL,
        )

    # 2. Собираем контекст и источники
    context_chunks: list[str] = []
    sources: list[SourceOut] = []
    for chunk, distance in found:
        context_chunks.append(f"[Источник: {chunk.source_type}] {chunk.content}")
        sources.append(
            SourceOut(
                source_type=chunk.source_type,
                source_id=str(chunk.source_id) if chunk.source_id else None,
                content=chunk.content,
                # ✅ В модели теперь поле называется meta, а не metadata.
                metadata=chunk.meta or {},
            )
        )

    # 3. Запрашиваем ответ у roobert
    answer = await ask_roobert(payload.text, context_chunks)

    return AskOut(
        answer=answer,
        sources=sources,
        model_used=OLLAMA_MODEL,
    )