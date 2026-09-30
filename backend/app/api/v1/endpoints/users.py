from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import require_role
from backend.app.core.database import get_db
from backend.app.models.enums import UserRole
from backend.app.models.user import User
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.user import UserResponse

router = APIRouter()


@router.get(
    "",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List Users",
    description="Lists investigator accounts for team assignments. Restricted to Administrators and Investigators.",
)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.INVESTIGATOR)),
    session: AsyncSession = Depends(get_db),
) -> List[UserResponse]:
    repo = UserRepository(session)
    users = await repo.list_users(skip=skip, limit=limit)
    return [UserResponse.model_validate(u) for u in users]
