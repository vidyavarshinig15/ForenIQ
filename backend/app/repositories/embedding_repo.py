"""
Phase 10 — Evidence Embedding Repository

Database operations for EvidenceEmbedding metadata records.
Tracks embedding statuses, staleness detection, model version consistency,
and batch lifecycle updates.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import EmbeddingStatus
from backend.app.models.evidence_embedding import EvidenceEmbedding


class EmbeddingRepository:
    """Data access layer for vector embedding metadata and lifecycle tracking."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_canonical_id(self, canonical_id: UUID) -> Optional[EvidenceEmbedding]:
        stmt = select(EvidenceEmbedding).where(EvidenceEmbedding.canonical_evidence_id == canonical_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_case_id(
        self,
        case_id: UUID,
        status: Optional[EmbeddingStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EvidenceEmbedding]:
        stmt = select(EvidenceEmbedding).where(EvidenceEmbedding.case_id == case_id)
        if status:
            stmt = stmt.where(EvidenceEmbedding.status == status)
        stmt = stmt.order_by(EvidenceEmbedding.created_at.asc()).offset(offset).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def upsert_embedding_record(
        self,
        case_id: UUID,
        canonical_id: UUID,
        model_name: str,
        model_version: str,
        dimension: int,
        content_hash: str,
        status: EmbeddingStatus,
        error_message: Optional[str] = None,
    ) -> EvidenceEmbedding:
        existing = await self.get_by_canonical_id(canonical_id)
        now = datetime.now(timezone.utc)
        if existing:
            existing.case_id = case_id
            existing.model_name = model_name
            existing.model_version = model_version
            existing.dimension = dimension
            existing.content_hash = content_hash
            existing.status = status
            existing.error_message = error_message
            existing.updated_at = now
            await self.session.flush()
            return existing
        else:
            emb = EvidenceEmbedding(
                id=uuid.uuid4(),
                case_id=case_id,
                canonical_evidence_id=canonical_id,
                model_name=model_name,
                model_version=model_version,
                dimension=dimension,
                content_hash=content_hash,
                status=status,
                error_message=error_message,
                created_at=now,
                updated_at=now,
            )
            self.session.add(emb)
            await self.session.flush()
            return emb

    async def get_case_embedding_stats(self, case_id: UUID) -> Dict[str, Any]:
        """Calculates counts of embeddings by status for a given case."""
        stmt = (
            select(EvidenceEmbedding.status, func.count(EvidenceEmbedding.id))
            .where(EvidenceEmbedding.case_id == case_id)
            .group_by(EvidenceEmbedding.status)
        )
        res = await self.session.execute(stmt)
        counts = {status.value if hasattr(status, "value") else str(status): count for status, count in res.all()}

        total_canonical_stmt = select(func.count(CanonicalEvidence.id)).where(CanonicalEvidence.case_id == case_id)
        total_canonical_res = await self.session.execute(total_canonical_stmt)
        total_canonical = total_canonical_res.scalar() or 0

        ready_count = counts.get("READY", 0)
        stale_count = counts.get("STALE", 0)
        failed_count = counts.get("FAILED", 0)
        not_embeddable_count = counts.get("NOT_EMBEDDABLE", 0)
        pending_count = total_canonical - (ready_count + stale_count + failed_count + not_embeddable_count)

        return {
            "case_id": str(case_id),
            "total_canonical_records": total_canonical,
            "ready": ready_count,
            "stale": stale_count,
            "failed": failed_count,
            "not_embeddable": not_embeddable_count,
            "pending": max(0, pending_count),
            "coverage_percentage": round((ready_count / total_canonical * 100.0), 1) if total_canonical > 0 else 100.0,
        }

    async def find_records_needing_embeddings(
        self,
        case_id: UUID,
        evidence_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CanonicalEvidence]:
        """
        Returns CanonicalEvidence records that do not have a READY embedding
        matching current content hash.
        """
        # Outer join CanonicalEvidence with EvidenceEmbedding
        stmt = (
            select(CanonicalEvidence)
            .outerjoin(EvidenceEmbedding, CanonicalEvidence.id == EvidenceEmbedding.canonical_evidence_id)
            .where(CanonicalEvidence.case_id == case_id)
        )
        if evidence_id:
            stmt = stmt.where(CanonicalEvidence.evidence_id == evidence_id)

        # Condition: either no embedding record, status is NOT_GENERATED/STALE/QUEUED, or error
        stmt = stmt.where(
            (EvidenceEmbedding.id.is_(None))
            | (EvidenceEmbedding.status.in_([EmbeddingStatus.NOT_GENERATED, EmbeddingStatus.STALE, EmbeddingStatus.QUEUED]))
        )
        stmt = stmt.order_by(CanonicalEvidence.created_at.asc()).offset(offset).limit(limit)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def mark_all_case_embeddings_stale(self, case_id: UUID) -> int:
        """Marks all embeddings in a case as STALE (e.g. before model migration or re-indexing)."""
        stmt = (
            update(EvidenceEmbedding)
            .where(EvidenceEmbedding.case_id == case_id)
            .values(
                status=EmbeddingStatus.STALE,
                updated_at=datetime.now(timezone.utc),
            )
        )
        res = await self.session.execute(stmt)
        return res.rowcount
