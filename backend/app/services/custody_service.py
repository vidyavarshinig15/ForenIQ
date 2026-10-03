from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import ForensicAppException
from backend.app.core.logging import get_logger
from backend.app.models.custody import EvidenceCustodyEvent
from backend.app.models.enums import AuditAction, CustodyEventType
from backend.app.repositories.custody_repo import CustodyRepository
from backend.app.schemas.custody import (
    CustodyChainVerificationResult,
    EvidenceCustodyEventResponse,
)
from backend.app.services.audit_service import AuditService

logger = get_logger("custody.service")


class CustodyService:
    """
    Manages append-only, tamper-evident Chain of Custody events for forensic evidence.
    Enforces cryptographic linkage (hash chain) across consecutive lifecycle events.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CustodyRepository(session)
        self.audit_service = AuditService(session)

    @staticmethod
    def _canonical_timestamp(dt: datetime) -> str:
        """Normalizes datetime to UTC ISO8601 string with second resolution for database portability."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def compute_event_hash(
        cls,
        sequence_number: int,
        evidence_id: UUID,
        case_id: UUID,
        actor_user_id: Optional[UUID],
        event_type: CustodyEventType,
        timestamp: datetime,
        previous_event_hash: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> str:
        """
        Deterministic canonical serialization for computing tamper-evident event hashes.
        Keys are sorted and delimiters are fixed without arbitrary whitespace.
        """
        norm_meta = json.loads(json.dumps(metadata)) if metadata else {}
        canonical_dict = {
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "case_id": str(case_id),
            "event_type": event_type.value,
            "evidence_id": str(evidence_id),
            "metadata": norm_meta,
            "previous_event_hash": previous_event_hash,
            "sequence_number": sequence_number,
            "timestamp": cls._canonical_timestamp(timestamp),
        }
        canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


    async def record_event(
        self,
        evidence_id: UUID,
        case_id: UUID,
        event_type: CustodyEventType,
        actor_user_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> EvidenceCustodyEvent:
        """
        Appends a new immutable custody event linked cryptographically to the preceding event.
        """
        event_time = timestamp or datetime.now(timezone.utc)
        latest_event = await self.repo.get_latest_event(evidence_id)

        if latest_event:
            sequence_number = latest_event.sequence_number + 1
            previous_event_id = latest_event.id
            previous_event_hash = latest_event.event_hash
        else:
            sequence_number = 1
            previous_event_id = None
            previous_event_hash = None

        event_hash = self.compute_event_hash(
            sequence_number=sequence_number,
            evidence_id=evidence_id,
            case_id=case_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            timestamp=event_time,
            previous_event_hash=previous_event_hash,
            metadata=metadata,
        )

        metadata_str = json.dumps(metadata, sort_keys=True) if metadata else None

        custody_event = EvidenceCustodyEvent(
            id=uuid4(),
            evidence_id=evidence_id,
            case_id=case_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            timestamp=event_time,
            sequence_number=sequence_number,
            previous_event_id=previous_event_id,
            previous_event_hash=previous_event_hash,
            event_hash=event_hash,
            metadata_json=metadata_str,
        )

        saved = await self.repo.create_event(custody_event)
        logger.info(
            f"Custody event recorded: evidence_id={evidence_id}, type={event_type.value}, seq={sequence_number}, hash={event_hash[:12]}..."
        )
        return saved

    async def list_events(
        self, case_id: UUID, evidence_id: UUID
    ) -> List[EvidenceCustodyEventResponse]:
        """
        Retrieves ordered custody history for an evidence item.
        """
        events = await self.repo.list_events_for_evidence(evidence_id)
        responses: List[EvidenceCustodyEventResponse] = []

        for ev in events:
            parsed_meta = json.loads(ev.metadata_json) if ev.metadata_json else None
            responses.append(
                EvidenceCustodyEventResponse(
                    id=ev.id,
                    evidence_id=ev.evidence_id,
                    case_id=ev.case_id,
                    actor_user_id=ev.actor_user_id,
                    actor_name=ev.actor.name if ev.actor else None,
                    actor_email=ev.actor.email if ev.actor else None,
                    event_type=ev.event_type,
                    timestamp=ev.timestamp,
                    sequence_number=ev.sequence_number,
                    previous_event_id=ev.previous_event_id,
                    previous_event_hash=ev.previous_event_hash,
                    event_hash=ev.event_hash,
                    metadata=parsed_meta,
                )
            )
        return responses

    async def verify_custody_chain(
        self, case_id: UUID, evidence_id: UUID, current_user_id: Optional[UUID] = None
    ) -> CustodyChainVerificationResult:
        """
        Recalculates cryptographic hashes of all sequential custody events for an evidence item.
        Verifies previous_event_hash pointers to detect tampering or broken chains.
        """
        events = await self.repo.list_events_for_evidence(evidence_id)
        verified_time = datetime.now(timezone.utc)

        if not events:
            return CustodyChainVerificationResult(
                evidence_id=evidence_id,
                case_id=case_id,
                status="VALID",
                events_checked=0,
                details="No custody events recorded for this evidence item.",
                verified_at=verified_time,
            )

        expected_prev_hash: Optional[str] = None

        for idx, ev in enumerate(events):
            # 1. Verify sequence order
            expected_seq = idx + 1
            if ev.sequence_number != expected_seq:
                logger.warning(
                    f"Custody chain sequence break: expected {expected_seq}, found {ev.sequence_number}"
                )
                return CustodyChainVerificationResult(
                    evidence_id=evidence_id,
                    case_id=case_id,
                    status="INVALID",
                    events_checked=idx,
                    details=f"Sequence number mismatch at index {idx}: expected {expected_seq}, got {ev.sequence_number}.",
                    verified_at=verified_time,
                )

            # 2. Verify previous event hash linkage
            if ev.previous_event_hash != expected_prev_hash:
                logger.warning(
                    f"Custody chain linkage broken at seq {ev.sequence_number}: expected {expected_prev_hash}, got {ev.previous_event_hash}"
                )
                return CustodyChainVerificationResult(
                    evidence_id=evidence_id,
                    case_id=case_id,
                    status="INVALID",
                    events_checked=idx,
                    details=f"Previous event hash linkage broken at sequence {ev.sequence_number}.",
                    verified_at=verified_time,
                )

            # 3. Recalculate event hash from canonical payload
            parsed_meta = json.loads(ev.metadata_json) if ev.metadata_json else None
            recalculated_hash = self.compute_event_hash(
                sequence_number=ev.sequence_number,
                evidence_id=ev.evidence_id,
                case_id=ev.case_id,
                actor_user_id=ev.actor_user_id,
                event_type=ev.event_type,
                timestamp=ev.timestamp,
                previous_event_hash=ev.previous_event_hash,
                metadata=parsed_meta,
            )

            if recalculated_hash != ev.event_hash:
                logger.warning(
                    f"Custody event payload altered at seq {ev.sequence_number}: stored {ev.event_hash}, calculated {recalculated_hash}"
                )
                return CustodyChainVerificationResult(
                    evidence_id=evidence_id,
                    case_id=case_id,
                    status="INVALID",
                    events_checked=idx,
                    details=f"Tampered event content detected at sequence {ev.sequence_number}: hash digest mismatch.",
                    verified_at=verified_time,
                )

            expected_prev_hash = ev.event_hash

        # Audit verification
        await self.audit_service.record_event(
            action=AuditAction.CUSTODY_CHAIN_VERIFICATION_COMPLETED.value,
            resource_type="evidence_custody",
            resource_id=str(evidence_id),
            user_id=current_user_id,
            case_id=case_id,
            status="SUCCESS",
            details={"events_checked": len(events), "result": "VALID"},
        )

        return CustodyChainVerificationResult(
            evidence_id=evidence_id,
            case_id=case_id,
            status="VALID",
            events_checked=len(events),
            details=f"Successfully verified cryptographic integrity of {len(events)} custody events.",
            verified_at=verified_time,
        )
