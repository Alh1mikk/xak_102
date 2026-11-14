import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.embedding import get_embedding

logger = logging.getLogger(__name__)

RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))


async def search_similar(
    db: AsyncSession,
    query: str,
    top_k: int | None = None,
    source_type: str | None = None,
) -> list[tuple[models.DocumentChunk, float]]:
    """Векторный поиск похожих чанков по cosine similarity.

    Возвращает список пар (чанк, расстояние), отсортированных по возрастанию расстояния.
    """
    k = top_k or RAG_TOP_K
    query_embedding = await get_embedding(query)

    conditions: list[str] = []
    embedding_str = "[" + ",".join(repr(float(x)) for x in query_embedding) + "]"
    params = {"embedding": embedding_str, "limit": k}
    if source_type:
        conditions.append("source_type = :source_type")
        params["source_type"] = source_type

    where_clause = " AND ".join(conditions) if conditions else "true"

    # pgvector.sqlalchemy сам сериализует list[float] в вектор при CAST.
    # Колонка в БД — vector(1024), колонка meta — JSONB.
    sql = f"""
        SELECT id, source_type, source_id, content, meta, created_at,
               embedding <=> CAST(:embedding AS vector) AS distance
        FROM document_chunks
        WHERE {where_clause}
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """

    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    found: list[tuple[models.DocumentChunk, float]] = []
    for row in rows:
        chunk = models.DocumentChunk(
            id=row.id,
            source_type=row.source_type,
            source_id=row.source_id,
            content=row.content,
            meta=row.meta,
            created_at=row.created_at,
            embedding=None,  # не загружаем обратно, экономим память
        )
        found.append((chunk, float(row.distance)))

    return found


async def index_chunks(
    db: AsyncSession,
    chunks: list[dict],
) -> int:
    """Проиндексировать список чанков.

    Каждый чанк: dict с ключами source_type, source_id, content, metadata, embedding.
    """
    from app.embedding import get_embeddings_batch

    texts = [c["content"] for c in chunks]
    embeddings = await get_embeddings_batch(texts)

    count = 0
    for chunk, embedding in zip(chunks, embeddings):
        db.add(
            models.DocumentChunk(
                source_type=chunk["source_type"],
                source_id=chunk.get("source_id"),
                content=chunk["content"],
                embedding=embedding,
                meta=chunk.get("metadata") or {},
            )
        )
        count += 1

    await db.flush()
    return count