from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import EntityNotFoundException, ForensicAppException, PermissionDeniedException
from backend.app.models.case import Case, CaseMember
from backend.app.models.enums import AuditAction, CaseAccessRole, CaseStatus, UserRole
from backend.app.models.user import User
from backend.app.repositories.case_repo import CaseRepository
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.case import (
    CaseCreate,
    CaseMemberAdd,
    CaseMemberResponse,
    CaseResponse,
    CaseUpdate,
)
from backend.app.services.audit_service import AuditService


class CaseService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.case_repo = CaseRepository(session)
        self.user_repo = UserRepository(session)
        self.audit_service = AuditService(session)

    async def create_case(
        self, user: User, req: CaseCreate, client_ip: Optional[str] = None
    ) -> CaseResponse:
        # Check system role permissions
        if user.role not in [UserRole.ADMIN, UserRole.INVESTIGATOR]:
            raise PermissionDeniedException("Only Administrators and Investigators can create new cases.")

        # Determine or generate unique case number
        if req.case_number:
            existing = await self.case_repo.get_by_case_number(req.case_number)
            if existing:
                raise ForensicAppException(
                    message=f"Case number '{req.case_number}' is already in use.",
                    code="CASE_NUMBER_CONFLICT",
                    status_code=409,
                )
            case_num = req.case_number.strip().upper()
        else:
            case_num = await self.case_repo.generate_case_number()

        new_case = Case(
            case_number=case_num,
            title=req.title.strip(),
            description=req.description.strip() if req.description else None,
            status=CaseStatus.OPEN,
            created_by=user.id,
        )
        case = await self.case_repo.create_case(new_case)

        # Creator is automatically assigned as LEAD case member
        lead_member = CaseMember(
            case_id=case.id,
            user_id=user.id,
            access_role=CaseAccessRole.LEAD,
            created_by=user.id,
        )
        await self.case_repo.add_member(lead_member)

        # Audit event
        await self.audit_service.record_event(
            action=AuditAction.CASE_CREATE.value,
            resource_type="CASE",
            resource_id=str(case.id),
            case_id=case.id,
            user_id=user.id,
            status="SUCCESS",
            details={"case_number": case.case_number, "title": case.title},
            client_ip=client_ip,
        )

        return CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            status=case.status,
            created_by=case.created_by,
            created_at=case.created_at,
            updated_at=case.updated_at,
            closed_at=case.closed_at,
            current_user_role=CaseAccessRole.LEAD.value,
            members=[
                CaseMemberResponse(
                    id=lead_member.id,
                    case_id=case.id,
                    user_id=user.id,
                    user_name=user.name,
                    user_email=user.email,
                    access_role=CaseAccessRole.LEAD,
                    created_at=lead_member.created_at,
                )
            ],
        )

    async def get_case(
        self, user: User, case_id: UUID, client_ip: Optional[str] = None
    ) -> CaseResponse:
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException(f"Case with ID '{case_id}' was not found.")

        # IDOR Authorization Enforcement
        current_role: str
        if user.role == UserRole.ADMIN:
            current_role = "ADMIN"
        else:
            membership = await self.case_repo.get_membership(case_id, user.id)
            if not membership:
                # Log unauthorized access attempt
                await self.audit_service.record_event(
                    action=AuditAction.UNAUTHORIZED_ACCESS.value,
                    resource_type="CASE",
                    resource_id=str(case_id),
                    case_id=case_id,
                    user_id=user.id,
                    status="DENIED",
                    details={"attempted_action": "GET_CASE_DETAILS", "reason": "No case membership"},
                    client_ip=client_ip,
                )
                # Raise 404 to avoid leaking whether case exists (IDOR protection)
                raise EntityNotFoundException(f"Case with ID '{case_id}' was not found.")
            current_role = membership.access_role.value

        members_list = [
            CaseMemberResponse(
                id=m.id,
                case_id=m.case_id,
                user_id=m.user_id,
                user_name=m.user.name if m.user else "Unknown",
                user_email=m.user.email if m.user else "",
                access_role=m.access_role,
                created_at=m.created_at,
            )
            for m in case.members
        ]

        return CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            status=case.status,
            created_by=case.created_by,
            created_at=case.created_at,
            updated_at=case.updated_at,
            closed_at=case.closed_at,
            current_user_role=current_role,
            members=members_list,
        )

    async def list_cases(
        self,
        user: User,
        skip: int = 0,
        limit: int = 50,
        status: Optional[CaseStatus] = None,
    ) -> List[CaseResponse]:
        cases = await self.case_repo.list_for_user(
            user_id=user.id,
            is_admin=(user.role == UserRole.ADMIN),
            skip=skip,
            limit=limit,
            status=status,
        )

        results: List[CaseResponse] = []
        for c in cases:
            user_role_str = "ADMIN" if user.role == UserRole.ADMIN else "MEMBER"
            if user.role != UserRole.ADMIN:
                membership = await self.case_repo.get_membership(c.id, user.id)
                if membership:
                    user_role_str = membership.access_role.value

            results.append(
                CaseResponse(
                    id=c.id,
                    case_number=c.case_number,
                    title=c.title,
                    description=c.description,
                    status=c.status,
                    created_by=c.created_by,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    closed_at=c.closed_at,
                    current_user_role=user_role_str,
                )
            )
        return results

    async def update_case(
        self,
        user: User,
        case_id: UUID,
        req: CaseUpdate,
        client_ip: Optional[str] = None,
    ) -> CaseResponse:
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException(f"Case with ID '{case_id}' was not found.")

        # Check permissions: ADMIN or LEAD/CONTRIBUTOR
        if user.role != UserRole.ADMIN:
            membership = await self.case_repo.get_membership(case_id, user.id)
            if not membership or membership.access_role not in [CaseAccessRole.LEAD, CaseAccessRole.CONTRIBUTOR]:
                raise PermissionDeniedException("Insufficient case permissions to update case metadata.")

        if req.title is not None:
            case.title = req.title.strip()
        if req.description is not None:
            case.description = req.description.strip()
        if req.status is not None:
            # Controlled transition
            if req.status == CaseStatus.CLOSED and case.status != CaseStatus.CLOSED:
                case.closed_at = datetime.now(timezone.utc)
            elif req.status == CaseStatus.OPEN and case.status == CaseStatus.CLOSED:
                case.closed_at = None
            case.status = req.status

        case.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

        await self.audit_service.record_event(
            action=AuditAction.CASE_UPDATE.value,
            resource_type="CASE",
            resource_id=str(case.id),
            case_id=case.id,
            user_id=user.id,
            status="SUCCESS",
            details={"new_status": case.status.value, "title": case.title},
            client_ip=client_ip,
        )

        return await self.get_case(user, case_id)

    async def list_members(self, user: User, case_id: UUID) -> List[CaseMemberResponse]:
        # Validate access to case first
        await self.get_case(user, case_id)
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException("Case not found.")

        return [
            CaseMemberResponse(
                id=m.id,
                case_id=m.case_id,
                user_id=m.user_id,
                user_name=m.user.name if m.user else "Unknown",
                user_email=m.user.email if m.user else "",
                access_role=m.access_role,
                created_at=m.created_at,
            )
            for m in case.members
        ]

    async def add_member(
        self,
        user: User,
        case_id: UUID,
        req: CaseMemberAdd,
        client_ip: Optional[str] = None,
    ) -> CaseMemberResponse:
        # Check permissions: ADMIN or LEAD
        if user.role != UserRole.ADMIN:
            membership = await self.case_repo.get_membership(case_id, user.id)
            if not membership or membership.access_role != CaseAccessRole.LEAD:
                raise PermissionDeniedException("Only Administrators or Case Leads can add case members.")

        # Resolve target user
        target_user = None
        if req.user_id:
            target_user = await self.user_repo.get_by_id(req.user_id)
        elif req.email:
            target_user = await self.user_repo.get_by_email(req.email)

        if not target_user:
            raise EntityNotFoundException("Target user account was not found.")

        # Check existing membership
        existing = await self.case_repo.get_membership(case_id, target_user.id)
        if existing:
            raise ForensicAppException(
                message="User is already an assigned member of this case.",
                code="ALREADY_CASE_MEMBER",
                status_code=409,
            )

        new_member = CaseMember(
            case_id=case_id,
            user_id=target_user.id,
            access_role=req.access_role,
            created_by=user.id,
        )
        member = await self.case_repo.add_member(new_member)

        await self.audit_service.record_event(
            action=AuditAction.CASE_MEMBER_ADD.value,
            resource_type="CASE_MEMBER",
            resource_id=str(member.id),
            case_id=case_id,
            user_id=user.id,
            status="SUCCESS",
            details={
                "added_user_id": str(target_user.id),
                "added_user_email": target_user.email,
                "role": req.access_role.value,
            },
            client_ip=client_ip,
        )

        return CaseMemberResponse(
            id=member.id,
            case_id=case_id,
            user_id=target_user.id,
            user_name=target_user.name,
            user_email=target_user.email,
            access_role=member.access_role,
            created_at=member.created_at,
        )

    async def update_member_role(
        self,
        user: User,
        case_id: UUID,
        target_user_id: UUID,
        new_role: CaseAccessRole,
        client_ip: Optional[str] = None,
    ) -> CaseMemberResponse:
        if user.role != UserRole.ADMIN:
            membership = await self.case_repo.get_membership(case_id, user.id)
            if not membership or membership.access_role != CaseAccessRole.LEAD:
                raise PermissionDeniedException("Only Administrators or Case Leads can alter member roles.")

        updated = await self.case_repo.update_member_role(case_id, target_user_id, new_role)
        if not updated:
            raise EntityNotFoundException("Case membership record was not found.")

        await self.audit_service.record_event(
            action=AuditAction.CASE_MEMBER_UPDATE.value,
            resource_type="CASE_MEMBER",
            resource_id=str(updated.id),
            case_id=case_id,
            user_id=user.id,
            status="SUCCESS",
            details={"target_user_id": str(target_user_id), "new_role": new_role.value},
            client_ip=client_ip,
        )

        return CaseMemberResponse(
            id=updated.id,
            case_id=case_id,
            user_id=updated.user_id,
            user_name=updated.user.name if updated.user else "Unknown",
            user_email=updated.user.email if updated.user else "",
            access_role=updated.access_role,
            created_at=updated.created_at,
        )

    async def remove_member(
        self,
        user: User,
        case_id: UUID,
        target_user_id: UUID,
        client_ip: Optional[str] = None,
    ) -> bool:
        if user.role != UserRole.ADMIN:
            membership = await self.case_repo.get_membership(case_id, user.id)
            if not membership or membership.access_role != CaseAccessRole.LEAD:
                raise PermissionDeniedException("Only Administrators or Case Leads can remove case members.")

        removed = await self.case_repo.remove_member(case_id, target_user_id)
        if not removed:
            raise EntityNotFoundException("Case member record not found to remove.")

        await self.audit_service.record_event(
            action=AuditAction.CASE_MEMBER_REMOVE.value,
            resource_type="CASE_MEMBER",
            case_id=case_id,
            user_id=user.id,
            status="SUCCESS",
            details={"removed_user_id": str(target_user_id)},
            client_ip=client_ip,
        )
        return True
