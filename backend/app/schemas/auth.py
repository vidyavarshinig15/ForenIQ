from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from backend.app.models.enums import UserRole
from backend.app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    email: str = Field(..., description="Investigator email address")
    password: str = Field(..., min_length=1, description="Password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserResponse


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: Optional[UserRole] = Field(default=UserRole.INVESTIGATOR)
