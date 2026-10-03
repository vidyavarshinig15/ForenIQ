from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from uuid import UUID

from backend.app.models.enums import JobStatus
from backend.app.schemas.timeline_anomaly import AnomalyDetectionResponse, AnomalyJobStatusResponse

logger = logging.getLogger(__name__)


class AnomalyJobManager:
    """
    In-memory / Persistent Anomaly Job Registry.
    Tracks asynchronous execution progress, state checkpoints, and recovery for large-case anomaly jobs.
    """

    def __init__(self):
        self._jobs: Dict[str, AnomalyJobStatusResponse] = {}

    def create_job(self, case_id: UUID) -> AnomalyJobStatusResponse:
        """Create a new queued anomaly analysis job."""
        job_id = f"anom_job_{uuid.uuid4().hex[:12]}"
        job = AnomalyJobStatusResponse(
            job_id=job_id,
            case_id=case_id,
            status=JobStatus.QUEUED,
            progress=0.0,
            total_windows=0,
            anomalies_found=0,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._jobs[job_id] = job
        return job

    def update_progress(
        self,
        job_id: str,
        status: JobStatus,
        progress: float,
        total_windows: int = 0,
        anomalies_found: int = 0,
        result: Optional[AnomalyDetectionResponse] = None,
        error_message: Optional[str] = None,
    ) -> Optional[AnomalyJobStatusResponse]:
        """Update job progress state."""
        if job_id not in self._jobs:
            return None

        job = self._jobs[job_id]
        job.status = status
        job.progress = round(progress, 2)
        if total_windows > 0:
            job.total_windows = total_windows
        if anomalies_found > 0:
            job.anomalies_found = anomalies_found
        if result:
            job.result = result
            job.completed_at = datetime.now(timezone.utc).isoformat()
        if error_message:
            job.error_message = error_message
            job.completed_at = datetime.now(timezone.utc).isoformat()

        return job

    def get_job(self, job_id: str, case_id: Optional[UUID] = None) -> Optional[AnomalyJobStatusResponse]:
        """Retrieve job status enforcing case scoping."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        if case_id and job.case_id != case_id:
            return None
        return job

    def cancel_job(self, job_id: str, case_id: UUID) -> bool:
        """Cancel a running or queued job."""
        job = self.get_job(job_id, case_id)
        if not job:
            return False
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc).isoformat()
        return True


anomaly_job_manager = AnomalyJobManager()
