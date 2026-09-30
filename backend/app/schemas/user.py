from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.app.models.enums import UserRole


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User corporate/investigative email address")
    name: str = Field(..., min_length=2, max_length=255, description="Full investigator name")
    role: UserRole = Field(default=UserRole.INVESTIGATOR, description="System role (RBAC)")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128, description="User password (min 8 characters)")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
