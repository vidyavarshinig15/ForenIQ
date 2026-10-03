from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from uuid import UUID

from backend.app.schemas.report import ForensicReportDocument, ReportJobStatusResponse

logger = logging.getLogger(__name__)


class ReportJobManager:
    """
    In-memory / Persistent Report Generation Job Registry.
    Tracks asynchronous execution progress, state checkpoints, and recovery for large report generation jobs.
    """

    def __init__(self):
        self._jobs: Dict[str, ReportJobStatusResponse] = {}

    def create_job(self, case_id: UUID) -> ReportJobStatusResponse:
        """Create a new queued report generation job."""
        job_id = f"rep_job_{uuid.uuid4().hex[:12]}"
        job = ReportJobStatusResponse(
            job_id=job_id,
            case_id=case_id,
            status="QUEUED",
            progress=0.0,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._jobs[job_id] = job
        return job

    def update_progress(
        self,
        job_id: str,
        status: str,
        progress: float,
        report_id: Optional[str] = None,
        report: Optional[ForensicReportDocument] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ReportJobStatusResponse]:
        """Update report job progress state."""
        if job_id not in self._jobs:
            return None

        job = self._jobs[job_id]
        job.status = status
        job.progress = round(progress, 2)
        if report_id:
            job.report_id = report_id
        if report:
            job.report = report
            job.completed_at = datetime.now(timezone.utc).isoformat()
        if error_message:
            job.error_message = error_message
            job.completed_at = datetime.now(timezone.utc).isoformat()

        return job

    def get_job(self, job_id: str, case_id: Optional[UUID] = None) -> Optional[ReportJobStatusResponse]:
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
        if job.status in ["COMPLETED", "FAILED", "CANCELLED"]:
            return False
        job.status = "CANCELLED"
        job.completed_at = datetime.now(timezone.utc).isoformat()
        return True


report_job_manager = ReportJobManager()
