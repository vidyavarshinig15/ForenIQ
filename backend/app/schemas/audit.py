import json
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, model_validator


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

    @model_validator(mode="before")
    @classmethod
    def populate_details(cls, data: Any) -> Any:
        if hasattr(data, "details_json"):
            raw_json = getattr(data, "details_json")
            if raw_json and isinstance(raw_json, str):
                try:
                    # If data is an ORM model or dict
                    parsed = json.loads(raw_json)
                    try:
                        setattr(data, "details", parsed)
                    except Exception:
                        pass
                except Exception:
                    pass
        return data
