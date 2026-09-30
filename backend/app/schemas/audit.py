from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: Optional[UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    case_id: Optional[UUID] = None
    timestamp: datetime
    status: str
    details: Optional[Dict[str, Any]] = None
    client_ip: Optional[str] = None
