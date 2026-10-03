"""
Phase 9 — Forensic Search Engine: Request & Response Schemas

Defines:
  - ForensicSearchRequest: validated search parameters
  - SearchResultItem: per-record result with traceability fields
  - SearchFacets: optional aggregate counts per artifact type
  - ForensicSearchResponse: paginated search response
  - SearchHistoryItem: lightweight search history entry
  - SearchHistoryResponse: paginated search history
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.models.enums import ArtifactType, DataQualityStatus, SearchMode, TimestampPrecision

# ------------------------------------------------------------------ #
# Constants                                                           #
# ------------------------------------------------------------------ #

MAX_QUERY_LENGTH = 500
MAX_SEARCH_PAGE_SIZE = 100

ALLOWED_SORT_FIELDS = {
    "timestamp_asc",
    "timestamp_desc",
    "created_at_asc",
    "created_at_desc",
    "artifact_type",
    "similarity",
    "similarity_desc",
}


# ------------------------------------------------------------------ #
# Source traceability block                                           #
# ------------------------------------------------------------------ #

class SearchResultSource(BaseModel):
    """Forensic provenance for a single search result."""
    evidence_id: UUID
    raw_artifact_id: UUID
    source_file: str
    source_path: str
    record_identifier: str


# ------------------------------------------------------------------ #
# Per-result item                                                     #
# ------------------------------------------------------------------ #

class SearchResultItem(BaseModel):
    """
    Single forensic search result.

    Returns a concise summary suitable for a result list.
    Full canonical detail is available via the existing
    GET /cases/{case_id}/canonical-records/{record_id} endpoint.
    """
    id: UUID
    artifact_type: ArtifactType
    event_timestamp: Optional[datetime] = None
    timestamp_precision: Optional[TimestampPrecision] = None
    application: Optional[str] = None
    device_id: Optional[str] = None
    # Short content preview (first 300 chars of content field, never modified)
    content_preview: Optional[str] = None
    # Matched entities for entity-based search (list of entity dicts)
    matched_entities: List[Dict[str, Any]] = Field(default_factory=list)
    data_quality_status: Optional[DataQualityStatus] = None
    # How this result was matched
    match_type: str = "FILTER_MATCH"  # EXACT_MATCH | TEXT_MATCH | FILTER_MATCH | SEMANTIC_MATCH | HYBRID_MATCH
    # Semantic retrieval score (Cosine similarity or combined rank score)
    similarity_score: Optional[float] = None
    # Explanatory provenance why this item was retrieved (e.g. "Matched via Semantic similarity (0.84)")
    retrieval_explanation: Optional[str] = None
    source: SearchResultSource


# ------------------------------------------------------------------ #
# Facets                                                              #
# ------------------------------------------------------------------ #

class SearchFacets(BaseModel):
    """
    Optional aggregate counts by artifact type for the current result set.
    Counts come from real DB aggregate queries — never invented.
    """
    by_artifact_type: Dict[str, int] = Field(default_factory=dict)
    total_matched: int = 0


# ------------------------------------------------------------------ #
# Pagination envelope                                                 #
# ------------------------------------------------------------------ #

class SearchPagination(BaseModel):
    next_cursor: Optional[str] = None
    has_more: bool = False
    page_size: int


# ------------------------------------------------------------------ #
# Full search response                                                #
# ------------------------------------------------------------------ #

class ForensicSearchResponse(BaseModel):
    """
    Paginated forensic search response.

    results: matching canonical evidence records (summary view)
    facets: optional aggregate counts (only when include_facets=True)
    pagination: cursor-based navigation
    """
    results: List[SearchResultItem]
    facets: Optional[SearchFacets] = None
    pagination: SearchPagination
    search_mode: SearchMode = SearchMode.LEXICAL
    # Wall-clock search duration on server (milliseconds)
    duration_ms: int = 0


# ------------------------------------------------------------------ #
# Search history                                                      #
# ------------------------------------------------------------------ #

class SearchHistoryItem(BaseModel):
    """Lightweight search history entry for display."""
    id: UUID
    query: Optional[str] = None
    filters_json: Optional[str] = None
    result_count: Optional[int] = None
    executed_at: datetime
    duration_ms: Optional[int] = None


class SearchHistoryResponse(BaseModel):
    items: List[SearchHistoryItem]
    total: int


# ------------------------------------------------------------------ #
# Embedding & Vector Subsystem Schemas                                #
# ------------------------------------------------------------------ #

class EmbeddingStatsResponse(BaseModel):
    case_id: UUID
    total_canonical_records: int
    ready: int
    stale: int
    failed: int
    not_embeddable: int
    pending: int
    coverage_percentage: float


class EmbeddingRebuildResponse(BaseModel):
    case_id: UUID
    job_id: UUID
    status: str
    message: str
