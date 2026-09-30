from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import CaseAccessRole, CaseStatus


class CaseCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Case title or subject")
    description: Optional[str] = Field(None, max_length=5000, description="Investigation scope and summary")
    case_number: Optional[str] = Field(None, max_length=100, description="Custom case number (auto-generated if omitted)")


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    status: Optional[CaseStatus] = None


class CaseMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    user_id: UUID
    user_name: str
    user_email: str
    access_role: CaseAccessRole
    created_at: datetime


class CaseMemberAdd(BaseModel):
    user_id: Optional[UUID] = None
    email: Optional[str] = None
    access_role: CaseAccessRole = Field(default=CaseAccessRole.CONTRIBUTOR)


class CaseMemberUpdate(BaseModel):
    access_role: CaseAccessRole


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_number: str
    title: str
    description: Optional[str] = None
    status: CaseStatus
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    current_user_role: Optional[str] = None
    members: Optional[List[CaseMemberResponse]] = None
