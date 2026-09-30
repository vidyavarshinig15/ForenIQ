from fastapi import APIRouter, status

from backend.app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Returns API operational health status without leaking sensitive system details."
)
async def health_check() -> HealthResponse:
    """
    Public health check endpoint.
    Used by container orchestration, load balancers, and monitoring systems.
    """
    return HealthResponse(status="ok")
