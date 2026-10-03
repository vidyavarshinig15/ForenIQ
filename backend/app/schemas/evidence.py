from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import EvidenceStatus, IntegrityStatus


class EvidenceResponse(BaseModel):
    """
    Public representation of an ingested forensic evidence record.
    Security Notice: Physical storage paths on server storage disks are strictly redacted.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    original_filename: str
    stored_filename: str
    file_size: int
    mime_type: str
    detected_mime_type: Optional[str] = None
    file_extension: str
    status: EvidenceStatus
    sha256_hash: Optional[str] = None
    integrity_status: IntegrityStatus = IntegrityStatus.VALID
    last_integrity_check_at: Optional[datetime] = None
    uploaded_by: UUID
    uploader_name: Optional[str] = None
    uploader_email: Optional[str] = None
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime



class EvidenceUploadResult(BaseModel):
    """Result payload returned immediately following evidence upload."""
    message: str
    evidence: EvidenceResponse
