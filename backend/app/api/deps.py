from typing import Callable, List, Optional
from uuid import UUID
from fastapi import Depends, Header, Path, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.errors import ForensicAppException, PermissionDeniedException
from backend.app.core.security import decode_access_token
from backend.app.models.case import CaseMember
from backend.app.models.enums import CaseAccessRole, UserRole
from backend.app.models.user import User
from backend.app.repositories.case_repo import CaseRepository
from backend.app.repositories.user_repo import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str:
    """Extracts client IP address safely considering forward headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Extracts and validates the Bearer JWT token from the Authorization header,
    decodes the payload, and verifies the user exists and is active.
    """
    if not auth or not auth.credentials:
        raise ForensicAppException(
            message="Authentication credentials were not provided.",
            code="NOT_AUTHENTICATED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    payload = decode_access_token(auth.credentials)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise ForensicAppException(
            message="Invalid token payload: subject missing.",
            code="TOKEN_MALFORMED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        user_uuid = UUID(user_id_str)
    except ValueError:
        raise ForensicAppException(
            message="Invalid token subject identifier.",
            code="TOKEN_INVALID",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_uuid)

    if not user:
        raise ForensicAppException(
            message="User account no longer exists.",
            code="USER_NOT_FOUND",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        raise ForensicAppException(
            message="User account is deactivated.",
            code="ACCOUNT_DEACTIVATED",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return user


def require_role(*allowed_roles: UserRole) -> Callable:
    """
    Factory creating a dependency that enforces system-level RBAC roles.
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise PermissionDeniedException(
                f"Action requires one of the following roles: {[r.value for r in allowed_roles]}."
            )
        return current_user

    return role_checker


async def verify_case_access(
    case_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CaseMember | None:
    """
    Case-level authorization dependency.
    Guarantees that User A cannot access User B's case simply by knowing the case ID (IDOR protection).
    Administrators have global operational access.
    """
    if current_user.role == UserRole.ADMIN:
        return None

    case_repo = CaseRepository(session)
    membership = await case_repo.get_membership(case_id, current_user.id)
    if not membership:
        raise PermissionDeniedException("You are not an authorized member of this case.")

    return membership
