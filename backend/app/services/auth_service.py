from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.errors import ForensicAppException
from backend.app.core.security import (
    create_access_token,
    hash_password,
    login_rate_limiter,
    verify_password,
)
from backend.app.models.enums import AuditAction, UserRole
from backend.app.models.user import User
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from backend.app.schemas.user import UserResponse
from backend.app.services.audit_service import AuditService

settings = get_settings()


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.audit_service = AuditService(session)

    async def register(self, req: RegisterRequest, client_ip: Optional[str] = None) -> UserResponse:
        normalized_email = req.email.strip().lower()

        # Check for existing email (case-insensitive)
        existing = await self.user_repo.get_by_email(normalized_email)
        if existing:
            raise ForensicAppException(
                message="An account with this email address already exists.",
                code="EMAIL_ALREADY_REGISTERED",
                status_code=409,
            )

        # Hash password via Argon2id
        pwd_hash = hash_password(req.password)

        new_user = User(
            email=normalized_email,
            name=req.name.strip(),
            password_hash=pwd_hash,
            role=req.role or UserRole.INVESTIGATOR,
            is_active=True,
        )

        user = await self.user_repo.create(new_user)

        # Audit user creation
        await self.audit_service.record_event(
            action=AuditAction.USER_CREATE.value,
            resource_type="USER",
            resource_id=str(user.id),
            user_id=user.id,
            status="SUCCESS",
            details={"email": user.email, "role": user.role.value},
            client_ip=client_ip,
        )

        return UserResponse.model_validate(user)

    async def login(self, req: LoginRequest, client_ip: Optional[str] = None) -> TokenResponse:
        rate_key = f"{req.email}_{client_ip or 'unknown'}"

        if login_rate_limiter.is_locked(rate_key):
            # Record throttled attempt in audit log
            await self.audit_service.record_event(
                action=AuditAction.LOGIN_FAILURE.value,
                resource_type="AUTH",
                status="LOCKED_OUT",
                details={"reason": "Rate limit exceeded. Temporary lockout."},
                client_ip=client_ip,
            )
            raise ForensicAppException(
                message="Too many failed login attempts. Please wait 15 minutes before trying again.",
                code="ACCOUNT_LOCKED_TEMPORARILY",
                status_code=429,
            )

        user = await self.user_repo.get_by_email(req.email)

        # Generic error message to prevent user enumeration
        generic_error = ForensicAppException(
            message="Invalid email or password.",
            code="INVALID_CREDENTIALS",
            status_code=401,
        )

        if not user or not user.is_active:
            login_rate_limiter.record_failure(rate_key)
            await self.audit_service.record_event(
                action=AuditAction.LOGIN_FAILURE.value,
                resource_type="AUTH",
                status="FAILED",
                details={"attempted_email": req.email.strip().lower()},
                client_ip=client_ip,
            )
            raise generic_error

        # Verify password with Argon2id
        if not verify_password(req.password, user.password_hash):
            login_rate_limiter.record_failure(rate_key)
            await self.audit_service.record_event(
                action=AuditAction.LOGIN_FAILURE.value,
                resource_type="AUTH",
                user_id=user.id,
                status="FAILED",
                details={"reason": "Password mismatch"},
                client_ip=client_ip,
            )
            raise generic_error

        # Success - reset rate limiter count
        login_rate_limiter.record_success(rate_key)
        await self.user_repo.update_last_login(user.id)

        # Audit successful authentication
        await self.audit_service.record_event(
            action=AuditAction.LOGIN_SUCCESS.value,
            resource_type="AUTH",
            user_id=user.id,
            status="SUCCESS",
            details={"email": user.email, "role": user.role.value},
            client_ip=client_ip,
        )

        token = create_access_token(subject=str(user.id), role=user.role.value)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )

    async def logout(self, user_id: UUID, client_ip: Optional[str] = None) -> None:
        await self.audit_service.record_event(
            action=AuditAction.LOGOUT.value,
            resource_type="AUTH",
            user_id=user_id,
            status="SUCCESS",
            client_ip=client_ip,
        )

    async def ensure_bootstrap_admin(self) -> None:
        """Bootstraps the initial administrator account from environment variables if no admin exists."""
        admin_email = settings.INITIAL_ADMIN_EMAIL.strip().lower()
        existing = await self.user_repo.get_by_email(admin_email)
        if not existing:
            pwd_hash = hash_password(settings.INITIAL_ADMIN_PASSWORD)
            admin_user = User(
                email=admin_email,
                name=settings.INITIAL_ADMIN_NAME,
                password_hash=pwd_hash,
                role=UserRole.ADMIN,
                is_active=True,
            )
            await self.user_repo.create(admin_user)
            await self.session.commit()
