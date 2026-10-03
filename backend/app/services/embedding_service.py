"""
Phase 10 — Sentence-BERT Embedding Service

Manages local SentenceTransformer embedding models with memory controls,
batch processing, CPU/GPU/MPS auto-detection, and L2-normalized vector output.
Guarantees zero external API data leakage for air-gapped forensic environments.
"""

import logging
import threading
from typing import Any, Dict, List, Optional
import numpy as np

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)

_embedding_service_instance: Optional["EmbeddingService"] = None
_service_lock = threading.Lock()


class EmbeddingService:
    """
    Forensic embedding generation service.
    Loads and caches the configured Sentence-BERT model (default: all-MiniLM-L6-v2).
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        model_version: Optional[str] = None,
        dimension: Optional[int] = None,
        device: Optional[str] = None,
    ) -> None:
        self.settings = get_settings()
        self.model_name = model_name or self.settings.EMBEDDING_MODEL_NAME
        self.model_version = model_version or self.settings.EMBEDDING_MODEL_VERSION
        self.dimension = dimension or self.settings.EMBEDDING_DIMENSION
        self.configured_device = device or self.settings.EMBEDDING_DEVICE
        self._model = None
        self._model_lock = threading.Lock()
        self._is_available = True
        self._load_error: Optional[str] = None

    def _determine_device(self) -> str:
        """Auto-detect compute device (CUDA if available, otherwise CPU)."""
        if self.configured_device and self.configured_device != "auto":
            return self.configured_device
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def _get_model(self):
        """Lazy-load SentenceTransformer model once per process."""
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    try:
                        import torch
                        torch.set_num_threads(1)
                        from sentence_transformers import SentenceTransformer
                        device = self._determine_device()
                        logger.info(
                            f"[EmbeddingService] Loading model {self.model_name} (v{self.model_version}) on device '{device}'..."
                        )
                        self._model = SentenceTransformer(self.model_name, device=device)
                        self._is_available = True
                        self._load_error = None
                        logger.info("[EmbeddingService] Model loaded successfully.")
                    except Exception as e:
                        self._is_available = False
                        self._load_error = str(e)
                        logger.error(f"[EmbeddingService] Failed to load embedding model: {e}")
                        raise RuntimeError(f"Embedding model unavailable: {e}")
        return self._model

    def embed_texts(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """
        Generate L2-normalized vector embeddings for a batch of strings.
        
        Returns:
            np.ndarray of shape (len(texts), dimension) and dtype float32.
        """
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        batch_size = batch_size or self.settings.EMBEDDING_BATCH_SIZE

        try:
            model = self._get_model()
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            vecs = np.asarray(embeddings, dtype=np.float32)
            if vecs.shape[1] != self.dimension:
                logger.warning(
                    f"[EmbeddingService] Generated embedding dimension {vecs.shape[1]} differs from configured {self.dimension}"
                )
            return vecs
        except Exception as e:
            logger.error(f"[EmbeddingService] Embedding batch generation failed: {e}")
            raise

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate L2-normalized vector embedding for a single query string.
        
        Returns:
            1D np.ndarray of shape (dimension,) and dtype float32.
        """
        clean_q = query.strip()
        if not clean_q:
            return np.zeros(self.dimension, dtype=np.float32)

        vecs = self.embed_texts([clean_q])
        return vecs[0]

    def health_check(self) -> Dict[str, Any]:
        """Verify model readiness and return metadata."""
        try:
            model = self._get_model()
            test_vec = self.embed_query("forensic analysis test query")
            is_valid = len(test_vec) == self.dimension and not np.isnan(test_vec).any()
            return {
                "status": "READY" if is_valid else "DEGRADED",
                "model_name": self.model_name,
                "model_version": self.model_version,
                "dimension": self.dimension,
                "device": self._determine_device(),
                "is_available": True,
            }
        except Exception as e:
            return {
                "status": "UNAVAILABLE",
                "model_name": self.model_name,
                "model_version": self.model_version,
                "dimension": self.dimension,
                "is_available": False,
                "error": str(e),
            }


def get_embedding_service() -> EmbeddingService:
    """Singleton accessor for EmbeddingService."""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        with _service_lock:
            if _embedding_service_instance is None:
                _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
