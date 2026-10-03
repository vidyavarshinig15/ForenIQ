from datetime import datetime, timezone
import hashlib
from typing import Optional
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import (
    CaseNotFoundException,
    ForensicAppException,
    PermissionDeniedException,
)
from backend.app.core.logging import get_logger
from backend.app.models.enums import (
    AuditAction,
    CaseAccessRole,
    CustodyEventType,
    EvidenceStatus,
    IntegrityStatus,
    UserRole,
)
from backend.app.models.evidence import Evidence
from backend.app.models.user import User
from backend.app.repositories.case_repo import CaseRepository
from backend.app.repositories.evidence_repo import EvidenceRepository
from backend.app.schemas.custody import IntegrityVerificationResult
from backend.app.services.audit_service import AuditService
from backend.app.services.custody_service import CustodyService
from backend.app.services.storage.local import LocalStorageService

logger = get_logger("integrity.service")


class IntegrityService:
    """
    Forensic Integrity Verification Service.
    Determines whether stored original evidence archives have remained byte-for-byte identical
    to their recorded ingestion SHA-256 digest using streaming chunked verification.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.evidence_repo = EvidenceRepository(session)
        self.case_repo = CaseRepository(session)
        self.custody_service = CustodyService(session)
        self.audit_service = AuditService(session)
        self.storage = LocalStorageService()

    async def _verify_case_and_role(
        self, case_id: UUID, current_user: User, allow_viewer: bool = False
    ):
        """Authorizes case access and verifies user permission."""
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise CaseNotFoundException(f"Case with ID {case_id} does not exist.")

        if current_user.role == UserRole.ADMIN:
            return case

        membership = await self.case_repo.get_membership(case_id, current_user.id)
        if not membership:
            raise PermissionDeniedException("You are not an authorized member of this case.")

        if not allow_viewer and current_user.role == UserRole.VIEWER:
            raise PermissionDeniedException("System role 'VIEWER' is not permitted to trigger integrity verification.")

        return case

    async def verify_evidence_integrity(
        self,
        case_id: UUID,
        evidence_id: UUID,
        current_user: User,
        client_ip: str = "unknown",
    ) -> IntegrityVerificationResult:
        """
        Executes an on-demand cryptographic integrity check on stored evidence:
        1. Confirms case authorization.
        2. Streams physical file in 64KB blocks, updating SHA-256 in memory (zero full-RAM buffering).
        3. Compares calculated digest against the baseline ingestion hash.
        4. If matched -> marks VALID.
        5. If mismatched -> preserves baseline hash, marks MISMATCH, flags QUARANTINED, and logs tamper event.
        6. If file missing -> marks MISSING.
        """
        await self._verify_case_and_role(case_id, current_user, allow_viewer=False)

        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence record not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        now_utc = datetime.now(timezone.utc)

        # Audit verification started
        await self.audit_service.record_event(
            action=AuditAction.INTEGRITY_VERIFICATION_STARTED.value,
            resource_type="evidence_integrity",
            resource_id=str(evidence_id),
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            client_ip=client_ip,
            details={"original_filename": evidence.original_filename},
        )

        # Check physical existence in storage
        file_exists = await self.storage.exists(evidence.storage_path_or_key)
        if not file_exists:
            logger.error(
                f"Evidence file missing from storage during integrity check: id={evidence_id}, path={evidence.storage_path_or_key}"
            )
            evidence.integrity_status = IntegrityStatus.MISSING
            evidence.last_integrity_check_at = now_utc
            await self.session.commit()

            # Record custody event for missing evidence
            await self.custody_service.record_event(
                evidence_id=evidence_id,
                case_id=case_id,
                event_type=CustodyEventType.INTEGRITY_MISMATCH,
                actor_user_id=current_user.id,
                metadata={
                    "status": "MISSING",
                    "reason": "Physical evidence file not found in storage repository.",
                },
                timestamp=now_utc,
            )

            # Record audit event
            await self.audit_service.record_event(
                action=AuditAction.INTEGRITY_MISMATCH_DETECTED.value,
                resource_type="evidence_integrity",
                resource_id=str(evidence_id),
                user_id=current_user.id,
                case_id=case_id,
                status="FAILURE",
                client_ip=client_ip,
                details={"reason": "FILE_MISSING_FROM_STORAGE"},
            )

            return IntegrityVerificationResult(
                evidence_id=evidence_id,
                case_id=case_id,
                original_filename=evidence.original_filename,
                stored_hash=evidence.sha256_hash or "",
                calculated_hash=None,
                integrity_status=IntegrityStatus.MISSING,
                match=False,
                details="Evidence file could not be located in storage.",
                verified_at=now_utc,
            )

        # Streaming incremental SHA-256 calculation
        hasher = hashlib.sha256()
        try:
            stream = self.storage.get_stream(evidence.storage_path_or_key)
            async for chunk in stream:
                hasher.update(chunk)
            calculated_hash = hasher.hexdigest()
        except Exception as read_err:
            logger.error(f"Error reading evidence stream for verification: {read_err}")
            evidence.integrity_status = IntegrityStatus.ERROR
            evidence.last_integrity_check_at = now_utc
            await self.session.commit()

            return IntegrityVerificationResult(
                evidence_id=evidence_id,
                case_id=case_id,
                original_filename=evidence.original_filename,
                stored_hash=evidence.sha256_hash or "",
                calculated_hash=None,
                integrity_status=IntegrityStatus.ERROR,
                match=False,
                details=f"Read error during integrity check: {read_err}",
                verified_at=now_utc,
            )

        stored_hash = evidence.sha256_hash or ""
        is_match = (calculated_hash.lower() == stored_hash.lower())

        if is_match:
            evidence.integrity_status = IntegrityStatus.VALID
            evidence.last_integrity_check_at = now_utc
            await self.session.commit()

            # Record custody event
            await self.custody_service.record_event(
                evidence_id=evidence_id,
                case_id=case_id,
                event_type=CustodyEventType.INTEGRITY_VERIFIED,
                actor_user_id=current_user.id,
                metadata={
                    "sha256": calculated_hash,
                    "result": "MATCH",
                },
                timestamp=now_utc,
            )

            # Record audit event
            await self.audit_service.record_event(
                action=AuditAction.INTEGRITY_VERIFICATION_COMPLETED.value,
                resource_type="evidence_integrity",
                resource_id=str(evidence_id),
                user_id=current_user.id,
                case_id=case_id,
                status="SUCCESS",
                client_ip=client_ip,
                details={"result": "VALID", "sha256": calculated_hash},
            )

            return IntegrityVerificationResult(
                evidence_id=evidence_id,
                case_id=case_id,
                original_filename=evidence.original_filename,
                stored_hash=stored_hash,
                calculated_hash=calculated_hash,
                integrity_status=IntegrityStatus.VALID,
                match=True,
                details="Current stored file SHA-256 matches recorded baseline.",
                verified_at=now_utc,
            )
        else:
            # Forensic Integrity Mismatch Detected!
            # Preserves original stored hash without overwriting.
            logger.warning(
                f"FORENSIC INTEGRITY MISMATCH: evidence_id={evidence_id}, stored={stored_hash}, current={calculated_hash}"
            )
            evidence.integrity_status = IntegrityStatus.MISMATCH
            evidence.status = EvidenceStatus.QUARANTINED
            evidence.last_integrity_check_at = now_utc
            await self.session.commit()

            # Record custody event
            await self.custody_service.record_event(
                evidence_id=evidence_id,
                case_id=case_id,
                event_type=CustodyEventType.INTEGRITY_MISMATCH,
                actor_user_id=current_user.id,
                metadata={
                    "stored_hash": stored_hash,
                    "calculated_hash": calculated_hash,
                    "action_taken": "QUARANTINED",
                },
                timestamp=now_utc,
            )

            # Record audit event
            await self.audit_service.record_event(
                action=AuditAction.INTEGRITY_MISMATCH_DETECTED.value,
                resource_type="evidence_integrity",
                resource_id=str(evidence_id),
                user_id=current_user.id,
                case_id=case_id,
                status="FAILURE",
                client_ip=client_ip,
                details={
                    "stored_hash": stored_hash,
                    "calculated_hash": calculated_hash,
                },
            )

            return IntegrityVerificationResult(
                evidence_id=evidence_id,
                case_id=case_id,
                original_filename=evidence.original_filename,
                stored_hash=stored_hash,
                calculated_hash=calculated_hash,
                integrity_status=IntegrityStatus.MISMATCH,
                match=False,
                details="Cryptographic mismatch detected: file content differs from ingestion baseline.",
                verified_at=now_utc,
            )
