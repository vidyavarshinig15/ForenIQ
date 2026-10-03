import logging
from typing import Optional

from backend.app.core.config import get_settings
from backend.app.queue.base import BaseJobQueue
from backend.app.queue.database_queue import DatabaseJobQueue
from backend.app.queue.redis_queue import RedisJobQueue

logger = logging.getLogger(__name__)

_global_queue: Optional[BaseJobQueue] = None


async def get_job_queue() -> BaseJobQueue:
    """
    Factory creating or returning the configured persistent job queue singleton.
    Tests Redis connection if QUEUE_BACKEND is 'auto' or 'redis',
    and gracefully falls back to DatabaseJobQueue if Redis is unavailable.
    """
    global _global_queue
    if _global_queue is not None:
        return _global_queue

    settings = get_settings()
    backend_choice = settings.QUEUE_BACKEND.lower()

    if backend_choice in ("redis", "auto"):
        try:
            redis_queue = RedisJobQueue(
                redis_url=settings.REDIS_URL,
                default_lease_seconds=settings.JOB_LEASE_TIMEOUT_SECONDS,
            )
            # Test connectivity
            await redis_queue.client.ping()
            logger.info(f"[QueueFactory] Connected to Redis queue at {settings.REDIS_URL}")
            _global_queue = redis_queue
            return _global_queue
        except Exception as e:
            if backend_choice == "redis":
                logger.error(f"[QueueFactory] Redis queue explicitly configured but connection failed: {e}")
                raise
            logger.warning(
                f"[QueueFactory] Redis unavailable ({e}). Falling back to transactional DatabaseJobQueue."
            )

    logger.info("[QueueFactory] Initializing persistent DatabaseJobQueue.")
    _global_queue = DatabaseJobQueue(
        default_lease_seconds=settings.JOB_LEASE_TIMEOUT_SECONDS,
    )
    return _global_queue


def reset_global_queue() -> None:
    """Reset the global queue singleton (primarily for testing)."""
    global _global_queue
    _global_queue = None
