"""
Phase 10 — Vector Store Abstraction

Defines the abstract interface for forensic vector storage engines.
Decouples application logic from specific vector index implementations
(e.g., FAISS, HNSW, pgvector, NumPy).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID
import numpy as np


class BaseVectorStore(ABC):
    """
    Abstract forensic vector storage interface.
    All vector storage engines must guarantee strict case-scoping,
    persistence, atomic rebuild safety, and bidirectional vector-to-canonical-ID mappings.
    """

    @abstractmethod
    def add(
        self,
        case_id: UUID,
        ids: List[UUID],
        vectors: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Add normalized vectors with their corresponding canonical evidence UUIDs to the case index.
        """
        pass

    @abstractmethod
    def search(
        self,
        case_id: UUID,
        query_vector: np.ndarray,
        top_k: int = 10,
        filter_ids: Optional[Set[UUID]] = None,
    ) -> List[Tuple[UUID, float]]:
        """
        Search for nearest vectors within the specified case.
        Returns ordered list of (canonical_evidence_id, similarity_score).
        """
        pass

    @abstractmethod
    def delete(
        self,
        case_id: UUID,
        ids: List[UUID],
    ) -> None:
        """
        Remove vectors associated with the given canonical evidence IDs from the case index.
        """
        pass

    @abstractmethod
    def persist(self, case_id: UUID) -> None:
        """
        Persist in-memory vector index to permanent disk storage.
        """
        pass

    @abstractmethod
    def load(self, case_id: UUID) -> bool:
        """
        Load persisted vector index from disk storage into memory.
        Returns True if loaded, False if index file does not exist.
        """
        pass

    @abstractmethod
    def rebuild(
        self,
        case_id: UUID,
        ids: List[UUID],
        vectors: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Atomically rebuild the vector index for a case using atomic switch pattern.
        """
        pass

    @abstractmethod
    def get_index_stats(self, case_id: UUID) -> Dict[str, Any]:
        """
        Retrieve index metadata, dimension, record count, and memory footprint.
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Verify vector storage subsystem availability and health status.
        """
        pass
