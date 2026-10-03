from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.custody import EvidenceCustodyEvent


class CustodyRepository:
    """Repository for append-only EvidenceCustodyEvent records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_event(self, event: EvidenceCustodyEvent) -> EvidenceCustodyEvent:
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def get_latest_event(self, evidence_id: UUID) -> Optional[EvidenceCustodyEvent]:
        query = (
            select(EvidenceCustodyEvent)
            .where(EvidenceCustodyEvent.evidence_id == evidence_id)
            .order_by(EvidenceCustodyEvent.sequence_number.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list_events_for_evidence(
        self, evidence_id: UUID
    ) -> List[EvidenceCustodyEvent]:
        query = (
            select(EvidenceCustodyEvent)
            .where(EvidenceCustodyEvent.evidence_id == evidence_id)
            .order_by(EvidenceCustodyEvent.sequence_number.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_event_by_id(self, event_id: UUID) -> Optional[EvidenceCustodyEvent]:
        query = select(EvidenceCustodyEvent).where(EvidenceCustodyEvent.id == event_id)
        result = await self.session.execute(query)
        return result.scalars().first()
