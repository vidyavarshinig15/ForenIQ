"""
Phase 11 — Investigation Query API Endpoints

Provides REST endpoints for natural-language query understanding, entity extraction,
investigation intent categorization, and automated retrieval plan execution.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_db
from backend.app.models.user import User
from backend.app.schemas.investigation import (
    InvestigationQuery,
    InvestigationQueryRequest,
    InvestigationQueryResponse,
)
from backend.app.services.investigation_service import ForensicInvestigationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/{case_id}/investigation/query",
    response_model=InvestigationQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Natural Language Investigation Query",
    description=(
        "Parses natural-language investigative inquiries, extracts forensic entities and temporal constraints, "
        "classifies intent, executes a case-scoped retrieval plan across forensic records, and logs the query for audit."
    ),
)
async def execute_investigation_query(
    case_id: UUID,
    request: InvestigationQueryRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> InvestigationQueryResponse:
    """Execute natural-language investigation query and retrieve ranked forensic evidence."""
    service = ForensicInvestigationService(session)
    return await service.execute_investigation_query(
        case_id=case_id,
        user=current_user,
        request=request,
    )


@router.post(
    "/{case_id}/investigation/parse",
    response_model=InvestigationQuery,
    status_code=status.HTTP_200_OK,
    summary="Parse Investigation Query (Transparency / Preview)",
    description=(
        "Inspect NLP query parsing without executing search. Returns extracted entities, temporal constraints, "
        "classified intent, and generated retrieval plan."
    ),
)
async def parse_investigation_query(
    case_id: UUID,
    request: InvestigationQueryRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> InvestigationQuery:
    """Parse and return structured investigation query interpretation."""
    service = ForensicInvestigationService(session)
    return await service.parse_investigation_query(
        case_id=case_id,
        user=current_user,
        request=request,
    )
