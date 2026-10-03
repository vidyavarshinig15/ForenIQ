from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from backend.app.models.enums import CustodyEventType, IntegrityStatus


class EvidenceCustodyEventResponse(BaseModel):
    """Schema representing an individual chain-of-custody event."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evidence_id: UUID
    case_id: UUID
    actor_user_id: Optional[UUID] = None
    actor_name: Optional[str] = None
    actor_email: Optional[str] = None
    event_type: CustodyEventType
    timestamp: datetime
    sequence_number: int
    previous_event_id: Optional[UUID] = None
    previous_event_hash: Optional[str] = None
    event_hash: str
    metadata: Optional[Dict[str, Any]] = None


class CustodyChainVerificationResult(BaseModel):
    """Schema representing the verification outcome of an entire custody event chain."""
    evidence_id: UUID
    case_id: UUID
    status: str  # "VALID" or "INVALID"
    events_checked: int
    details: Optional[str] = None
    verified_at: datetime


class IntegrityVerificationResult(BaseModel):
    """Schema representing cryptographic storage integrity check against recorded SHA-256."""
    evidence_id: UUID
    case_id: UUID
    original_filename: str
    stored_hash: str
    calculated_hash: Optional[str] = None
    integrity_status: IntegrityStatus
    match: bool
    details: Optional[str] = None
    verified_at: datetime
