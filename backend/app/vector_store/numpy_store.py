"""
Phase 10 — Pure NumPy Vector Storage Engine (Fallback)

Provides an exact in-memory / file-persisted vector store using pure NumPy cosine similarity.
Used as fallback or lightweight testing harness.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID
import numpy as np

from backend.app.core.config import get_settings
from backend.app.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class NumpyVectorStore(BaseVectorStore):
    """Pure NumPy cosine similarity vector storage."""

    def __init__(
        self,
        index_dir: Optional[str] = None,
        dimension: Optional[int] = None,
    ) -> None:
        self.settings = get_settings()
        self.dimension = dimension or self.settings.EMBEDDING_DIMENSION
        self.index_dir = Path(index_dir or self.settings.VECTOR_INDEX_DIR)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._cases_vecs: Dict[UUID, np.ndarray] = {}
        self._cases_ids: Dict[UUID, List[UUID]] = {}
        self._lock = threading.RLock()

    def _ensure_case(self, case_id: UUID) -> None:
        if case_id not in self._cases_vecs:
            self._cases_vecs[case_id] = np.zeros((0, self.dimension), dtype=np.float32)
            self._cases_ids[case_id] = []
            self.load(case_id)

    def add(
        self,
        case_id: UUID,
        ids: List[UUID],
        vectors: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        if len(ids) == 0:
            return
        with self._lock:
            self._ensure_case(case_id)
            vecs = np.asarray(vectors, dtype=np.float32)
            if len(vecs.shape) == 1:
                vecs = vecs.reshape(1, -1)

            # Normalize
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            norm_vecs = vecs / norms

            self._cases_vecs[case_id] = (
                np.vstack([self._cases_vecs[case_id], norm_vecs])
                if self._cases_vecs[case_id].shape[0] > 0
                else norm_vecs
            )
            self._cases_ids[case_id].extend(ids)
            self.persist(case_id)

    def search(
        self,
        case_id: UUID,
        query_vector: np.ndarray,
        top_k: int = 10,
        filter_ids: Optional[Set[UUID]] = None,
    ) -> List[Tuple[UUID, float]]:
        with self._lock:
            self._ensure_case(case_id)
            mat = self._cases_vecs[case_id]
            ids = self._cases_ids[case_id]

            if mat.shape[0] == 0:
                return []

            q = np.asarray(query_vector, dtype=np.float32)
            if len(q.shape) == 1:
                q = q.reshape(1, -1)
            norm = np.linalg.norm(q)
            if norm > 0:
                q = q / norm

            # Dot product with normalized matrix
            scores = np.dot(mat, q.T).flatten()

            # Rank
            sorted_indices = np.argsort(-scores)
            results: List[Tuple[UUID, float]] = []
            seen: Set[UUID] = set()

            for idx in sorted_indices:
                uid = ids[idx]
                if uid in seen:
                    continue
                if filter_ids is not None and uid not in filter_ids:
                    continue
                seen.add(uid)
                sc = float(scores[idx])
                results.append((uid, max(0.0, min(1.0, (sc + 1.0) / 2.0 if sc < 0 else sc))))
                if len(results) >= top_k:
                    break

            return results

    def delete(
        self,
        case_id: UUID,
        ids: List[UUID],
    ) -> None:
        with self._lock:
            self._ensure_case(case_id)
            id_set = set(ids)
            keep_idx = [i for i, uid in enumerate(self._cases_ids[case_id]) if uid not in id_set]
            if len(keep_idx) == len(self._cases_ids[case_id]):
                return
            if len(keep_idx) > 0:
                self._cases_vecs[case_id] = self._cases_vecs[case_id][keep_idx]
                self._cases_ids[case_id] = [self._cases_ids[case_id][i] for i in keep_idx]
            else:
                self._cases_vecs[case_id] = np.zeros((0, self.dimension), dtype=np.float32)
                self._cases_ids[case_id] = []
            self.persist(case_id)

    def persist(self, case_id: UUID) -> None:
        case_dir = self.index_dir / str(case_id)
        case_dir.mkdir(parents=True, exist_ok=True)
        np.save(case_dir / "vectors.npy", self._cases_vecs.get(case_id, np.zeros((0, self.dimension))))
        with open(case_dir / "ids.json", "w", encoding="utf-8") as f:
            json.dump([str(u) for u in self._cases_ids.get(case_id, [])], f)

    def load(self, case_id: UUID) -> bool:
        case_dir = self.index_dir / str(case_id)
        vec_file = case_dir / "vectors.npy"
        id_file = case_dir / "ids.json"
        if vec_file.exists() and id_file.exists():
            try:
                self._cases_vecs[case_id] = np.load(vec_file)
                with open(id_file, "r", encoding="utf-8") as f:
                    self._cases_ids[case_id] = [UUID(i) for i in json.load(f)]
                return True
            except Exception as e:
                logger.error(f"[NumpyVectorStore] Failed to load index for case {case_id}: {e}")
                return False
        return False

    def rebuild(
        self,
        case_id: UUID,
        ids: List[UUID],
        vectors: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        with self._lock:
            vecs = np.asarray(vectors, dtype=np.float32)
            if len(vecs.shape) == 1:
                vecs = vecs.reshape(1, -1)
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._cases_vecs[case_id] = vecs / norms
            self._cases_ids[case_id] = list(ids)
            self.persist(case_id)

    def get_index_stats(self, case_id: UUID) -> Dict[str, Any]:
        with self._lock:
            self._ensure_case(case_id)
            return {
                "case_id": str(case_id),
                "dimension": self.dimension,
                "total_vectors": self._cases_vecs[case_id].shape[0],
                "mapped_ids_count": len(self._cases_ids[case_id]),
                "engine": "NUMPY",
            }

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "engine": "NUMPY",
            "dimension": self.dimension,
            "active_cases_cached": len(self._cases_vecs),
        }
