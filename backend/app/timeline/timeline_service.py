from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from uuid import UUID

from fastapi import status
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.errors import ForensicAppException
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import ArtifactType, AuditAction, TimestampPrecision, TimestampStatus
from backend.app.models.user import User
from backend.app.repositories.case_repo import CaseRepository
from backend.app.schemas.timeline_anomaly import TimelineEvent, TimelineFilterRequest, TimelineResponse

logger = logging.getLogger(__name__)


class TimelineService:
    """
    Forensic Timeline Construction & Query Engine.
    Transforms canonical forensic records into an immutable, deterministically sorted
    chronological timeline with evidence traceability and strict case isolation.
    """

    @staticmethod
    def _extract_actor_and_target(record: CanonicalEvidence) -> tuple[Optional[str], Optional[str]]:
        """Extract sender/actor and receiver/target with normalization fallbacks."""
        meta = record.metadata_ or {}
        actor = None
        target = None

        # 1. Check metadata fields
        actor_candidates = ["sender", "caller", "from", "owner", "author", "creator", "source_entity"]
        for key in actor_candidates:
            val = meta.get(key)
            if val and isinstance(val, str) and val.strip():
                actor = val.strip()
                break

        target_candidates = ["receiver", "callee", "to", "recipient", "target_entity", "peer"]
        for key in target_candidates:
            val = meta.get(key)
            if val and isinstance(val, str) and val.strip():
                target = val.strip()
                break

        # 2. Check entities list fallback
        if not actor or not target:
            for entity in record.entities or []:
                role = (entity.get("role") or "").lower()
                val = entity.get("value")
                if not val or not isinstance(val, str):
                    continue
                if not actor and role in ["sender", "caller", "from", "source", "author"]:
                    actor = val.strip()
                elif not target and role in ["receiver", "callee", "to", "recipient", "target"]:
                    target = val.strip()

        # 3. Artifact-specific fallbacks
        if not actor and record.artifact_type == ArtifactType.CONTACT:
            actor = meta.get("display_name") or record.record_identifier

        return actor, target

    @staticmethod
    def _build_content_summary(record: CanonicalEvidence) -> Optional[str]:
        """Construct a concise, sanitized content summary for quick timeline browsing."""
        if record.content and record.content.strip():
            c = record.content.strip()
            return c[:200] + ("..." if len(c) > 200 else "")

        meta = record.metadata_ or {}
        if record.artifact_type == ArtifactType.CALL:
            duration = meta.get("duration", 0)
            call_type = meta.get("call_type", "CALL")
            return f"{call_type} (Duration: {duration}s)"
        elif record.artifact_type == ArtifactType.LOCATION:
            lat = meta.get("latitude")
            lon = meta.get("longitude")
            return f"GPS Coordinates: ({lat}, {lon})" if lat and lon else "Location Event"
        elif record.artifact_type == ArtifactType.BROWSER:
            url = meta.get("url") or meta.get("title")
            return f"URL: {url}" if url else "Browser History"
        elif record.artifact_type == ArtifactType.FILESYSTEM:
            file_name = meta.get("file_name") or record.record_identifier
            return f"File: {file_name}"

        return record.record_identifier

    async def get_timeline(
        self,
        case_id: UUID,
        filter_params: TimelineFilterRequest,
        current_user: User,
        session: AsyncSession,
    ) -> TimelineResponse:
        """
        Query and construct a unified case-scoped timeline.
        Enforces RBAC, case boundaries, and timestamp integrity.
        """
        # Validate Case Scoping and Access
        case_repo = CaseRepository(session)
        case = await case_repo.get_by_id(case_id)
        if not case:
            raise ForensicAppException(
                message=f"Case '{case_id}' not found.",
                code="CASE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        member = await case_repo.get_membership(case_id, current_user.id)
        if not member and current_user.role.value not in ("ADMIN",):
            raise ForensicAppException(
                message="Access denied to this case.",
                code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Build SQL Query with Case Isolation
        query = select(CanonicalEvidence).where(CanonicalEvidence.case_id == case_id)

        # Temporal Filtering
        if filter_params.start_time:
            try:
                start_dt = datetime.fromisoformat(filter_params.start_time.replace("Z", "+00:00"))
                query = query.where(CanonicalEvidence.event_timestamp >= start_dt)
            except ValueError:
                logger.warning("Invalid start_time format: %s", filter_params.start_time)

        if filter_params.end_time:
            try:
                end_dt = datetime.fromisoformat(filter_params.end_time.replace("Z", "+00:00"))
                query = query.where(CanonicalEvidence.event_timestamp <= end_dt)
            except ValueError:
                logger.warning("Invalid end_time format: %s", filter_params.end_time)

        # Artifact Types Filter
        if filter_params.artifact_types:
            query = query.where(CanonicalEvidence.artifact_type.in_(filter_params.artifact_types))

        # Application Filter
        if filter_params.applications:
            query = query.where(CanonicalEvidence.application.in_(filter_params.applications))

        # Device ID Filter
        if filter_params.device_id:
            query = query.where(CanonicalEvidence.device_id == filter_params.device_id)

        # Deterministic Chronological Sorting
        query = query.order_by(
            CanonicalEvidence.event_timestamp.asc().nulls_last(),
            CanonicalEvidence.artifact_type.asc(),
            CanonicalEvidence.id.asc(),
        )

        result = await session.execute(query)
        all_records = result.scalars().all()

        # In-memory entity filtering if requested
        if filter_params.entity_value:
            target_val = filter_params.entity_value.strip().lower()
            filtered_records = []
            for rec in all_records:
                actor, target = self._extract_actor_and_target(rec)
                actor_match = actor and target_val in actor.lower()
                target_match = target and target_val in target.lower()
                entity_match = any(
                    target_val in str(e.get("value", "")).lower()
                    for e in (rec.entities or [])
                )
                if actor_match or target_match or entity_match:
                    filtered_records.append(rec)
            records = filtered_records
        else:
            records = all_records

        total_count = len(records)
        paginated_records = records[filter_params.offset : filter_params.offset + filter_params.limit]

        events: List[TimelineEvent] = []
        event_distribution: Dict[str, int] = {}
        earliest_ts: Optional[str] = None
        latest_ts: Optional[str] = None

        for rec in paginated_records:
            actor, target = self._extract_actor_and_target(rec)
            summary = self._build_content_summary(rec)
            ts_str = rec.event_timestamp.isoformat() if rec.event_timestamp else None

            if ts_str:
                if earliest_ts is None or ts_str < earliest_ts:
                    earliest_ts = ts_str
                if latest_ts is None or ts_str > latest_ts:
                    latest_ts = ts_str

            type_name = rec.artifact_type.value if hasattr(rec.artifact_type, "value") else str(rec.artifact_type)
            event_distribution[type_name] = event_distribution.get(type_name, 0) + 1

            event_id = f"{case_id}:{rec.id}"
            events.append(
                TimelineEvent(
                    event_id=event_id,
                    case_id=rec.case_id,
                    evidence_id=rec.evidence_id,
                    artifact_id=rec.id,
                    raw_artifact_id=rec.raw_artifact_id,
                    timestamp=ts_str,
                    timestamp_precision=rec.timestamp_precision or TimestampPrecision.UNKNOWN,
                    timestamp_status=rec.timestamp_status or TimestampStatus.UNKNOWN,
                    timezone=rec.original_timezone,
                    event_type=rec.artifact_type,
                    application=rec.application,
                    actor=actor,
                    target=target,
                    device=rec.device_id,
                    content_summary=summary,
                    source_file=rec.source_file,
                    source_path=rec.source_path,
                    metadata=rec.metadata_ or {},
                )
            )

        # Record audit log
        from backend.app.services.audit_service import AuditService
        audit_service = AuditService(session)
        await audit_service.record_event(
            action=AuditAction.TIMELINE_GENERATED.value if hasattr(AuditAction.TIMELINE_GENERATED, "value") else str(AuditAction.TIMELINE_GENERATED),
            resource_type="timeline",
            status="SUCCESS",
            user_id=current_user.id,
            resource_id=str(case_id),
            case_id=case_id,
            details={
                "total_events": total_count,
                "returned_events": len(events),
                "filter_start": filter_params.start_time,
                "filter_end": filter_params.end_time,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return TimelineResponse(
            case_id=case_id,
            total_events=total_count,
            events=events,
            earliest_timestamp=earliest_ts,
            latest_timestamp=latest_ts,
            event_distribution=event_distribution,
        )


timeline_service = TimelineService()
