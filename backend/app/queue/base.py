from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from backend.app.models.enums import JobPriority


class BaseJobQueue(ABC):
    """
    Abstract persistent job queue interface for forensic asynchronous processing.
    Guarantees atomic queue operations, bounded concurrency, priority scheduling,
    heartbeats, and worker crash recovery.
    """

    @abstractmethod
    async def enqueue(
        self,
        job_id: UUID,
        priority: JobPriority = JobPriority.NORMAL,
        delay_seconds: float = 0.0,
    ) -> None:
        """Enqueue a processing job with specified priority and optional backoff delay."""
        pass

    @abstractmethod
    async def dequeue(
        self,
        worker_id: str,
        timeout_seconds: float = 5.0,
    ) -> Optional[UUID]:
        """
        Atomically dequeue the highest-priority available job and assign a lease to worker_id.
        Returns None if no eligible jobs are ready within timeout_seconds.
        """
        pass

    @abstractmethod
    async def ack(self, job_id: UUID, worker_id: str) -> None:
        """Acknowledge successful completion of a job, releasing queue references."""
        pass

    @abstractmethod
    async def nack(
        self,
        job_id: UUID,
        worker_id: str,
        retryable: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Negative acknowledgement when a job fails.
        If retryable is True, re-enqueues with exponential backoff if retries remain.
        """
        pass

    @abstractmethod
    async def heartbeat(
        self,
        job_id: UUID,
        worker_id: str,
        lease_duration_seconds: int = 30,
    ) -> bool:
        """
        Extend the worker lease on an actively executing job.
        Returns False if the lease was lost or revoked.
        """
        pass

    @abstractmethod
    async def reap_stale_jobs(self, stale_threshold_seconds: int = 30) -> List[UUID]:
        """
        Identify jobs whose workers stopped sending heartbeats and recover them.
        """
        pass

    @abstractmethod
    async def get_queue_length(self) -> int:
        """Return the current number of pending items in the queue."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Release underlying connections and resources."""
        pass
