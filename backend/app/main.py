from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_v1_router
from backend.app.core.config import get_settings
from backend.app.core.database import async_session_factory, init_db
from backend.app.core.errors import register_exception_handlers
from backend.app.core.logging import get_logger, setup_logging
from backend.app.core.security import SecurityHeadersMiddleware
from backend.app.services.auth_service import AuthService

settings = get_settings()
setup_logging(settings.LOG_LEVEL)
logger = get_logger("forensic.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for startup and graceful shutdown."""
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [Env: {settings.APP_ENV}]"
    )

    # Initialize database tables
    try:
        await init_db()
        logger.info("Database schemas verified.")

        # Ensure bootstrap administrator exists
        async with async_session_factory() as session:
            auth_service = AuthService(session)
            await auth_service.ensure_bootstrap_admin()
            logger.info("Bootstrap administrator verified.")

        # Start asynchronous WorkerPool
        from backend.app.queue import get_worker_pool, get_job_queue
        worker_pool = await get_worker_pool()
        await worker_pool.start()
        logger.info(f"Worker pool active with concurrency={worker_pool.concurrency}.")
    except Exception as e:
        logger.error(f"Initialization error: {e}", exc_info=True)

    yield

    # Gracefully shutdown worker pool and queue
    try:
        from backend.app.queue import get_worker_pool, get_job_queue
        worker_pool = await get_worker_pool()
        await worker_pool.stop()
        queue = await get_job_queue()
        await queue.close()
    except Exception as e:
        logger.error(f"Error shutting down worker pool/queue: {e}")

    logger.info(f"Shutting down {settings.APP_NAME}")


def create_application() -> FastAPI:
    """Application factory for the Forensic Analysis Platform API."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Enterprise Digital Forensic Investigation Platform API",
        openapi_url=f"{settings.API_PREFIX}/openapi.json" if settings.DEBUG or settings.APP_ENV == "development" else None,
        docs_url=f"{settings.API_PREFIX}/docs" if settings.DEBUG or settings.APP_ENV == "development" else None,
        redoc_url=f"{settings.API_PREFIX}/redoc" if settings.DEBUG or settings.APP_ENV == "development" else None,
        lifespan=lifespan,
    )

    # 1. Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 2. CORS Middleware with configured origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    )

    # 3. Centralized Exception Handling
    register_exception_handlers(app)

    # 4. Versioned API Router
    app.include_router(api_v1_router, prefix=settings.API_PREFIX)

    return app


app = create_application()
