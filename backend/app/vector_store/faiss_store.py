"""
Phase 10 — FAISS Vector Storage Engine

High-performance, case-isolated vector storage using Facebook AI Similarity Search (FAISS).
Uses Inner Product over L2-normalized embeddings (equivalent to Cosine Similarity).
Maintains bidirectional UUID mappings and index metadata on disk with atomic rebuild safety.
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import json
import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

import faiss
import numpy as np

from backend.app.core.config import get_settings
from backend.app.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class FaissCaseIndex:
    """Encapsulates a single case's FAISS index and UUID mapping."""

    def __init__(self, case_id: UUID, dimension: int, index_dir: Path):
        self.case_id = case_id
        self.dimension = dimension
        self.index_dir = index_dir
        self.case_dir = index_dir / str(case_id)
        self.index_path = self.case_dir / "index.faiss"
        self.mapping_path = self.case_dir / "mapping.json"
        self.metadata_path = self.case_dir / "metadata.json"
        self.lock = threading.RLock()

        # In-memory structures
        # IndexFlatIP calculates inner product: for unit-normalized vectors, this equals cosine similarity
        self.index: faiss.Index = faiss.IndexFlatIP(dimension)
        self.id_list: List[UUID] = []
        self.id_to_idx: Dict[str, int] = {}
        self.metadata: Dict[str, Any] = {
            "case_id": str(case_id),
            "dimension": dimension,
            "metric": "INNER_PRODUCT_NORMALIZED_COSINE",
            "model_name": get_settings().EMBEDDING_MODEL_NAME,
            "model_version": get_settings().EMBEDDING_MODEL_VERSION,
            "total_records": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def ensure_dir(self) -> None:
        self.case_dir.mkdir(parents=True, exist_ok=True)

    def persist(self) -> None:
        with self.lock:
            self.ensure_dir()
            faiss.write_index(self.index, str(self.index_path))
            with open(self.mapping_path, "w", encoding="utf-8") as f:
                json.dump([str(u) for u in self.id_list], f)
            self.metadata["total_records"] = len(self.id_list)
            self.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2)

    def load(self) -> bool:
        with self.lock:
            if not self.index_path.exists() or not self.mapping_path.exists():
                return False
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.mapping_path, "r", encoding="utf-8") as f:
                    raw_ids = json.load(f)
                    self.id_list = [UUID(i) for i in raw_ids]
                    self.id_to_idx = {str(uid): idx for idx, uid in enumerate(self.id_list)}
                if self.metadata_path.exists():
                    with open(self.metadata_path, "r", encoding="utf-8") as f:
                        self.metadata = json.load(f)
                return True
            except Exception as e:
                logger.error(f"[FaissVectorStore] Failed to load index for case {self.case_id}: {e}")
                return False


class FaissVectorStore(BaseVectorStore):
    """
    Case-isolated FAISS vector store implementation.
    Manages multiple case indices in memory with automatic disk persistence and cache-loading.
    """

    def __init__(
        self,
        index_dir: Optional[str] = None,
        dimension: Optional[int] = None,
    ) -> None:
        self.settings = get_settings()
        self.dimension = dimension or self.settings.EMBEDDING_DIMENSION
        self.index_dir = Path(index_dir or self.settings.VECTOR_INDEX_DIR)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._cases: Dict[UUID, FaissCaseIndex] = {}
        self._global_lock = threading.RLock()

    def _get_case_index(self, case_id: UUID) -> FaissCaseIndex:
        with self._global_lock:
            if case_id not in self._cases:
                case_idx = FaissCaseIndex(case_id, self.dimension, self.index_dir)
                case_idx.load()
                self._cases[case_id] = case_idx
            return self._cases[case_id]

    @staticmethod
    def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
        """L2-normalize vectors safely using numpy."""
        vecs = np.ascontiguousarray(vectors, dtype=np.float32)
        if len(vecs.shape) == 1:
            vecs = vecs.reshape(1, -1)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (vecs / norms).astype(np.float32)

    def add(
        self,
        case_id: UUID,
        ids: List[UUID],
        vectors: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        if len(ids) == 0:
            return

        case_idx = self._get_case_index(case_id)
        vectors = self._normalize_vectors(vectors)

        if vectors.shape[1] != self.dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.dimension}, got {vectors.shape[1]}"
            )

        with case_idx.lock:
            # Check for existing IDs and replace or append
            for i, uid in enumerate(ids):
                uid_str = str(uid)
                case_idx.id_list.append(uid)
                case_idx.id_to_idx[uid_str] = len(case_idx.id_list) - 1

            case_idx.index.add(vectors)
            case_idx.persist()

    def search(
        self,
        case_id: UUID,
        query_vector: np.ndarray,
        top_k: int = 10,
        filter_ids: Optional[Set[UUID]] = None,
    ) -> List[Tuple[UUID, float]]:
        case_idx = self._get_case_index(case_id)
        with case_idx.lock:
            total = case_idx.index.ntotal
            if total == 0 or len(case_idx.id_list) == 0:
                return []

            q_vec = self._normalize_vectors(query_vector)

            # Cap search k to actual number of indexed vectors
            k_search = min(max(top_k * 3, 20), total)
            distances, indices = case_idx.index.search(q_vec, k_search)

            results: List[Tuple[UUID, float]] = []
            seen: Set[UUID] = set()

            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0 or idx >= len(case_idx.id_list):
                    continue
                record_id = case_idx.id_list[idx]
                if record_id in seen:
                    continue
                if filter_ids is not None and record_id not in filter_ids:
                    continue

                seen.add(record_id)
                # Cosine similarity is bounded in [-1.0, 1.0], clamp to [0.0, 1.0] for similarity score
                similarity = float(np.clip((dist + 1.0) / 2.0, 0.0, 1.0)) if dist < 0 else float(min(dist, 1.0))
                results.append((record_id, similarity))
                if len(results) >= top_k:
                    break

            return results

    def delete(
        self,
        case_id: UUID,
        ids: List[UUID],
    ) -> None:
        case_idx = self._get_case_index(case_id)
        with case_idx.lock:
            id_set = {str(u) for u in ids}
            keep_indices = [i for i, u in enumerate(case_idx.id_list) if str(u) not in id_set]
            if len(keep_indices) == len(case_idx.id_list):
                return  # Nothing to delete

            # Reconstruct remaining vectors
            if len(keep_indices) > 0:
                reconstructed = np.zeros((len(keep_indices), self.dimension), dtype=np.float32)
                for new_pos, old_pos in enumerate(keep_indices):
                    reconstructed[new_pos] = case_idx.index.reconstruct(old_pos)

                new_index = faiss.IndexFlatIP(self.dimension)
                new_index.add(reconstructed)
                case_idx.index = new_index
                case_idx.id_list = [case_idx.id_list[i] for i in keep_indices]
                case_idx.id_to_idx = {str(u): i for i, u in enumerate(case_idx.id_list)}
            else:
                case_idx.index = faiss.IndexFlatIP(self.dimension)
                case_idx.id_list = []
                case_idx.id_to_idx = {}

            case_idx.persist()

    def persist(self, case_id: UUID) -> None:
        case_idx = self._get_case_index(case_id)
        case_idx.persist()

    def load(self, case_id: UUID) -> bool:
        case_idx = self._get_case_index(case_id)
        return case_idx.load()

    def rebuild(
        self,
        case_id: UUID,
        ids: List[UUID],
        vectors: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Atomic rebuild safety pattern:
        1. Builds temp index & temp mappings in a staging directory.
        2. Validates vector count and dimension.
        3. Atomically replaces case index files.
        """
        if len(ids) != len(vectors):
            raise ValueError(f"IDs count ({len(ids)}) does not match vectors count ({len(vectors)})")

        case_dir = self.index_dir / str(case_id)
        tmp_dir = self.index_dir / f"{case_id}_rebuild_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        try:
            tmp_index = faiss.IndexFlatIP(self.dimension)
            if len(vectors) > 0:
                vecs = self._normalize_vectors(vectors)
                tmp_index.add(vecs)

            # Persist to temp staging
            tmp_index_path = tmp_dir / "index.faiss"
            tmp_mapping_path = tmp_dir / "mapping.json"
            tmp_meta_path = tmp_dir / "metadata.json"

            faiss.write_index(tmp_index, str(tmp_index_path))
            with open(tmp_mapping_path, "w", encoding="utf-8") as f:
                json.dump([str(u) for u in ids], f)

            meta = {
                "case_id": str(case_id),
                "dimension": self.dimension,
                "metric": "INNER_PRODUCT_NORMALIZED_COSINE",
                "model_name": self.settings.EMBEDDING_MODEL_NAME,
                "model_version": self.settings.EMBEDDING_MODEL_VERSION,
                "total_records": len(ids),
                "rebuilt_at": datetime.now(timezone.utc).isoformat(),
            }
            if metadata:
                meta["extra"] = metadata

            with open(tmp_meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            # Atomic swap
            case_dir.mkdir(parents=True, exist_ok=True)
            os.replace(str(tmp_index_path), str(case_dir / "index.faiss"))
            os.replace(str(tmp_mapping_path), str(case_dir / "mapping.json"))
            os.replace(str(tmp_meta_path), str(case_dir / "metadata.json"))

            # Refresh in-memory cache
            with self._global_lock:
                case_idx = FaissCaseIndex(case_id, self.dimension, self.index_dir)
                case_idx.load()
                self._cases[case_id] = case_idx

            logger.info(f"[FaissVectorStore] Successfully rebuilt vector index for case {case_id} ({len(ids)} records)")

        finally:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def get_index_stats(self, case_id: UUID) -> Dict[str, Any]:
        case_idx = self._get_case_index(case_id)
        with case_idx.lock:
            return {
                "case_id": str(case_id),
                "dimension": self.dimension,
                "total_vectors": case_idx.index.ntotal,
                "mapped_ids_count": len(case_idx.id_list),
                "index_file_exists": case_idx.index_path.exists(),
                "file_size_bytes": case_idx.index_path.stat().st_size if case_idx.index_path.exists() else 0,
                "metadata": case_idx.metadata,
                "is_consistent": case_idx.index.ntotal == len(case_idx.id_list),
            }

    def health_check(self) -> Dict[str, Any]:
        try:
            test_idx = faiss.IndexFlatIP(self.dimension)
            test_vec = np.random.rand(1, self.dimension).astype(np.float32)
            test_vec = self._normalize_vectors(test_vec)
            test_idx.add(test_vec)
            _, ind = test_idx.search(test_vec, 1)
            healthy = ind[0][0] == 0
            return {
                "status": "HEALTHY" if healthy else "DEGRADED",
                "engine": "FAISS",
                "dimension": self.dimension,
                "index_dir": str(self.index_dir),
                "active_cases_cached": len(self._cases),
            }
        except Exception as e:
            return {
                "status": "UNHEALTHY",
                "engine": "FAISS",
                "error": str(e),
            }
