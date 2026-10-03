import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import JobPriority, JobStatus, JobType


class ProcessingJobCreateRequest(BaseModel):
    """Optional payload to trigger parsing with specific priority."""
    priority: JobPriority = Field(default=JobPriority.NORMAL, description="Job execution priority")


class ProcessingJobResponse(BaseModel):
    """Schema representing an asynchronous processing job."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    evidence_id: uuid.UUID
    job_type: JobType
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus
    current_stage: Optional[str] = None
    current_file: Optional[str] = None
    worker_id: Optional[str] = None
    progress: int = Field(ge=0, le=100)
    files_total: int
    files_processed: int
    artifacts_total: int
    records_processed: int = 0
    records_failed: int = 0
    bytes_processed: int = 0
    bytes_total: int = 0
    processing_rate: Optional[float] = None
    estimated_remaining_seconds: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3
    warnings_count: int
    errors_count: int
    summary_json: Optional[Dict[str, Any]] = None
    checkpoint_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_by: uuid.UUID
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ProcessingSummaryResponse(BaseModel):
    """Detailed summary of extracted artifact counts and parser diagnostics."""
    files_total: int = 0
    files_processed: int = 0
    files_failed: int = 0
    artifacts_extracted: int = 0
    calls_extracted: int = 0
    messages_extracted: int = 0
    contacts_extracted: int = 0
    location_extracted: int = 0
    browser_extracted: int = 0
    application_extracted: int = 0
    filesystem_extracted: int = 0
    warnings: List[str] = []
    errors: List[str] = []
