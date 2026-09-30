from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_client_ip, get_current_user
from backend.app.core.database import get_db
from backend.app.models.case import CaseMember
from backend.app.models.enums import CaseAccessRole, CaseStatus, UserRole
from backend.app.models.user import User
from backend.app.schemas.case import (
    CaseCreate,
    CaseMemberAdd,
    CaseMemberResponse,
    CaseMemberUpdate,
    CaseResponse,
    CaseUpdate,
)
from backend.app.services.case_service import CaseService

router = APIRouter()


@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Case",
    description="Creates a new forensic case and sets the authenticated investigator as LEAD.",
)
async def create_case(
    req: CaseCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CaseResponse:
    client_ip = get_client_ip(request)
    case_service = CaseService(session)
    return await case_service.create_case(current_user, req, client_ip=client_ip)


@router.get(
    "",
    response_model=List[CaseResponse],
    status_code=status.HTTP_200_OK,
    summary="List Cases",
    description="Lists forensic cases accessible to the authenticated user (enforced at database query level).",
)
async def list_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[CaseStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> List[CaseResponse]:
    case_service = CaseService(session)
    return await case_service.list_cases(current_user, skip=skip, limit=limit, status=status)


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Case Details",
    description="Retrieves case details if user is authorized. Protects against IDOR.",
)
async def get_case(
    case_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CaseResponse:
    client_ip = get_client_ip(request)
    case_service = CaseService(session)
    return await case_service.get_case(current_user, case_id, client_ip=client_ip)


@router.patch(
    "/{case_id}",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Case Metadata or Status",
    description="Updates case title, description, or controlled status lifecycle.",
)
async def update_case(
    case_id: UUID,
    req: CaseUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CaseResponse:
    client_ip = get_client_ip(request)
    case_service = CaseService(session)
    return await case_service.update_case(current_user, case_id, req, client_ip=client_ip)


@router.get(
    "/{case_id}/members",
    response_model=List[CaseMemberResponse],
    status_code=status.HTTP_200_OK,
    summary="List Case Members",
    description="Lists authorized members assigned to the case.",
)
async def list_case_members(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> List[CaseMemberResponse]:
    case_service = CaseService(session)
    return await case_service.list_members(current_user, case_id)


@router.post(
    "/{case_id}/members",
    response_model=CaseMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Case Member",
    description="Assigns a new investigator or analyst to the case.",
)
async def add_case_member(
    case_id: UUID,
    req: CaseMemberAdd,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CaseMemberResponse:
    client_ip = get_client_ip(request)
    case_service = CaseService(session)
    return await case_service.add_member(current_user, case_id, req, client_ip=client_ip)


@router.patch(
    "/{case_id}/members/{user_id}",
    response_model=CaseMemberResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Member Role",
    description="Updates access role for an assigned case member.",
)
async def update_member_role(
    case_id: UUID,
    user_id: UUID,
    req: CaseMemberUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CaseMemberResponse:
    client_ip = get_client_ip(request)
    case_service = CaseService(session)
    return await case_service.update_member_role(
        current_user, case_id, user_id, req.access_role, client_ip=client_ip
    )


@router.delete(
    "/{case_id}/members/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove Case Member",
    description="Revokes case access for a member.",
)
async def remove_case_member(
    case_id: UUID,
    user_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    client_ip = get_client_ip(request)
    case_service = CaseService(session)
    await case_service.remove_member(current_user, case_id, user_id, client_ip=client_ip)
    return {"message": "Case member successfully removed."}
