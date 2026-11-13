import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.rag.embeddings import embedding_service
from app.services.rag.vector_store import vector_store

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: int
    source_filename: str
    title: str
    category: str
    page_number: int
    chunk_index: int
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    query: str
    chunks: List[RetrievedChunk] = field(default_factory=list)
    context_text: str = ""
    total_candidates: int = 0
    retained_count: int = 0
    threshold: float = 0.28

    @property
    def has_relevant_docs(self) -> bool:
        return len(self.chunks) > 0


def retrieve_relevant_context(
    query: str,
    top_k: Optional[int] = None,
    min_score: Optional[float] = None,
    category: Optional[str] = None,
    max_context_chars: Optional[int] = None,
) -> RetrievalResult:
    """
    Executes steps 2-6 of the RAG pipeline:
    1. Generate query embedding via singleton EmbeddingService.
    2. Search persistent ChromaDB vector store.
    3. Filter candidates against the configured cosine similarity threshold.
    4. Construct bounded grounded context string preserving filename & page citations.
    """
    cleaned_query = (query or "").strip()
    effective_top_k = top_k if top_k is not None else settings.RAG_TOP_K
    effective_threshold = (
        min_score if min_score is not None else settings.RAG_RELEVANCE_THRESHOLD
    )
    effective_max_chars = (
        max_context_chars if max_context_chars is not None else settings.RAG_MAX_CONTEXT_CHARS
    )

    if not cleaned_query:
        return RetrievalResult(query=cleaned_query, threshold=effective_threshold)

    # Skip heavy embedding model initialization when vector store has no indexed chunks
    if vector_store.count() == 0:
        return RetrievalResult(query=cleaned_query, threshold=effective_threshold)

    query_embedding = embedding_service.embed_query(cleaned_query)
    if not query_embedding:
        return RetrievalResult(query=cleaned_query, threshold=effective_threshold)

    raw_candidates = vector_store.search(
        query_embedding=query_embedding,
        top_k=max(1, effective_top_k),
        category=category,
    )

    filtered: List[RetrievedChunk] = []
    for item in raw_candidates:
        score = float(item.get("score", 0.0))
        if score < effective_threshold:
            continue
        filtered.append(
            RetrievedChunk(
                chunk_id=str(item["chunk_id"]),
                document_id=int(item["document_id"]),
                source_filename=str(item["source_filename"]),
                title=str(item["title"]),
                category=str(item.get("category") or "general"),
                page_number=int(item.get("page_number") or 1),
                chunk_index=int(item.get("chunk_index") or 0),
                text=str(item["text"]),
                score=score,
                metadata=dict(item.get("metadata") or {}),
            )
        )

    # Sort descending by relevance score
    filtered.sort(key=lambda c: c.score, reverse=True)

    # Construct grounded context string within character budget
    context_blocks: List[str] = []
    used_chars = 0
    retained_chunks: List[RetrievedChunk] = []

    for idx, chunk in enumerate(filtered, start=1):
        block = (
            f"[Source {idx}] File: {chunk.source_filename} | Page: {chunk.page_number} | "
            f"Title: {chunk.title} | Category: {chunk.category} | Relevance: {chunk.score:.2f}\n"
            f"{chunk.text}"
        )
        separator_len = 2 if context_blocks else 0
        if used_chars + separator_len + len(block) > effective_max_chars:
            if not context_blocks:
                # Truncate first oversized block rather than returning empty context
                allowed = max(200, effective_max_chars - 50)
                context_blocks.append(block[:allowed] + "...")
                retained_chunks.append(chunk)
            break
        context_blocks.append(block)
        retained_chunks.append(chunk)
        used_chars += separator_len + len(block)

    logger.info(
        "RAG retrieval completed: candidates=%d retained=%d threshold=%.2f",
        len(raw_candidates),
        len(retained_chunks),
        effective_threshold,
    )

    return RetrievalResult(
        query=cleaned_query,
        chunks=retained_chunks,
        context_text="\n\n---\n\n".join(context_blocks),
        total_candidates=len(raw_candidates),
        retained_count=len(retained_chunks),
        threshold=effective_threshold,
    )
