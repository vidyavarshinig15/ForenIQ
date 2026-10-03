import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.enums import JobPriority, JobStatus, JobType, ProcessingStage
from backend.app.models.processing_job import ProcessingJob


class ProcessingJobRepository:
    """Data access repository for forensic processing jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(
        self,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        created_by: uuid.UUID,
        job_type: JobType = JobType.UFDR_PARSE,
        priority: JobPriority = JobPriority.NORMAL,
    ) -> ProcessingJob:
        """Create a new queued processing job."""
        job = ProcessingJob(
            case_id=case_id,
            evidence_id=evidence_id,
            job_type=job_type,
            priority=priority,
            status=JobStatus.QUEUED,
            current_stage=ProcessingStage.VALIDATING.value,
            progress=0,
            files_total=0,
            files_processed=0,
            artifacts_total=0,
            records_processed=0,
            records_failed=0,
            bytes_processed=0,
            bytes_total=0,
            warnings_count=0,
            errors_count=0,
            created_by=created_by,
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> Optional[ProcessingJob]:
        """Fetch job by ID."""
        stmt = select(ProcessingJob).where(ProcessingJob.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_active_job_for_evidence(self, evidence_id: uuid.UUID) -> Optional[ProcessingJob]:
        """Check if an active job already exists for this evidence."""
        stmt = (
            select(ProcessingJob)
            .where(
                ProcessingJob.evidence_id == evidence_id,
                ProcessingJob.status.in_([
                    JobStatus.QUEUED,
                    JobStatus.STARTING,
                    JobStatus.RUNNING,
                    JobStatus.RETRYING,
                    JobStatus.CANCEL_REQUESTED,
                ]),
            )
            .order_by(desc(ProcessingJob.created_at))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_evidence(self, evidence_id: uuid.UUID) -> List[ProcessingJob]:
        """List all processing jobs for an evidence item ordered by creation date desc."""
        stmt = (
            select(ProcessingJob)
            .where(ProcessingJob.evidence_id == evidence_id)
            .order_by(desc(ProcessingJob.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        job_id: uuid.UUID,
        status: JobStatus,
        priority: Optional[JobPriority] = None,
        worker_id: Optional[str] = None,
        current_stage: Optional[str] = None,
        current_file: Optional[str] = None,
        progress: Optional[int] = None,
        files_total: Optional[int] = None,
        files_processed: Optional[int] = None,
        artifacts_total: Optional[int] = None,
        records_processed: Optional[int] = None,
        records_failed: Optional[int] = None,
        bytes_processed: Optional[int] = None,
        bytes_total: Optional[int] = None,
        processing_rate: Optional[float] = None,
        estimated_remaining_seconds: Optional[int] = None,
        checkpoint_data: Optional[Dict[str, Any]] = None,
        last_heartbeat_at: Optional[datetime] = None,
        lease_expires_at: Optional[datetime] = None,
        warnings_count: Optional[int] = None,
        errors_count: Optional[int] = None,
        summary_json: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ProcessingJob]:
        """Update job execution metrics and status."""
        job = await self.get_by_id(job_id)
        if not job:
            return None

        job.status = status
        now = datetime.now(timezone.utc)

        if status in (JobStatus.STARTING, JobStatus.RUNNING) and not job.started_at:
            job.started_at = now
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            job.completed_at = now
            job.lease_expires_at = None

        if priority is not None:
            job.priority = priority
        if worker_id is not None:
            job.worker_id = worker_id
        if current_stage is not None:
            job.current_stage = current_stage
        if current_file is not None:
            job.current_file = current_file
        if progress is not None:
            job.progress = max(0, min(100, progress))
        if files_total is not None:
            job.files_total = files_total
        if files_processed is not None:
            job.files_processed = files_processed
        if artifacts_total is not None:
            job.artifacts_total = artifacts_total
        if records_processed is not None:
            job.records_processed = records_processed
        if records_failed is not None:
            job.records_failed = records_failed
        if bytes_processed is not None:
            job.bytes_processed = bytes_processed
        if bytes_total is not None:
            job.bytes_total = bytes_total
        if processing_rate is not None:
            job.processing_rate = processing_rate
        if estimated_remaining_seconds is not None:
            job.estimated_remaining_seconds = estimated_remaining_seconds
        if checkpoint_data is not None:
            job.checkpoint_data = checkpoint_data
        if last_heartbeat_at is not None:
            job.last_heartbeat_at = last_heartbeat_at
        if lease_expires_at is not None:
            job.lease_expires_at = lease_expires_at
        if warnings_count is not None:
            job.warnings_count = warnings_count
        if errors_count is not None:
            job.errors_count = errors_count
        if summary_json is not None:
            job.summary_json = summary_json
        if error_message is not None:
            job.error_message = error_message

        job.updated_at = now
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def request_cancellation(self, job_id: uuid.UUID) -> Optional[ProcessingJob]:
        """Request cooperative cancellation for an in-flight job."""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        if job.status in (JobStatus.QUEUED, JobStatus.STARTING):
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now(timezone.utc)
        elif job.status == JobStatus.RUNNING:
            job.status = JobStatus.CANCEL_REQUESTED
        job.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def is_cancel_requested(self, job_id: uuid.UUID) -> bool:
        """Check if job has received a cancellation request."""
        job = await self.get_by_id(job_id)
        if not job:
            return False
        return job.status in (JobStatus.CANCEL_REQUESTED, JobStatus.CANCELLED)

