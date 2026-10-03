"""
Phase 9 — Forensic Search Repository

ForensicSearchRepository encapsulates all database-side search query logic.

Architecture:
  - Every query is case-scoped (case_id always required)
  - Uses SQLAlchemy ORM with parameterized queries (no raw string concatenation)
  - Cursor-based (keyset) pagination — no OFFSET, no COUNT(*) for result pages
  - Separate facet query (GROUP BY) run only when explicitly requested
  - Partial text search uses SQL LIKE with bounded input (no unrestricted %% allowed)
  - Entity search targets the JSON entities array via JSON path (SQLite compatible)
  - All enum inputs are validated before reaching this layer

Searchable fields and their match strategy:
  content          → partial text, case-insensitive LIKE (bounded by MAX_QUERY_LENGTH)
  application      → case-insensitive exact or LIKE
  device_id        → exact match
  artifact_type    → exact enum match
  event_timestamp  → range filter (start_time <= ts <= end_time)
  source_file      → exact or LIKE
  record_identifier → exact
  evidence_id      → exact UUID
  case_id          → exact UUID (always enforced)
  entities[]       → JSON contains search by entity_type + entity_value
"""
import base64
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import ArtifactType, DataQualityStatus, TimestampPrecision
from backend.app.models.search_history import SearchHistory
from backend.app.schemas.search import (
    MAX_SEARCH_PAGE_SIZE,
    SearchFacets,
    SearchHistoryItem,
    SearchResultItem,
    SearchResultSource,
)


class ForensicSearchRepository:
    """
    Phase 9 search data access layer.

    All queries are case-scoped. All parameterization is handled by
    SQLAlchemy's ORM/Core layer — no raw string substitution.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------------------- #
    # Cursor helpers (reuse canonical evidence pattern)                        #
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _encode_cursor(event_timestamp: Optional[datetime], record_id: uuid.UUID) -> str:
        payload = {
            "ts": event_timestamp.isoformat() if event_timestamp else None,
            "id": str(record_id),
        }
        return base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> Tuple[Optional[datetime], uuid.UUID]:
        try:
            raw = base64.urlsafe_b64decode(cursor.encode()).decode()
            payload = json.loads(raw)
            ts_str = payload.get("ts")
            event_ts = datetime.fromisoformat(ts_str) if ts_str else None
            record_id = uuid.UUID(payload["id"])
            return event_ts, record_id
        except Exception as exc:
            raise ValueError(f"Invalid search cursor: {exc}") from exc

    # ---------------------------------------------------------------------- #
    # Query builder                                                            #
    # ---------------------------------------------------------------------- #

    def _build_base_query(
        self,
        case_id: uuid.UUID,
        *,
        q: Optional[str] = None,
        artifact_type: Optional[ArtifactType] = None,
        evidence_id: Optional[uuid.UUID] = None,
        device_id: Optional[str] = None,
        application: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_value: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        timestamp_precision: Optional[TimestampPrecision] = None,
        source_file: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
    ):
        """
        Build a SQLAlchemy SELECT query for CanonicalEvidence with all applicable filters.
        Always case-scoped. Never concatenates user input into SQL strings.
        """
        stmt = select(CanonicalEvidence).where(
            CanonicalEvidence.case_id == case_id
        )

        # --- Artifact type (exact enum) ---
        if artifact_type is not None:
            val = artifact_type.value if hasattr(artifact_type, "value") else str(artifact_type)
            stmt = stmt.where(CanonicalEvidence.artifact_type == val)

        # --- Evidence ID filter (verify it belongs to this case — done at service layer) ---
        if evidence_id is not None:
            stmt = stmt.where(CanonicalEvidence.evidence_id == evidence_id)

        # --- Device ID (exact) ---
        if device_id is not None and device_id.strip():
            stmt = stmt.where(CanonicalEvidence.device_id == device_id.strip())

        # --- Application (case-insensitive LIKE for partial, exact for normalized value) ---
        if application is not None and application.strip():
            app_clean = application.strip()
            # Use case-insensitive contains. SQLAlchemy ilike() is parameterized.
            stmt = stmt.where(CanonicalEvidence.application.ilike(f"%{app_clean}%"))

        # --- Source file (exact match against stored source_file field) ---
        if source_file is not None and source_file.strip():
            stmt = stmt.where(
                CanonicalEvidence.source_file == source_file.strip()
            )

        # --- Date range ---
        if start_time is not None:
            stmt = stmt.where(CanonicalEvidence.event_timestamp >= start_time)
        if end_time is not None:
            stmt = stmt.where(CanonicalEvidence.event_timestamp <= end_time)

        # --- Timestamp precision ---
        if timestamp_precision is not None:
            val_tp = timestamp_precision.value if hasattr(timestamp_precision, "value") else str(timestamp_precision)
            stmt = stmt.where(CanonicalEvidence.timestamp_precision == val_tp)

        # --- Data quality status ---
        if data_quality_status is not None:
            val_dq = data_quality_status.value if hasattr(data_quality_status, "value") else str(data_quality_status)
            stmt = stmt.where(CanonicalEvidence.data_quality_status == val_dq)

        # --- General text query (q) ---
        # Applied to: content (partial), application (partial), source_file (partial),
        # record_identifier (partial). All via parameterized LIKE, never raw string concat.
        if q is not None and q.strip():
            q_clean = q.strip()
            q_pattern = f"%{q_clean}%"
            text_conditions = or_(
                CanonicalEvidence.content.ilike(q_pattern),
                CanonicalEvidence.application.ilike(q_pattern),
                CanonicalEvidence.source_file.ilike(q_pattern),
                CanonicalEvidence.record_identifier.ilike(q_pattern),
                CanonicalEvidence.device_id.ilike(q_pattern),
            )
            stmt = stmt.where(text_conditions)

        # --- Entity search (type + value) ---
        # Searches the JSON entities array. Since SQLite doesn't support jsonb operators,
        # we use a JSON_EXTRACT approach for the entity value field.
        # For entity_value: we do a LIKE on the serialized JSON column (safe, parameterized).
        if entity_value is not None and entity_value.strip():
            ev_clean = entity_value.strip()
            # JSON array contains search: look for the value in the serialized entities JSON.
            # Cast JSON column to Text explicitly so SQLite can compile the LIKE comparison.
            from sqlalchemy import cast as sa_cast, Text as SAText
            stmt = stmt.where(
                sa_cast(CanonicalEvidence.entities, SAText).ilike(
                    f"%{ev_clean}%"
                )
            )
        if entity_type is not None and entity_type.strip():
            et_clean = entity_type.strip()
            from sqlalchemy import cast as sa_cast, Text as SAText
            stmt = stmt.where(
                sa_cast(CanonicalEvidence.entities, SAText).ilike(
                    f"%{et_clean}%"
                )
            )

        return stmt

    # ---------------------------------------------------------------------- #
    # Main search (cursor-paginated)                                           #
    # ---------------------------------------------------------------------- #

    async def search(
        self,
        case_id: uuid.UUID,
        *,
        q: Optional[str] = None,
        artifact_type: Optional[ArtifactType] = None,
        evidence_id: Optional[uuid.UUID] = None,
        device_id: Optional[str] = None,
        application: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_value: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        timestamp_precision: Optional[TimestampPrecision] = None,
        source_file: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
        sort: str = "timestamp_desc",
        page_size: int = 50,
        cursor: Optional[str] = None,
    ) -> Tuple[List[CanonicalEvidence], Optional[str]]:
        """
        Execute a case-scoped forensic search with cursor-based pagination.

        Returns (items, next_cursor). next_cursor is None when exhausted.
        """
        stmt = self._build_base_query(
            case_id=case_id,
            q=q,
            artifact_type=artifact_type,
            evidence_id=evidence_id,
            device_id=device_id,
            application=application,
            entity_type=entity_type,
            entity_value=entity_value,
            start_time=start_time,
            end_time=end_time,
            timestamp_precision=timestamp_precision,
            source_file=source_file,
            data_quality_status=data_quality_status,
        )

        # Apply cursor keyset condition
        if cursor:
            cursor_ts, cursor_id = self._decode_cursor(cursor)
            if sort in ("timestamp_desc", "created_at_desc"):
                if cursor_ts is not None:
                    stmt = stmt.where(
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
                    stmt = stmt.where(
                        and_(
                            CanonicalEvidence.event_timestamp.is_(None),
                            CanonicalEvidence.id < cursor_id,
                        )
                    )
            else:
                # timestamp_asc / created_at_asc
                if cursor_ts is not None:
                    stmt = stmt.where(
                        or_(
                            CanonicalEvidence.event_timestamp > cursor_ts,
                            and_(
                                CanonicalEvidence.event_timestamp == cursor_ts,
                                CanonicalEvidence.id > cursor_id,
                            ),
                        )
                    )
                else:
                    stmt = stmt.where(
                        and_(
                            CanonicalEvidence.event_timestamp.is_(None),
                            CanonicalEvidence.id > cursor_id,
                        )
                    )

        # Controlled sort (only approved fields)
        if sort == "timestamp_asc":
            stmt = stmt.order_by(
                CanonicalEvidence.event_timestamp.asc().nullslast(),
                CanonicalEvidence.id.asc(),
            )
        elif sort == "timestamp_desc":
            stmt = stmt.order_by(
                CanonicalEvidence.event_timestamp.desc().nullslast(),
                CanonicalEvidence.id.desc(),
            )
        elif sort == "created_at_asc":
            stmt = stmt.order_by(
                CanonicalEvidence.created_at.asc(),
                CanonicalEvidence.id.asc(),
            )
        elif sort == "created_at_desc":
            stmt = stmt.order_by(
                CanonicalEvidence.created_at.desc(),
                CanonicalEvidence.id.desc(),
            )
        elif sort == "artifact_type":
            stmt = stmt.order_by(
                CanonicalEvidence.artifact_type.asc(),
                CanonicalEvidence.event_timestamp.desc().nullslast(),
                CanonicalEvidence.id.desc(),
            )
        else:
            # Default fallback (should not reach here after validation)
            stmt = stmt.order_by(
                CanonicalEvidence.event_timestamp.desc().nullslast(),
                CanonicalEvidence.id.desc(),
            )

        stmt = stmt.limit(page_size + 1)

        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        has_next = len(rows) > page_size
        items = rows[:page_size]

        next_cursor: Optional[str] = None
        if has_next and items:
            last = items[-1]
            next_cursor = self._encode_cursor(last.event_timestamp, last.id)

        return items, next_cursor

    async def fetch_canonical_by_ids(
        self,
        case_id: uuid.UUID,
        record_ids: List[uuid.UUID],
        *,
        artifact_type: Optional[ArtifactType] = None,
        evidence_id: Optional[uuid.UUID] = None,
        device_id: Optional[str] = None,
        application: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        source_file: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
    ) -> List[CanonicalEvidence]:
        """
        Fetches CanonicalEvidence records for the specified IDs within the case,
        applying all active metadata filters.
        """
        if not record_ids:
            return []

        stmt = select(CanonicalEvidence).where(
            CanonicalEvidence.case_id == case_id,
            CanonicalEvidence.id.in_(record_ids),
        )

        if artifact_type is not None:
            stmt = stmt.where(CanonicalEvidence.artifact_type == artifact_type)
        if evidence_id is not None:
            stmt = stmt.where(CanonicalEvidence.evidence_id == evidence_id)
        if device_id is not None and device_id.strip():
            stmt = stmt.where(CanonicalEvidence.device_id == device_id.strip())
        if application is not None and application.strip():
            stmt = stmt.where(CanonicalEvidence.application.ilike(f"%{application.strip()}%"))
        if start_time is not None:
            stmt = stmt.where(CanonicalEvidence.event_timestamp >= start_time)
        if end_time is not None:
            stmt = stmt.where(CanonicalEvidence.event_timestamp <= end_time)
        if source_file is not None and source_file.strip():
            stmt = stmt.where(CanonicalEvidence.source_file.ilike(f"%{source_file.strip()}%"))
        if data_quality_status is not None:
            stmt = stmt.where(CanonicalEvidence.data_quality_status == data_quality_status)

        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # ---------------------------------------------------------------------- #
    # Facets (aggregate counts, run separately)                                #
    # ---------------------------------------------------------------------- #

    async def get_facets(
        self,
        case_id: uuid.UUID,
        *,
        q: Optional[str] = None,
        artifact_type: Optional[ArtifactType] = None,
        evidence_id: Optional[uuid.UUID] = None,
        device_id: Optional[str] = None,
        application: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_value: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        source_file: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
    ) -> SearchFacets:
        """
        Run a GROUP BY aggregate to get per-artifact-type counts for the current filter set.
        Only executed when the caller explicitly requests facets (include_facets=True).
        """
        # Build the base filter without sort/cursor/limit
        base = self._build_base_query(
            case_id=case_id,
            q=q,
            artifact_type=artifact_type,
            evidence_id=evidence_id,
            device_id=device_id,
            application=application,
            entity_type=entity_type,
            entity_value=entity_value,
            start_time=start_time,
            end_time=end_time,
            source_file=source_file,
            data_quality_status=data_quality_status,
        )

        # Replace SELECT columns for GROUP BY aggregate
        agg_stmt = (
            select(CanonicalEvidence.artifact_type, func.count(CanonicalEvidence.id))
            .where(base.whereclause)
            .group_by(CanonicalEvidence.artifact_type)
        )

        res = await self.session.execute(agg_stmt)
        rows = res.all()

        by_type: Dict[str, int] = {
            str(row[0].value if hasattr(row[0], "value") else row[0]): row[1]
            for row in rows
        }
        total = sum(by_type.values())
        return SearchFacets(by_artifact_type=by_type, total_matched=total)

    # ---------------------------------------------------------------------- #
    # Search history CRUD                                                      #
    # ---------------------------------------------------------------------- #

    async def save_search_history(
        self,
        case_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        query: Optional[str],
        filters: Dict[str, Any],
        result_count: int,
        duration_ms: int,
    ) -> SearchHistory:
        """Persist a completed search operation to the audit trail."""
        entry = SearchHistory(
            id=uuid.uuid4(),
            case_id=case_id,
            user_id=user_id,
            query=query,
            filters_json=json.dumps(filters, default=str),
            result_count=result_count,
            executed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def list_search_history(
        self,
        case_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[SearchHistory], int]:
        """Return case-scoped search history, optionally filtered by user."""
        from sqlalchemy import desc

        stmt = select(SearchHistory).where(SearchHistory.case_id == case_id)
        count_stmt = select(func.count(SearchHistory.id)).where(
            SearchHistory.case_id == case_id
        )

        if user_id is not None:
            stmt = stmt.where(SearchHistory.user_id == user_id)
            count_stmt = count_stmt.where(SearchHistory.user_id == user_id)

        stmt = stmt.order_by(desc(SearchHistory.executed_at)).limit(limit).offset(offset)

        items_res = await self.session.execute(stmt)
        count_res = await self.session.execute(count_stmt)

        return list(items_res.scalars().all()), (count_res.scalar() or 0)
