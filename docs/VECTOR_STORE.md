# Phase 10 — Vector Store Architecture & FAISS Integration

## 1. Vector Store Abstraction
The system utilizes a clean `BaseVectorStore` interface to decouple application retrieval logic from concrete vector storage engines:

```python
class BaseVectorStore(ABC):
    @abstractmethod
    def add(self, case_id: UUID, ids: List[UUID], vectors: np.ndarray, metadata: Optional[List[Dict[str, Any]]] = None) -> None: ...
    
    @abstractmethod
    def search(self, case_id: UUID, query_vector: np.ndarray, top_k: int = 10, filter_ids: Optional[Set[UUID]] = None) -> List[Tuple[UUID, float]]: ...
    
    @abstractmethod
    def delete(self, case_id: UUID, ids: List[UUID]) -> None: ...
    
    @abstractmethod
    def rebuild(self, case_id: UUID, ids: List[UUID], vectors: np.ndarray, metadata: Optional[List[Dict[str, Any]]] = None) -> None: ...
    
    @abstractmethod
    def persist(self, case_id: UUID) -> None: ...
    
    @abstractmethod
    def load(self, case_id: UUID) -> bool: ...
    
    @abstractmethod
    def get_index_stats(self, case_id: UUID) -> Dict[str, Any]: ...
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]: ...
```

## 2. FAISS Engine Implementation (`FaissVectorStore`)
- **Index Type**: `faiss.IndexFlatIP` (Inner Product).
- **Similarity Metric**: Inner Product over unit L2-normalized vectors is mathematically identical to **Cosine Similarity** ($\cos(\theta) = \frac{u \cdot v}{||u||_2 ||v||_2} = u \cdot v$).
- **Score Mapping**: Raw inner products in $[-1.0, 1.0]$ are bounded and clamped to $[0.0, 1.0]$ for clean display in UI result badges.
- **Case Isolation**: Each case receives an isolated index partition on disk:
  ```
  storage/vector_index/{case_id}/
    ├── index.faiss     (FAISS binary index)
    ├── mapping.json    (Integer position -> UUID mapping array)
    └── metadata.json   (Model version, dimensions, timestamp, counts)
  ```

## 3. Atomic Rebuild Safety Pattern
When rebuilding an existing case vector index:
1. Vectors and UUID mappings are indexed into an isolated temporary directory (`{case_id}_rebuild_tmp/`).
2. The staging index and metadata are written and validated for count and dimension consistency.
3. Files are swapped into the target directory atomically using `os.replace(...)`.
4. In-memory case caches are refreshed under reentrant thread locks (`RLock`).

This guarantees **zero downtime** for ongoing queries during index rebuilding operations.

## 4. Fallback Engine (`NumpyVectorStore`)
If FAISS is unavailable or uninstalled in constrained environments, the factory automatically falls back to `NumpyVectorStore`, which computes exact dot-product cosine similarity over in-memory NumPy arrays with identical disk persistence semantics.
