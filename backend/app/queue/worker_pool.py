import asyncio
from datetime import datetime, timezone
import logging
import os
import socket
from typing import Dict, List, Optional, Set
from uuid import UUID

from backend.app.core.config import get_settings
from backend.app.core.database import async_session_factory
from backend.app.models.enums import JobStatus, JobType
from backend.app.models.processing_job import ProcessingJob
from backend.app.queue.base import BaseJobQueue
from backend.app.queue.factory import get_job_queue
from backend.app.services.embedding_worker import EvidenceEmbeddingWorker
from backend.app.services.normalization_worker import EvidenceNormalizationWorker
from backend.app.services.parser_worker import UFDRParserWorker

logger = logging.getLogger(__name__)


class JobWorker:
    """
    Individual isolated worker process thread/coroutine.
    Maintains heartbeat loop and processes jobs through UFDRParserWorker.
    """

    def __init__(self, worker_id: str, queue: BaseJobQueue) -> None:
        self.worker_id = worker_id
        self.queue = queue
        self.settings = get_settings()
        self.parser_worker = UFDRParserWorker()
        self.norm_worker = EvidenceNormalizationWorker()
        self.embedding_worker = EvidenceEmbeddingWorker()
        self.current_job_id: Optional[UUID] = None
        self._is_running = True
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def _heartbeat_loop(self, job_id: UUID) -> None:
        """Periodically ping the queue to maintain lease validity."""
        interval = self.settings.JOB_HEARTBEAT_INTERVAL_SECONDS
        lease_duration = self.settings.JOB_LEASE_TIMEOUT_SECONDS

        while self.current_job_id == job_id:
            try:
                await asyncio.sleep(interval)
                if self.current_job_id != job_id:
                    break
                renewed = await self.queue.heartbeat(
                    job_id=job_id,
                    worker_id=self.worker_id,
                    lease_duration_seconds=lease_duration,
                )
                if not renewed:
                    logger.warning(
                        f"[{self.worker_id}] Heartbeat renewal failed or lease revoked for job {job_id}"
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.worker_id}] Heartbeat error on job {job_id}: {e}")

    async def start(self) -> None:
        """Main worker execution loop."""
        logger.info(f"[{self.worker_id}] Worker loop started.")
        while self._is_running:
            try:
                # Atomically dequeue next available job
                job_id = await self.queue.dequeue(worker_id=self.worker_id, timeout_seconds=2.0)
                if not job_id:
                    await asyncio.sleep(0.5)
                    continue

                self.current_job_id = job_id
                logger.info(f"[{self.worker_id}] Claimed job {job_id}. Starting execution...")

                # Spawn periodic heartbeat task
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(job_id))

                try:
                    # Execute appropriate processing engine based on job_type
                    async with async_session_factory() as session:
                        job = await session.get(ProcessingJob, job_id)
                        job_type = job.job_type if job else JobType.UFDR_PARSE

                    if job_type == JobType.NORMALIZATION:
                        await self.norm_worker.execute_job(job_id=job_id, worker_id=self.worker_id)
                    elif job_type == JobType.EMBEDDING:
                        await self.embedding_worker.execute_job(job_id=job_id, worker_id=self.worker_id)
                    else:
                        await self.parser_worker.execute_job(job_id=job_id, worker_id=self.worker_id)

                    await self.queue.ack(job_id=job_id, worker_id=self.worker_id)
                    logger.info(f"[{self.worker_id}] Successfully finished job {job_id}.")
                except Exception as exc:
                    logger.exception(f"[{self.worker_id}] Exception while executing job {job_id}: {exc}")
                    # Determine if error is retryable
                    is_retryable = not (
                        "UNSUPPORTED_UFDR_STRUCTURE" in str(exc)
                        or "SECURITY_VIOLATION" in str(exc)
                        or "INTEGRITY_MISMATCH" in str(exc)
                    )
                    await self.queue.nack(
                        job_id=job_id,
                        worker_id=self.worker_id,
                        retryable=is_retryable,
                        error=str(exc),
                    )
                finally:
                    if self._heartbeat_task and not self._heartbeat_task.done():
                        self._heartbeat_task.cancel()
                    self.current_job_id = None

            except asyncio.CancelledError:
                logger.info(f"[{self.worker_id}] Worker task cancelled.")
                break
            except Exception as e:
                logger.error(f"[{self.worker_id}] Unexpected error in worker loop: {e}")
                await asyncio.sleep(1.0)

    def stop(self) -> None:
        """Signal worker to stop after current job finishes."""
        self._is_running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()


class WorkerPool:
    """
    Manages bounded worker coroutines, concurrency constraints,
    and stale job crash recovery.
    """

    def __init__(self, concurrency: Optional[int] = None) -> None:
        self.settings = get_settings()
        self.concurrency = min(
            concurrency or self.settings.WORKER_CONCURRENCY,
            self.settings.MAX_WORKERS,
        )
        self.queue: Optional[BaseJobQueue] = None
        self.workers: List[JobWorker] = []
        self._worker_tasks: List[asyncio.Task] = []
        self._reaper_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self) -> None:
        """Start the worker pool and background stale-job reaper."""
        if self._is_running:
            return

        self.queue = await get_job_queue()
        self._is_running = True
        hostname = socket.gethostname()[:12]
        pid = os.getpid()

        for i in range(self.concurrency):
            worker_id = f"worker-{hostname}-{pid}-{i + 1}"
            worker = JobWorker(worker_id=worker_id, queue=self.queue)
            self.workers.append(worker)
            task = asyncio.create_task(worker.start(), name=worker_id)
            self._worker_tasks.append(task)

        # Start stale job reaper loop
        self._reaper_task = asyncio.create_task(self._reaper_loop(), name="stale-job-reaper")
        logger.info(
            f"[WorkerPool] Started with concurrency={self.concurrency} "
            f"(queue={type(self.queue).__name__})"
        )

    async def _reaper_loop(self) -> None:
        """Periodic background task that detects crashed workers and recovers stale jobs."""
        interval = self.settings.JOB_LEASE_TIMEOUT_SECONDS
        while self._is_running:
            try:
                await asyncio.sleep(interval)
                if not self._is_running:
                    break
                if self.queue:
                    recovered = await self.queue.reap_stale_jobs(stale_threshold_seconds=interval)
                    if recovered:
                        logger.warning(
                            f"[WorkerPool] Reaped and recovered {len(recovered)} stale/crashed jobs: {recovered}"
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[WorkerPool] Error in reaper loop: {e}")

    async def stop(self, timeout: float = 10.0) -> None:
        """Gracefully stop worker pool."""
        if not self._is_running:
            return

        logger.info("[WorkerPool] Stopping worker pool...")
        self._is_running = False

        if self._reaper_task and not self._reaper_task.done():
            self._reaper_task.cancel()

        for worker in self.workers:
            worker.stop()

        for task in self._worker_tasks:
            if not task.done():
                task.cancel()

        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        self.workers.clear()
        self._worker_tasks.clear()
        logger.info("[WorkerPool] Worker pool stopped cleanly.")


# Global singleton worker pool for application lifecycle
_global_pool: Optional[WorkerPool] = None


async def get_worker_pool() -> WorkerPool:
    global _global_pool
    if _global_pool is None:
        _global_pool = WorkerPool()
    return _global_pool
