import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.enums import ArtifactType
from backend.app.models.raw_artifact import RawArtifact


from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert


class RawArtifactRepository:
    """Data access repository for extracted raw forensic artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_create(self, artifacts: List[RawArtifact]) -> int:
        """Batch insert raw artifact records."""
        if not artifacts:
            return 0
        self.session.add_all(artifacts)
        await self.session.commit()
        return len(artifacts)

    async def bulk_create_or_ignore(self, artifacts: List[RawArtifact]) -> int:
        """
        Idempotent batch insert ignoring duplicate artifacts based on (evidence_id, artifact_fingerprint).
        Supports both PostgreSQL and SQLite.
        """
        if not artifacts:
            return 0

        bind = self.session.bind
        dialect_name = bind.dialect.name if bind else "sqlite"

        now = datetime.now(timezone.utc)
        values = [
            {
                "id": a.id,
                "case_id": a.case_id,
                "evidence_id": a.evidence_id,
                "processing_job_id": a.processing_job_id,
                "artifact_type": a.artifact_type.value if hasattr(a.artifact_type, "value") else str(a.artifact_type),
                "artifact_fingerprint": a.artifact_fingerprint,
                "source_file": a.source_file,
                "source_path": a.source_path,
                "record_identifier": a.record_identifier,
                "raw_data": a.raw_data,
                "parsed_at": a.parsed_at or now,
                "created_at": a.created_at or now,
            }
            for a in artifacts
        ]

        if dialect_name == "postgresql":
            stmt = pg_insert(RawArtifact).values(values).on_conflict_do_nothing(
                constraint="uq_raw_artifact_identity"
            )
        else:
            stmt = sqlite_insert(RawArtifact).values(values).on_conflict_do_nothing(
                index_elements=["evidence_id", "artifact_fingerprint"]
            )

        await self.session.execute(stmt)
        await self.session.commit()
        return len(artifacts)

    async def delete_by_job_id(self, job_id: uuid.UUID) -> int:
        """Delete all raw artifacts produced by a specific job (used for idempotency/re-processing)."""
        stmt = delete(RawArtifact).where(RawArtifact.processing_job_id == job_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    async def delete_by_evidence_id(self, evidence_id: uuid.UUID) -> int:
        """Delete all raw artifacts for an evidence item."""
        stmt = delete(RawArtifact).where(RawArtifact.evidence_id == evidence_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    async def get_by_id(self, artifact_id: uuid.UUID) -> Optional[RawArtifact]:
        """Fetch raw artifact by ID."""
        stmt = select(RawArtifact).where(RawArtifact.id == artifact_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_evidence(
        self,
        evidence_id: uuid.UUID,
        artifact_type: Optional[ArtifactType] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[RawArtifact], int]:
        """
        Query paginated raw artifacts for an evidence package with optional type filtering.
        Returns (items, total_count).
        """
        query = select(RawArtifact).where(RawArtifact.evidence_id == evidence_id)
        count_query = select(func.count(RawArtifact.id)).where(RawArtifact.evidence_id == evidence_id)

        if artifact_type:
            query = query.where(RawArtifact.artifact_type == artifact_type)
            count_query = count_query.where(RawArtifact.artifact_type == artifact_type)

        query = query.order_by(RawArtifact.created_at.desc())
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        total_res = await self.session.execute(count_query)
        total = total_res.scalar() or 0

        items_res = await self.session.execute(query)
        items = list(items_res.scalars().all())

        return items, total

    async def count_by_artifact_type(self, evidence_id: uuid.UUID) -> Dict[str, int]:
        """Aggregate counts per artifact type for an evidence package."""
        stmt = (
            select(RawArtifact.artifact_type, func.count(RawArtifact.id))
            .where(RawArtifact.evidence_id == evidence_id)
            .group_by(RawArtifact.artifact_type)
        )
        res = await self.session.execute(stmt)
        return {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in res.all()}
