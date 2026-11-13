import logging
import threading
from typing import List, Optional

from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 384


class EmbeddingService:
    """Thread-safe singleton wrapper around SentenceTransformer (loaded once and reused)."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._model: Optional[SentenceTransformer] = None
        self._lock = threading.Lock()

    def get_model(self) -> SentenceTransformer:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    logger.info("Loading embedding model once: %s", self.model_name)
                    self._model = SentenceTransformer(self.model_name)
                    get_dim = getattr(
                        self._model,
                        "get_embedding_dimension",
                        self._model.get_sentence_embedding_dimension,
                    )
                    dim = get_dim()
                    logger.info("Embedding model loaded successfully (dimension=%s)", dim)
        return self._model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self.get_model()
        vectors = model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [vec.tolist() for vec in vectors]

    def embed_query(self, query: str) -> List[float]:
        vectors = self.embed_texts([query])
        return vectors[0]


embedding_service = EmbeddingService()
