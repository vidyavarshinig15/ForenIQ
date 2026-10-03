import base64
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import ArtifactType, DataQualityStatus


class CanonicalEvidenceRepository:
    """
    Data access repository for CanonicalEvidence records.

    Phase 7: idempotent batch inserts, timeline queries, forensic lineage.
    Phase 8: cursor-based (keyset) pagination, case-scoped queries,
             streaming batch iteration, device-scoped forensic queries,
             count-free deep pagination, and DB health probing.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------------------- #
    # Cursor encoding / decoding helpers                                       #
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _encode_cursor(event_timestamp: Optional[datetime], record_id: uuid.UUID) -> str:
        """
        Encode a keyset cursor from (event_timestamp, record_id).
        Returns a URL-safe base64 string safe to embed in API responses.
        The timestamp is serialised as ISO-8601 so it round-trips via JSON.
        """
        payload = {
            "ts": event_timestamp.isoformat() if event_timestamp else None,
            "id": str(record_id),
        }
        raw = json.dumps(payload, separators=(",", ":"))
        return base64.urlsafe_b64encode(raw.encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> Tuple[Optional[datetime], uuid.UUID]:
        """
        Decode a keyset cursor back into (event_timestamp, record_id).
        Raises ValueError for malformed cursors so callers can return HTTP 400.
        """
        try:
            raw = base64.urlsafe_b64decode(cursor.encode()).decode()
            payload = json.loads(raw)
            ts_str = payload.get("ts")
            event_ts = datetime.fromisoformat(ts_str) if ts_str else None
            record_id = uuid.UUID(payload["id"])
            return event_ts, record_id
        except Exception as exc:
            raise ValueError(f"Invalid pagination cursor: {exc}") from exc

    # ---------------------------------------------------------------------- #
    # Bulk create (idempotent)                                                 #
    # ---------------------------------------------------------------------- #

    async def bulk_create_or_ignore(self, records: List[CanonicalEvidence]) -> int:
        """
        Idempotently batch inserts canonical records.
        Skips duplicates matching (evidence_id, canonical_fingerprint).
        Supports both PostgreSQL and SQLite.
        """
        if not records:
            return 0

        bind = self.session.bind
        dialect_name = bind.dialect.name if bind else "sqlite"
        now = datetime.now(timezone.utc)

        values = [
            {
                "id": r.id,
                "case_id": r.case_id,
                "evidence_id": r.evidence_id,
                "raw_artifact_id": r.raw_artifact_id,
                "processing_job_id": r.processing_job_id,
                "artifact_type": r.artifact_type.value if hasattr(r.artifact_type, "value") else str(r.artifact_type),
                "canonical_fingerprint": r.canonical_fingerprint,
                "source_file": r.source_file,
                "source_path": r.source_path,
                "record_identifier": r.record_identifier,
                "event_timestamp": r.event_timestamp,
                "timestamp_precision": r.timestamp_precision.value if hasattr(r.timestamp_precision, "value") else str(r.timestamp_precision),
                "timestamp_status": r.timestamp_status.value if hasattr(r.timestamp_status, "value") else str(r.timestamp_status),
                "original_timestamp": r.original_timestamp,
                "original_timezone": r.original_timezone,
                "device_id": r.device_id,
                "application": r.application,
                "original_application": r.original_application,
                "content": r.content,
                "entities": r.entities,
                "metadata": r.metadata_,
                "data_quality_status": r.data_quality_status.value if hasattr(r.data_quality_status, "value") else str(r.data_quality_status),
                "validation_warnings": r.validation_warnings,
                "parser_version": r.parser_version,
                "normalizer_version": r.normalizer_version,
                "created_at": r.created_at or now,
                "updated_at": r.updated_at or now,
            }
            for r in records
        ]

        if dialect_name == "postgresql":
            stmt = pg_insert(CanonicalEvidence).values(values).on_conflict_do_nothing(
                constraint="uq_canonical_evidence_identity"
            )
        else:
            stmt = sqlite_insert(CanonicalEvidence).values(values).on_conflict_do_nothing(
                index_elements=["evidence_id", "canonical_fingerprint"]
            )

        await self.session.execute(stmt)
        await self.session.commit()
        return len(records)

    # ---------------------------------------------------------------------- #
    # Single-record lookups                                                    #
    # ---------------------------------------------------------------------- #

    async def get_by_id(self, record_id: uuid.UUID) -> Optional[CanonicalEvidence]:
        """Fetch canonical evidence record by primary UUID."""
        stmt = select(CanonicalEvidence).where(CanonicalEvidence.id == record_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_raw_artifact_id(self, raw_artifact_id: uuid.UUID) -> Optional[CanonicalEvidence]:
        """Fetch canonical record derived from a specific RawArtifact."""
        stmt = select(CanonicalEvidence).where(CanonicalEvidence.raw_artifact_id == raw_artifact_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # ---------------------------------------------------------------------- #
    # Offset-based pagination (Phase 7 — retained for backward compatibility) #
    # ---------------------------------------------------------------------- #

    async def list_by_evidence(
        self,
        evidence_id: uuid.UUID,
        artifact_type: Optional[ArtifactType] = None,
        application: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[CanonicalEvidence], int]:
        """
        Offset-based paginated query for evidence-scoped canonical records.
        Returns (items, total_count).

        NOTE: For deep pagination (page > 100) at scale, prefer
        ``cursor_page_by_evidence`` which uses keyset pagination and avoids
        expensive COUNT + OFFSET scans.
        """
        query = select(CanonicalEvidence).where(CanonicalEvidence.evidence_id == evidence_id)
        count_query = select(func.count(CanonicalEvidence.id)).where(
            CanonicalEvidence.evidence_id == evidence_id
        )

        if artifact_type:
            val = artifact_type.value if hasattr(artifact_type, "value") else str(artifact_type)
            query = query.where(CanonicalEvidence.artifact_type == val)
            count_query = count_query.where(CanonicalEvidence.artifact_type == val)

        if application:
            query = query.where(CanonicalEvidence.application == application)
            count_query = count_query.where(CanonicalEvidence.application == application)

        if data_quality_status:
            val_dq = data_quality_status.value if hasattr(data_quality_status, "value") else str(data_quality_status)
            query = query.where(CanonicalEvidence.data_quality_status == val_dq)
            count_query = count_query.where(CanonicalEvidence.data_quality_status == val_dq)

        if start_time:
            query = query.where(CanonicalEvidence.event_timestamp >= start_time)
            count_query = count_query.where(CanonicalEvidence.event_timestamp >= start_time)

        if end_time:
            query = query.where(CanonicalEvidence.event_timestamp <= end_time)
            count_query = count_query.where(CanonicalEvidence.event_timestamp <= end_time)

        query = query.order_by(
            CanonicalEvidence.event_timestamp.desc().nullslast(),
            CanonicalEvidence.created_at.desc(),
        )

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        total_res = await self.session.execute(count_query)
        total = total_res.scalar() or 0

        items_res = await self.session.execute(query)
        items = list(items_res.scalars().all())

        return items, total

    # ---------------------------------------------------------------------- #
    # Phase 8: Cursor-based (keyset) pagination — evidence-scoped             #
    # ---------------------------------------------------------------------- #

    async def cursor_page_by_evidence(
        self,
        evidence_id: uuid.UUID,
        page_size: int = 50,
        cursor: Optional[str] = None,
        artifact_type: Optional[ArtifactType] = None,
        application: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[List[CanonicalEvidence], Optional[str]]:
        """
        Keyset (cursor) pagination for evidence-scoped canonical records.

        Performs a single indexed range scan — no OFFSET, no COUNT(*).
        Suitable for deep pagination at millions of records.

        Returns:
            (items, next_cursor) where next_cursor is None when exhausted.
        """
        query = select(CanonicalEvidence).where(CanonicalEvidence.evidence_id == evidence_id)

        if artifact_type:
            val = artifact_type.value if hasattr(artifact_type, "value") else str(artifact_type)
            query = query.where(CanonicalEvidence.artifact_type == val)
        if application:
            query = query.where(CanonicalEvidence.application == application)
        if data_quality_status:
            val_dq = data_quality_status.value if hasattr(data_quality_status, "value") else str(data_quality_status)
            query = query.where(CanonicalEvidence.data_quality_status == val_dq)
        if start_time:
            query = query.where(CanonicalEvidence.event_timestamp >= start_time)
        if end_time:
            query = query.where(CanonicalEvidence.event_timestamp <= end_time)

        if cursor:
            cursor_ts, cursor_id = self._decode_cursor(cursor)
            # Keyset condition for ORDER BY event_timestamp DESC NULLS LAST, id DESC:
            #   rows where ts < cursor_ts
            #   OR (ts == cursor_ts AND id < cursor_id)
            #   OR ts IS NULL  (NULLs sort after all non-NULLs in DESC NULLS LAST)
            if cursor_ts is not None:
                query = query.where(
                    or_(
                        CanonicalEvidence.event_timestamp < cursor_ts,
                        and_(
                            CanonicalEvidence.event_timestamp == cursor_ts,
                            CanonicalEvidence.id < cursor_id,
                        ),
                        CanonicalEvidence.event_timestamp.is_(None),
                    )
                )
            else:
                # Already in the NULL region; only id tiebreak matters
                query = query.where(
                    and_(
                        CanonicalEvidence.event_timestamp.is_(None),
                        CanonicalEvidence.id < cursor_id,
                    )
                )

        query = query.order_by(
            CanonicalEvidence.event_timestamp.desc().nullslast(),
            CanonicalEvidence.id.desc(),
        ).limit(page_size + 1)  # +1 to detect whether a next page exists

        result = await self.session.execute(query)
        rows = list(result.scalars().all())

        has_next = len(rows) > page_size
        items = rows[:page_size]

        next_cursor: Optional[str] = None
        if has_next and items:
            last = items[-1]
            next_cursor = self._encode_cursor(last.event_timestamp, last.id)

        return items, next_cursor

    # ---------------------------------------------------------------------- #
    # Phase 8: Cursor-based (keyset) pagination — case-scoped                 #
    # ---------------------------------------------------------------------- #

    async def cursor_page_by_case(
        self,
        case_id: uuid.UUID,
        page_size: int = 50,
        cursor: Optional[str] = None,
        artifact_type: Optional[ArtifactType] = None,
        device_id: Optional[str] = None,
        application: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[List[CanonicalEvidence], Optional[str]]:
        """
        Keyset (cursor) pagination across ALL evidence items in a case.

        Uses ``ix_canonical_evidence_case_time_id`` for constant-time
        page fetches regardless of dataset depth.

        Returns:
            (items, next_cursor)
        """
        query = select(CanonicalEvidence).where(CanonicalEvidence.case_id == case_id)

        if artifact_type:
            val = artifact_type.value if hasattr(artifact_type, "value") else str(artifact_type)
            query = query.where(CanonicalEvidence.artifact_type == val)
        if device_id:
            query = query.where(CanonicalEvidence.device_id == device_id)
        if application:
            query = query.where(CanonicalEvidence.application == application)
        if data_quality_status:
            val_dq = data_quality_status.value if hasattr(data_quality_status, "value") else str(data_quality_status)
            query = query.where(CanonicalEvidence.data_quality_status == val_dq)
        if start_time:
            query = query.where(CanonicalEvidence.event_timestamp >= start_time)
        if end_time:
            query = query.where(CanonicalEvidence.event_timestamp <= end_time)

        if cursor:
            cursor_ts, cursor_id = self._decode_cursor(cursor)
            if cursor_ts is not None:
                query = query.where(
                    or_(
                        CanonicalEvidence.event_timestamp < cursor_ts,
                        and_(
                            CanonicalEvidence.event_timestamp == cursor_ts,
                            CanonicalEvidence.id < cursor_id,
                        ),
                        CanonicalEvidence.event_timestamp.is_(None),
                    )
                )
            else:
                query = query.where(
                    and_(
                        CanonicalEvidence.event_timestamp.is_(None),
                        CanonicalEvidence.id < cursor_id,
                    )
                )

        query = query.order_by(
            CanonicalEvidence.event_timestamp.desc().nullslast(),
            CanonicalEvidence.id.desc(),
        ).limit(page_size + 1)

        result = await self.session.execute(query)
        rows = list(result.scalars().all())

        has_next = len(rows) > page_size
        items = rows[:page_size]

        next_cursor: Optional[str] = None
        if has_next and items:
            last = items[-1]
            next_cursor = self._encode_cursor(last.event_timestamp, last.id)

        return items, next_cursor

    # ---------------------------------------------------------------------- #
    # Phase 8: Streaming batch iterator                                        #
    # ---------------------------------------------------------------------- #

    async def stream_by_evidence(
        self,
        evidence_id: uuid.UUID,
        batch_size: int = 500,
        artifact_type: Optional[ArtifactType] = None,
    ) -> AsyncGenerator[List[CanonicalEvidence], None]:
        """
        Stream all canonical records for an evidence package in memory-bounded batches.

        Uses keyset pagination internally so memory usage is O(batch_size),
        not O(total_records). Safe for evidence packages with 1M+ records.

        Yields:
            List[CanonicalEvidence] — one batch at a time.
        """
        cursor: Optional[str] = None
        while True:
            batch, next_cursor = await self.cursor_page_by_evidence(
                evidence_id=evidence_id,
                page_size=batch_size,
                cursor=cursor,
                artifact_type=artifact_type,
            )
            if not batch:
                return
            yield batch
            if next_cursor is None:
                return
            cursor = next_cursor

    # ---------------------------------------------------------------------- #
    # Aggregate queries                                                        #
    # ---------------------------------------------------------------------- #

    async def count_by_artifact_type(self, evidence_id: uuid.UUID) -> Dict[str, int]:
        """Aggregate counts per canonical artifact type for an evidence package."""
        stmt = (
            select(CanonicalEvidence.artifact_type, func.count(CanonicalEvidence.id))
            .where(CanonicalEvidence.evidence_id == evidence_id)
            .group_by(CanonicalEvidence.artifact_type)
        )
        res = await self.session.execute(stmt)
        return {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in res.all()}

    async def count_by_artifact_type_for_case(self, case_id: uuid.UUID) -> Dict[str, int]:
        """
        Phase 8: Aggregate canonical record counts per artifact type across
        ALL evidence items in a case.
        """
        stmt = (
            select(CanonicalEvidence.artifact_type, func.count(CanonicalEvidence.id))
            .where(CanonicalEvidence.case_id == case_id)
            .group_by(CanonicalEvidence.artifact_type)
        )
        res = await self.session.execute(stmt)
        return {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in res.all()}

    async def count_for_case(self, case_id: uuid.UUID) -> int:
        """Phase 8: Total canonical record count across all evidence in a case."""
        stmt = select(func.count(CanonicalEvidence.id)).where(
            CanonicalEvidence.case_id == case_id
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    # ---------------------------------------------------------------------- #
    # Deletions                                                                #
    # ---------------------------------------------------------------------- #

    async def delete_by_evidence_id(self, evidence_id: uuid.UUID) -> int:
        """Delete all canonical records for an evidence package."""
        stmt = delete(CanonicalEvidence).where(CanonicalEvidence.evidence_id == evidence_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    async def delete_by_job_id(self, job_id: uuid.UUID) -> int:
        """Delete all canonical records produced by a specific processing job."""
        stmt = delete(CanonicalEvidence).where(CanonicalEvidence.processing_job_id == job_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    # ---------------------------------------------------------------------- #
    # Count helpers (Phase 7 compatibility)                                    #
    # ---------------------------------------------------------------------- #

    async def count_for_evidence(self, case_id: uuid.UUID, evidence_id: uuid.UUID) -> int:
        """Count total canonical records for an evidence container."""
        stmt = (
            select(func.count(CanonicalEvidence.id))
            .where(CanonicalEvidence.evidence_id == evidence_id)
            .where(CanonicalEvidence.case_id == case_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    async def list_for_evidence(
        self,
        case_id: uuid.UUID,
        evidence_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[CanonicalEvidence], int]:
        """Convenience method: list_by_evidence filtered by case and evidence."""
        return await self.list_by_evidence(
            evidence_id=evidence_id,
            page=page,
            page_size=page_size,
        )

    # ---------------------------------------------------------------------- #
    # Forensic lineage                                                         #
    # ---------------------------------------------------------------------- #

    async def get_originating_raw_artifact(
        self, case_id: uuid.UUID, record_id: uuid.UUID
    ):
        """Fetch the exact RawArtifact from which this CanonicalEvidence was derived."""
        from backend.app.models.raw_artifact import RawArtifact

        stmt = (
            select(RawArtifact)
            .join(CanonicalEvidence, CanonicalEvidence.raw_artifact_id == RawArtifact.id)
            .where(CanonicalEvidence.id == record_id)
            .where(CanonicalEvidence.case_id == case_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # ---------------------------------------------------------------------- #
    # Phase 8: DB storage health probe                                         #
    # ---------------------------------------------------------------------- #

    async def health_check(self) -> Dict[str, Any]:
        """
        Lightweight database health probe.
        Confirms connectivity and returns aggregate row counts.
        Does NOT perform sequential scans.
        """
        try:
            canonical_count = await self.session.scalar(
                select(func.count(CanonicalEvidence.id))
            ) or 0
            return {
                "status": "healthy",
                "canonical_evidence_rows": canonical_count,
            }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "error": str(exc),
            }
