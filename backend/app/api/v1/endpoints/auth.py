from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_client_ip, get_current_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from backend.app.schemas.user import UserResponse
from backend.app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User Registration",
    description="Registers a new forensic investigator account.",
)
async def register(
    req: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    client_ip = get_client_ip(request)
    auth_service = AuthService(session)
    return await auth_service.register(req, client_ip=client_ip)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Investigator Authentication",
    description="Validates credentials via Argon2id and issues a signed JWT access token.",
)
async def login(
    req: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    client_ip = get_client_ip(request)
    auth_service = AuthService(session)
    return await auth_service.login(req, client_ip=client_ip)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Investigator Logout",
    description="Logs out the current investigator and records an audit event.",
)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    client_ip = get_client_ip(request)
    auth_service = AuthService(session)
    await auth_service.logout(current_user.id, client_ip=client_ip)
    return {"message": "Successfully logged out."}


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Current User Profile",
    description="Returns the profile and system role of the currently authenticated investigator.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)
