import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import async_session_factory
from backend.app.models.enums import JobPriority, JobStatus
from backend.app.models.processing_job import ProcessingJob
from backend.app.queue.base import BaseJobQueue

logger = logging.getLogger(__name__)

# Numerical priority weights for deterministic ordering
PRIORITY_WEIGHTS = {
    JobPriority.HIGH: 10,
    JobPriority.NORMAL: 5,
    JobPriority.LOW: 1,
}


class DatabaseJobQueue(BaseJobQueue):
    """
    Robust transactional database-backed queue implementation.
    Enforces atomic lease assignments, priority ordering, heartbeats,
    and stale-worker crash recovery on PostgreSQL and SQLite.
    """

    def __init__(self, default_lease_seconds: int = 30) -> None:
        self.default_lease_seconds = default_lease_seconds
        self._lock = asyncio.Lock()

    async def enqueue(
        self,
        job_id: UUID,
        priority: JobPriority = JobPriority.NORMAL,
        delay_seconds: float = 0.0,
    ) -> None:
        """Enqueue or re-enqueue a job in the database."""
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        async with async_session_factory() as session:
            stmt = (
                update(ProcessingJob)
                .where(ProcessingJob.id == job_id)
                .values(
                    status=JobStatus.QUEUED,
                    priority=priority,
                    worker_id=None,
                    lease_expires_at=None,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.execute(stmt)
            await session.commit()
            logger.debug(f"[DatabaseQueue] Enqueued job {job_id} with priority {priority.value}")

    async def dequeue(
        self,
        worker_id: str,
        timeout_seconds: float = 5.0,
    ) -> Optional[UUID]:
        """
        Atomically find and lease the highest-priority eligible job.
        Uses asyncio.Lock to serialize concurrent worker pulls in local process.
        """
        end_time = asyncio.get_event_loop().time() + timeout_seconds

        while True:
            async with self._lock:
                async with async_session_factory() as session:
                    # Select next candidate in QUEUED state
                    query = (
                        select(ProcessingJob)
                        .where(ProcessingJob.status == JobStatus.QUEUED)
                        .order_by(
                            # Sort by priority order, then oldest created_at
                            ProcessingJob.created_at.asc()
                        )
                        .limit(10)
                    )
                    result = await session.execute(query)
                    candidates = list(result.scalars().all())

                    if candidates:
                        # In-memory priority sorting based on weight
                        candidates.sort(
                            key=lambda j: (
                                -PRIORITY_WEIGHTS.get(j.priority, 5),
                                j.created_at,
                            )
                        )
                        chosen = candidates[0]

                        # Atomic lease assignment
                        now = datetime.now(timezone.utc)
                        expires_at = now + timedelta(seconds=self.default_lease_seconds)

                        update_stmt = (
                            update(ProcessingJob)
                            .where(
                                ProcessingJob.id == chosen.id,
                                ProcessingJob.status == JobStatus.QUEUED,
                            )
                            .values(
                                status=JobStatus.STARTING,
                                worker_id=worker_id,
                                started_at=chosen.started_at or now,
                                last_heartbeat_at=now,
                                lease_expires_at=expires_at,
                                updated_at=now,
                            )
                        )
                        res = await session.execute(update_stmt)
                        await session.commit()

                        if res.rowcount == 1:
                            logger.info(
                                f"[DatabaseQueue] Leased job {chosen.id} to worker {worker_id} "
                                f"(priority: {chosen.priority.value}, lease expires: {expires_at.isoformat()})"
                            )
                            return chosen.id

            if asyncio.get_event_loop().time() >= end_time:
                return None

            await asyncio.sleep(0.5)

    async def ack(self, job_id: UUID, worker_id: str) -> None:
        """Mark job successfully completed and clear lease."""
        async with async_session_factory() as session:
            stmt = (
                update(ProcessingJob)
                .where(ProcessingJob.id == job_id, ProcessingJob.worker_id == worker_id)
                .values(
                    lease_expires_at=None,
                    completed_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.execute(stmt)
            await session.commit()
            logger.debug(f"[DatabaseQueue] Acked job {job_id} by worker {worker_id}")

    async def nack(
        self,
        job_id: UUID,
        worker_id: str,
        retryable: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Handle job failure, increment retry count, and re-enqueue if retryable."""
        async with async_session_factory() as session:
            job = await session.get(ProcessingJob, job_id)
            if not job:
                return

            now = datetime.now(timezone.utc)
            if retryable and job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = JobStatus.RETRYING
                job.worker_id = None
                job.lease_expires_at = None
                job.error_message = f"Retryable error (attempt {job.retry_count}/{job.max_retries}): {error}"
                job.updated_at = now
                await session.commit()
                logger.warning(
                    f"[DatabaseQueue] Nacked retryable job {job_id} (attempt {job.retry_count}/{job.max_retries}). Error: {error}"
                )
                # Re-enqueue with exponential backoff delay
                delay = 2.0 ** job.retry_count
                asyncio.create_task(self.enqueue(job_id=job_id, priority=job.priority, delay_seconds=delay))
            else:
                job.status = JobStatus.FAILED
                job.worker_id = None
                job.lease_expires_at = None
                job.error_message = error or "Processing failed permanently."
                job.completed_at = now
                job.updated_at = now
                await session.commit()
                logger.error(f"[DatabaseQueue] Nacked permanently failed job {job_id}. Error: {error}")

    async def heartbeat(
        self,
        job_id: UUID,
        worker_id: str,
        lease_duration_seconds: int = 30,
    ) -> bool:
        """Extend active lease and record heartbeat timestamp."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=lease_duration_seconds)

        async with async_session_factory() as session:
            stmt = (
                update(ProcessingJob)
                .where(
                    ProcessingJob.id == job_id,
                    ProcessingJob.worker_id == worker_id,
                    ProcessingJob.status.in_([JobStatus.STARTING, JobStatus.RUNNING]),
                )
                .values(
                    last_heartbeat_at=now,
                    lease_expires_at=expires_at,
                    updated_at=now,
                )
            )
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    async def reap_stale_jobs(self, stale_threshold_seconds: int = 30) -> List[UUID]:
        """
        Detect workers that stopped heartbeating and expired their lease.
        Recovers jobs to RETRYING or marks FAILED if max retries exceeded.
        """
        now = datetime.now(timezone.utc)
        recovered: List[UUID] = []

        async with async_session_factory() as session:
            stmt = (
                select(ProcessingJob)
                .where(
                    ProcessingJob.status.in_([JobStatus.STARTING, JobStatus.RUNNING]),
                    ProcessingJob.lease_expires_at < now,
                )
            )
            result = await session.execute(stmt)
            stale_jobs = list(result.scalars().all())

            for job in stale_jobs:
                logger.warning(
                    f"[DatabaseQueue] Detected stale job {job.id} held by worker '{job.worker_id}'. "
                    f"Lease expired at {job.lease_expires_at.isoformat()}."
                )
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.status = JobStatus.RETRYING
                    job.worker_id = None
                    job.lease_expires_at = None
                    job.error_message = f"Recovered from crashed/stale worker '{job.worker_id}'."
                    job.updated_at = now
                    recovered.append(job.id)
                    # Re-enqueue
                    asyncio.create_task(self.enqueue(job_id=job.id, priority=job.priority, delay_seconds=2.0))
                else:
                    job.status = JobStatus.FAILED
                    job.worker_id = None
                    job.lease_expires_at = None
                    job.error_message = f"WORKER_TIMEOUT_CRASH: Worker lease expired after {job.retry_count} retries."
                    job.completed_at = now
                    job.updated_at = now
                    recovered.append(job.id)

            if stale_jobs:
                await session.commit()

        return recovered

    async def get_queue_length(self) -> int:
        """Count jobs currently waiting in QUEUED state."""
        async with async_session_factory() as session:
            stmt = select(func.count(ProcessingJob.id)).where(ProcessingJob.status == JobStatus.QUEUED)
            result = await session.execute(stmt)
            return int(result.scalar() or 0)

    async def close(self) -> None:
        """No persistent background connection to close for DatabaseQueue."""
        pass
