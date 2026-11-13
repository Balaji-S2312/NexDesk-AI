import logging
import os
import threading
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 384

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def _is_low_memory_container() -> bool:
    """Detect constrained cloud containers (e.g. Render 512 MB free tier) via env or cgroup limits."""
    env_flag = os.getenv("LOW_MEMORY_EMBEDDINGS", "").strip().lower()
    if env_flag in ("1", "true", "yes"):
        return True
    if env_flag in ("0", "false", "no"):
        return False

    limit_mb_threshold = 768 * 1024 * 1024
    for cgroup_path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            with open(cgroup_path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if raw and raw != "max":
                val = int(raw)
                if 0 < val <= limit_mb_threshold:
                    return True
        except Exception:
            continue
    return False


class EmbeddingService:
    """Thread-safe singleton wrapper around all-MiniLM-L6-v2 (SentenceTransformer or ONNX in low-RAM mode)."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._model = None
        self._onnx_ef = None
        self._lock = threading.Lock()

    def get_model(self):
        if _is_low_memory_container():
            if self._onnx_ef is None:
                with self._lock:
                    if self._onnx_ef is None:
                        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

                        logger.info("Low-memory container detected; initializing ONNX all-MiniLM-L6-v2")
                        self._onnx_ef = ONNXMiniLM_L6_V2()
            return self._onnx_ef

        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

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
        if self._onnx_ef is not None and model is self._onnx_ef:
            vectors = model(texts)
            return [vec.tolist() if hasattr(vec, "tolist") else list(vec) for vec in vectors]

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
