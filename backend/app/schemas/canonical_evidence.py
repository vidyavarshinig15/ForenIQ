from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import ArtifactType, DataQualityStatus, JobPriority, JobStatus, JobType, TimestampPrecision, TimestampStatus


class EntityReferenceResponse(BaseModel):
    """Normalized entity reference model."""
    entity_type: str
    entity_value: str
    normalized_value: Optional[str] = None
    role: str


class CanonicalEvidenceResponse(BaseModel):
    """Serialized representation of a Canonical Evidence record."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    case_id: UUID
    evidence_id: UUID
    raw_artifact_id: UUID
    processing_job_id: Optional[UUID] = None
    artifact_type: ArtifactType
    canonical_fingerprint: str
    source_file: str
    source_path: str
    record_identifier: str

    event_timestamp: Optional[datetime] = None
    timestamp_precision: TimestampPrecision = TimestampPrecision.UNKNOWN
    timestamp_status: TimestampStatus = TimestampStatus.UNKNOWN
    original_timestamp: Optional[str] = None
    original_timezone: Optional[str] = None

    device_id: Optional[str] = None
    application: Optional[str] = None
    original_application: Optional[str] = None
    content: Optional[str] = None

    entities: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")

    data_quality_status: DataQualityStatus = DataQualityStatus.VALID
    validation_warnings: List[Dict[str, Any]] = Field(default_factory=list)

    parser_version: str = "1.0.0"
    normalizer_version: str = "1.0.0"
    created_at: datetime
    updated_at: datetime


class CanonicalEvidenceListResponse(BaseModel):
    """Paginated (offset-based) collection of canonical forensic evidence records."""
    items: List[CanonicalEvidenceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ------------------------------------------------------------------ #
# Phase 8: Cursor-based pagination schemas                            #
# ------------------------------------------------------------------ #

class CanonicalCursorPageResponse(BaseModel):
    """
    Cursor-paginated (keyset) collection of canonical forensic evidence records.

    ``next_cursor`` is an opaque token to pass as the ``cursor`` query parameter
    in the next request. When ``next_cursor`` is null the result set is exhausted.

    Unlike offset pagination, cursor pagination does not provide a total count
    (which requires a COUNT(*) scan). Use the offset endpoint when exact totals
    are needed; use this endpoint for deep pagination at scale.
    """
    items: List[CanonicalEvidenceResponse]
    page_size: int
    has_next: bool
    next_cursor: Optional[str] = None


class CaseCanonicalSummaryResponse(BaseModel):
    """
    Phase 8: Aggregate summary of canonical evidence across an entire case.
    Provides artifact-type breakdown and total count without loading records.
    """
    case_id: UUID
    total_canonical_records: int
    breakdown_by_type: Dict[str, int] = Field(default_factory=dict)

