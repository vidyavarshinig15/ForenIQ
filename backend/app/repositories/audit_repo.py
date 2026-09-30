import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.audit import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
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
        # Strip potential secrets from details if passed
        sanitized_details = None
        if details:
            safe_copy = {k: v for k, v in details.items() if "password" not in k.lower() and "token" not in k.lower()}
            sanitized_details = json.dumps(safe_copy)

        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            case_id=case_id,
            timestamp=datetime.now(timezone.utc),
            status=status,
            details_json=sanitized_details,
            client_ip=client_ip,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_events(
        self,
        case_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        stmt = select(AuditLog)
        if case_id:
            stmt = stmt.where(AuditLog.case_id == case_id)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)

        stmt = stmt.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
