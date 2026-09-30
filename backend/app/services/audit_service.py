from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.audit import AuditLog
from backend.app.repositories.audit_repo import AuditRepository


class AuditService:
    def __init__(self, session: AsyncSession):
        self.repo = AuditRepository(session)

    async def record_event(
        self,
        action: str,
        resource_type: str,
        status: str,
        user_id: Optional[UUID] = None,
        resource_id: Optional[str] = None,
        case_id: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None,
    ) -> AuditLog:
        return await self.repo.log_event(
            action=action,
            resource_type=resource_type,
            status=status,
            user_id=user_id,
            resource_id=resource_id,
            case_id=case_id,
            details=details,
            client_ip=client_ip,
        )

    async def list_events(
        self,
        case_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        return await self.repo.list_events(case_id=case_id, user_id=user_id, skip=skip, limit=limit)
