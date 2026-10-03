"""
Phase 10 — Vector Store Factory & Exports
"""

import logging
from typing import Optional
from backend.app.core.config import get_settings
from backend.app.vector_store.base import BaseVectorStore
from backend.app.vector_store.faiss_store import FaissVectorStore
from backend.app.vector_store.numpy_store import NumpyVectorStore

logger = logging.getLogger(__name__)

_vector_store_instance: Optional[BaseVectorStore] = None


def get_vector_store() -> BaseVectorStore:
    """
    Singleton factory for vector storage engine.
    Prefers FaissVectorStore with automatic fallback to NumpyVectorStore if FAISS encounters errors.
    """
    global _vector_store_instance
    if _vector_store_instance is None:
        try:
            store = FaissVectorStore()
            health = store.health_check()
            if health["status"] == "HEALTHY":
                _vector_store_instance = store
            else:
                logger.warning("[VectorStore] FAISS health check degraded, falling back to NumPy store")
                _vector_store_instance = NumpyVectorStore()
        except Exception as e:
            logger.warning(f"[VectorStore] Could not initialize FAISS vector store ({e}), falling back to NumPy store")
            _vector_store_instance = NumpyVectorStore()
    return _vector_store_instance


__all__ = [
    "BaseVectorStore",
    "FaissVectorStore",
    "NumpyVectorStore",
    "get_vector_store",
]
