import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_db
from backend.app.models.enums import ArtifactType
from backend.app.models.user import User
from backend.app.schemas.timeline_anomaly import TimelineFilterRequest, TimelineResponse
from backend.app.timeline.timeline_service import timeline_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=TimelineResponse, status_code=status.HTTP_200_OK)
async def get_case_timeline(
    case_id: UUID,
    start_time: Optional[str] = Query(None, description="Start date/time in ISO-8601 format"),
    end_time: Optional[str] = Query(None, description="End date/time in ISO-8601 format"),
    entity_value: Optional[str] = Query(None, description="Filter by participant or entity name/number"),
    device_id: Optional[str] = Query(None, description="Filter by specific mobile device identifier"),
    limit: int = Query(1000, ge=1, le=10000, description="Max timeline events to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TimelineResponse:
    """
    Retrieve unified chronological forensic timeline for a case.
    Preserves exact timestamp precision, timezone offsets, and full evidence traceability.
    """
    filter_params = TimelineFilterRequest(
        start_time=start_time,
        end_time=end_time,
        entity_value=entity_value,
        device_id=device_id,
        limit=limit,
        offset=offset,
    )
    return await timeline_service.get_timeline(
        case_id=case_id,
        filter_params=filter_params,
        current_user=current_user,
        session=session,
    )


@router.post("/query", response_model=TimelineResponse, status_code=status.HTTP_200_OK)
async def query_case_timeline(
    case_id: UUID,
    filter_params: TimelineFilterRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TimelineResponse:
    """
    Advanced filtered timeline query supporting multi-attribute filters (artifact types, applications).
    """
    return await timeline_service.get_timeline(
        case_id=case_id,
        filter_params=filter_params,
        current_user=current_user,
        session=session,
    )
