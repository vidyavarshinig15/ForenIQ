from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import require_role
from backend.app.core.database import get_db
from backend.app.models.enums import UserRole
from backend.app.models.user import User
from backend.app.schemas.audit import AuditLogResponse
from backend.app.services.audit_service import AuditService

router = APIRouter()


@router.get(
    "",
    response_model=List[AuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Query Audit Logs",
    description="Lists tamper-evident forensic audit logs. Restricted to Administrators.",
)
async def list_audit_logs(
    case_id: Optional[UUID] = Query(None),
    user_id: Optional[UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> List[AuditLogResponse]:
    audit_service = AuditService(session)
    events = await audit_service.list_events(case_id=case_id, user_id=user_id, skip=skip, limit=limit)
    return [AuditLogResponse.model_validate(e) for e in events]
