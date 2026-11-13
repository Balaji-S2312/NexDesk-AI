import logging
import os
import threading
from typing import Any, Dict, List, Optional

import chromadb

from app.core.config import settings
from app.services.rag.chunker import TextChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "nexdesk_knowledge"


class ChromaVectorStore:
    """Persistent ChromaDB wrapper for storing and querying document chunk embeddings."""

    def __init__(self, persist_directory: Optional[str] = None, collection_name: str = COLLECTION_NAME):
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIRECTORY
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._lock = threading.Lock()

    def _get_collection(self):
        if self._collection is None:
            with self._lock:
                if self._collection is None:
                    os.makedirs(self.persist_directory, exist_ok=True)
                    self._client = chromadb.PersistentClient(path=self.persist_directory)
                    self._collection = self._client.get_or_create_collection(
                        name=self.collection_name,
                        metadata={"hnsw:space": "cosine"},
                    )
                    logger.info(
                        "Initialized persistent ChromaDB collection '%s' at %s",
                        self.collection_name,
                        self.persist_directory,
                    )
        return self._collection

    def add_document_chunks(
        self,
        document_id: int,
        source_filename: str,
        title: str,
        category: str,
        chunks: List[TextChunk],
        embeddings: List[List[float]],
    ) -> int:
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError("Mismatch between chunks count and embeddings count")

        collection = self._get_collection()
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for chunk in chunks:
            chunk_id = f"doc_{document_id}_chunk_{chunk.chunk_index}"
            ids.append(chunk_id)
            documents.append(chunk.text)
            metadatas.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": int(document_id),
                    "chunk_index": int(chunk.chunk_index),
                    "source_filename": source_filename,
                    "title": title,
                    "category": category,
                    "page_number": int(chunk.page_number),
                    "token_count": int(chunk.token_count),
                }
            )

        # Upsert in batches to stay safe on large documents
        batch_size = 100
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            collection.upsert(
                ids=ids[start:end],
                embeddings=embeddings[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )
        return len(ids)

    def count(self) -> int:
        return int(self._get_collection().count())

    def delete_document_chunks(self, document_id: int) -> int:
        collection = self._get_collection()
        existing = collection.get(where={"document_id": int(document_id)}, include=[])
        existing_ids = existing.get("ids") or []
        if existing_ids:
            collection.delete(where={"document_id": int(document_id)})
        return len(existing_ids)

    def get_document_chunks(
        self, document_id: int, include_embeddings: bool = False
    ) -> List[Dict[str, Any]]:
        collection = self._get_collection()
        includes = ["documents", "metadatas"]
        if include_embeddings:
            includes.append("embeddings")
        res = collection.get(
            where={"document_id": int(document_id)},
            include=includes,
        )
        ids = res.get("ids") or []
        docs = res.get("documents") or []
        metas = res.get("metadatas") or []
        embeds = res.get("embeddings") if include_embeddings else None

        items: List[Dict[str, Any]] = []
        for idx, (cid, doc, meta) in enumerate(zip(ids, docs, metas)):
            item: Dict[str, Any] = {"chunk_id": cid, "text": doc, "metadata": meta}
            if embeds is not None and idx < len(embeds):
                item["embedding"] = list(embeds[idx])
            items.append(item)
        items.sort(key=lambda x: x["metadata"].get("chunk_index", 0))
        return items

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        category: Optional[str] = None,
        document_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        collection = self._get_collection()
        total_count = collection.count()
        if total_count == 0:
            return []

        where_clauses: List[Dict[str, Any]] = []
        if category and category != "all":
            where_clauses.append({"category": category})
        if document_id is not None:
            where_clauses.append({"document_id": int(document_id)})

        where_filter: Optional[Dict[str, Any]] = None
        if len(where_clauses) == 1:
            where_filter = where_clauses[0]
        elif len(where_clauses) > 1:
            where_filter = {"$and": where_clauses}

        n_results = min(max(1, top_k), total_count)
        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter is not None:
            kwargs["where"] = where_filter

        res = collection.query(**kwargs)
        ids_list = (res.get("ids") or [[]])[0]
        docs_list = (res.get("documents") or [[]])[0]
        metas_list = (res.get("metadatas") or [[]])[0]
        dists_list = (res.get("distances") or [[]])[0]

        results: List[Dict[str, Any]] = []
        for cid, doc, meta, dist in zip(ids_list, docs_list, metas_list, dists_list):
            score = round(max(0.0, min(1.0, 1.0 - float(dist))), 4)
            results.append(
                {
                    "chunk_id": cid,
                    "document_id": int(meta.get("document_id", 0)),
                    "source_filename": str(meta.get("source_filename", "")),
                    "title": str(meta.get("title", "")),
                    "category": str(meta.get("category", "general")),
                    "page_number": int(meta.get("page_number", 1)),
                    "chunk_index": int(meta.get("chunk_index", 0)),
                    "text": doc,
                    "score": score,
                    "metadata": meta,
                }
            )
        return results

    def reset_for_testing(self, persist_directory: str) -> None:
        """Switches storage directory (used by pytest for isolated vector store runs)."""
        with self._lock:
            self.persist_directory = persist_directory
            self._client = None
            self._collection = None


vector_store = ChromaVectorStore()
