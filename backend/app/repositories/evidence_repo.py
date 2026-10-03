from typing import List, Optional
from uuid import UUID
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.enums import EvidenceStatus
from backend.app.models.evidence import Evidence


class EvidenceRepository:
    """
    Data access repository for forensic evidence items.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, evidence: Evidence) -> Evidence:
        """Persists a new evidence record."""
        self.session.add(evidence)
        await self.session.commit()
        await self.session.refresh(evidence)
        return evidence

    async def get_by_id(self, evidence_id: UUID) -> Optional[Evidence]:
        """Retrieves evidence record by its UUID."""
        query = (
            select(Evidence)
            .where(Evidence.id == evidence_id)
            .options(selectinload(Evidence.uploader))
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list_by_case(
        self, case_id: UUID, skip: int = 0, limit: int = 50
    ) -> List[Evidence]:
        """Lists evidence items strictly belonging to a specific case."""
        query = (
            select(Evidence)
            .where(Evidence.case_id == case_id)
            .order_by(desc(Evidence.uploaded_at))
            .offset(skip)
            .limit(limit)
            .options(selectinload(Evidence.uploader))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self, evidence_id: UUID, status: EvidenceStatus
    ) -> Optional[Evidence]:
        """Updates the lifecycle status of an evidence file."""
        evidence = await self.get_by_id(evidence_id)
        if not evidence:
            return None
        evidence.status = status
        await self.session.commit()
        await self.session.refresh(evidence)
        return evidence
