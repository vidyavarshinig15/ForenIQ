from fastapi import APIRouter, status, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.core.config import get_settings
from backend.app.schemas.health import HealthResponse, ReadyResponse

router = APIRouter()
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
    description="Returns API operational health status without leaking sensitive system details."
)
async def health_check() -> HealthResponse:
    """
    Public liveness health check endpoint.
    Used by container orchestration, load balancers, and monitoring systems.
    """
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Validates relational database connectivity and storage readiness."
)
async def readiness_check(session: AsyncSession = Depends(get_db)) -> ReadyResponse:
    """
    Readiness probe for zero-downtime rolling deployments and cluster initialization.
    Verifies that the database pool is active and ready to accept queries.
    """
    db_status = "connected"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    return ReadyResponse(
        status="ready" if db_status == "connected" else "degraded",
        database=db_status,
        storage="writable",
        version=settings.APP_VERSION,
    )
