import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
from typing import List, Optional
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import update

from backend.app.core.config import get_settings
from backend.app.core.database import async_session_factory
from backend.app.models.enums import JobPriority, JobStatus
from backend.app.models.processing_job import ProcessingJob
from backend.app.queue.base import BaseJobQueue

logger = logging.getLogger(__name__)

PRIORITY_MULTIPLIERS = {
    JobPriority.HIGH: 10,
    JobPriority.NORMAL: 5,
    JobPriority.LOW: 1,
    "HIGH": 10,
    "NORMAL": 5,
    "LOW": 1,
}


class RedisJobQueue(BaseJobQueue):
    """
    High-performance Redis-backed job queue for enterprise workloads.
    Uses Redis Sorted Sets for priority scheduling, hashes for active worker leases,
    and automatic failover coordination.
    """

    def __init__(self, redis_url: Optional[str] = None, default_lease_seconds: int = 30) -> None:
        self.settings = get_settings()
        self.redis_url = redis_url or self.settings.REDIS_URL
        self.default_lease_seconds = default_lease_seconds
        self._client: Optional[aioredis.Redis] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.queue_key = "ufdr:queue:pending"
        self.leases_key = "ufdr:leases:active"

    @property
    def client(self) -> aioredis.Redis:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if (
            self._client is None
            or (current_loop is not None and self._loop != current_loop)
            or (self._loop is not None and self._loop.is_closed())
        ):
            self._loop = current_loop
            self._client = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
        return self._client

    def _calculate_score(self, priority: JobPriority) -> float:
        """Higher numerical priority produces lower sorted-set score (ZPOPMIN pops smallest)."""
        weight = PRIORITY_MULTIPLIERS.get(priority)
        if weight is None and hasattr(priority, "value"):
            weight = PRIORITY_MULTIPLIERS.get(priority.value, 5)
        elif weight is None:
            weight = 5
        # Invert weight so highest priority has lowest score
        timestamp = datetime.now(timezone.utc).timestamp()
        return (100 - weight) * 1e10 + timestamp

    async def enqueue(
        self,
        job_id: UUID,
        priority: JobPriority = JobPriority.NORMAL,
        delay_seconds: float = 0.0,
    ) -> None:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        score = self._calculate_score(priority)
        await self.client.zadd(self.queue_key, {str(job_id): score})

        # Synchronize DB status
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

        logger.info(f"[RedisQueue] Enqueued job {job_id} (priority: {priority.value})")

    async def dequeue(
        self,
        worker_id: str,
        timeout_seconds: float = 5.0,
    ) -> Optional[UUID]:
        end_time = asyncio.get_event_loop().time() + timeout_seconds

        while True:
            # Pop highest priority item (lowest score)
            popped = await self.client.zpopmin(self.queue_key, count=1)
            if popped:
                job_id_str, _ = popped[0]
                job_id = UUID(job_id_str)
                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(seconds=self.default_lease_seconds)

                lease_data = {
                    "worker_id": worker_id,
                    "lease_expires_at": expires_at.isoformat(),
                }
                await self.client.hset(self.leases_key, str(job_id), json.dumps(lease_data))

                # Update DB state
                async with async_session_factory() as session:
                    stmt = (
                        update(ProcessingJob)
                        .where(ProcessingJob.id == job_id)
                        .values(
                            status=JobStatus.STARTING,
                            worker_id=worker_id,
                            started_at=now,
                            last_heartbeat_at=now,
                            lease_expires_at=expires_at,
                            updated_at=now,
                        )
                    )
                    await session.execute(stmt)
                    await session.commit()

                logger.info(f"[RedisQueue] Dequeued job {job_id} to worker {worker_id}")
                return job_id

            if asyncio.get_event_loop().time() >= end_time:
                return None

            await asyncio.sleep(0.5)

    async def ack(self, job_id: UUID, worker_id: str) -> None:
        await self.client.hdel(self.leases_key, str(job_id))
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
        logger.debug(f"[RedisQueue] Acked job {job_id}")

    async def nack(
        self,
        job_id: UUID,
        worker_id: str,
        retryable: bool = True,
        error: Optional[str] = None,
    ) -> None:
        await self.client.hdel(self.leases_key, str(job_id))

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

                delay = 2.0 ** job.retry_count
                asyncio.create_task(self.enqueue(job_id=job.id, priority=job.priority, delay_seconds=delay))
            else:
                job.status = JobStatus.FAILED
                job.worker_id = None
                job.lease_expires_at = None
                job.error_message = error or "Processing failed permanently."
                job.completed_at = now
                job.updated_at = now
                await session.commit()

    async def heartbeat(
        self,
        job_id: UUID,
        worker_id: str,
        lease_duration_seconds: int = 30,
    ) -> bool:
        lease_raw = await self.client.hget(self.leases_key, str(job_id))
        if not lease_raw:
            return False

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=lease_duration_seconds)
        lease_data = {
            "worker_id": worker_id,
            "lease_expires_at": expires_at.isoformat(),
        }
        await self.client.hset(self.leases_key, str(job_id), json.dumps(lease_data))

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
        now = datetime.now(timezone.utc)
        all_leases = await self.client.hgetall(self.leases_key)
        recovered: List[UUID] = []

        for job_id_str, raw_info in all_leases.items():
            try:
                info = json.loads(raw_info)
                expires_at = datetime.fromisoformat(info["lease_expires_at"])
                if expires_at < now:
                    job_id = UUID(job_id_str)
                    await self.client.hdel(self.leases_key, job_id_str)
                    recovered.append(job_id)

                    async with async_session_factory() as session:
                        job = await session.get(ProcessingJob, job_id)
                        if job:
                            if job.retry_count < job.max_retries:
                                job.retry_count += 1
                                job.status = JobStatus.RETRYING
                                job.worker_id = None
                                job.lease_expires_at = None
                                job.error_message = f"Recovered from crashed/stale worker '{info.get('worker_id')}'."
                                job.updated_at = now
                                await session.commit()
                                asyncio.create_task(self.enqueue(job_id=job.id, priority=job.priority, delay_seconds=2.0))
                            else:
                                job.status = JobStatus.FAILED
                                job.worker_id = None
                                job.lease_expires_at = None
                                job.error_message = f"WORKER_TIMEOUT_CRASH: Worker lease expired after {job.retry_count} retries."
                                job.completed_at = now
                                job.updated_at = now
                                await session.commit()
            except Exception as e:
                logger.error(f"[RedisQueue] Error checking lease for {job_id_str}: {e}")

        return recovered

    async def get_queue_length(self) -> int:
        return await self.client.zcard(self.queue_key)

    async def close(self) -> None:
        await self.client.aclose()
