import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import ArtifactType


class RawArtifactResponse(BaseModel):
    """Schema representing an extracted raw artifact with strict source provenance."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    evidence_id: uuid.UUID
    processing_job_id: uuid.UUID
    artifact_type: ArtifactType
    source_file: str
    source_path: str
    record_identifier: str
    raw_data: Dict[str, Any]
    parsed_at: datetime
    created_at: datetime


class RawArtifactListResponse(BaseModel):
    """Paginated list of raw artifacts."""
    items: List[RawArtifactResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
