from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.case import Case, CaseMember
from backend.app.models.enums import CaseAccessRole, CaseStatus


class CaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_case_number(self) -> str:
        current_year = datetime.now(timezone.utc).year
        stmt = select(func.count(Case.id))
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return f"CASE-{current_year}-{count + 1:06d}"

    async def create_case(self, case: Case) -> Case:
        self.session.add(case)
        await self.session.flush()
        return case

    async def get_by_id(self, case_id: UUID) -> Optional[Case]:
        stmt = select(Case).where(Case.id == case_id).options(
            selectinload(Case.members).selectinload(CaseMember.user)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_case_number(self, case_number: str) -> Optional[Case]:
        stmt = select(Case).where(Case.case_number == case_number.strip())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: UUID,
        is_admin: bool,
        skip: int = 0,
        limit: int = 50,
        status: Optional[CaseStatus] = None,
    ) -> List[Case]:
        """
        Database-level filtering:
        Administrators see all cases.
        Non-administrators ONLY see cases where a corresponding CaseMember entry exists.
        """
        if is_admin:
            stmt = select(Case)
            if status:
                stmt = stmt.where(Case.status == status)
            stmt = stmt.order_by(Case.created_at.desc()).offset(skip).limit(limit)
        else:
            stmt = (
                select(Case)
                .join(CaseMember, Case.id == CaseMember.case_id)
                .where(CaseMember.user_id == user_id)
            )
            if status:
                stmt = stmt.where(Case.status == status)
            stmt = stmt.order_by(Case.created_at.desc()).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_membership(self, case_id: UUID, user_id: UUID) -> Optional[CaseMember]:
        stmt = (
            select(CaseMember)
            .where(CaseMember.case_id == case_id, CaseMember.user_id == user_id)
            .options(selectinload(CaseMember.user))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_member(self, member: CaseMember) -> CaseMember:
        self.session.add(member)
        await self.session.flush()
        return member

    async def update_member_role(
        self, case_id: UUID, user_id: UUID, new_role: CaseAccessRole
    ) -> Optional[CaseMember]:
        member = await self.get_membership(case_id, user_id)
        if member:
            member.access_role = new_role
            await self.session.flush()
        return member

    async def remove_member(self, case_id: UUID, user_id: UUID) -> bool:
        member = await self.get_membership(case_id, user_id)
        if member:
            await self.session.delete(member)
            await self.session.flush()
            return True
        return False
