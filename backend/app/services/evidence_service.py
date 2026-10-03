import os
from typing import AsyncIterator, List, Optional, Tuple
from uuid import UUID, uuid4
from fastapi import UploadFile, status

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
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
from backend.app.schemas.evidence import EvidenceResponse
from backend.app.services.audit_service import AuditService
from backend.app.services.custody_service import CustodyService
from backend.app.services.evidence_validator import EvidenceValidator
from backend.app.services.storage.local import LocalStorageService

logger = get_logger("evidence.service")


class EvidenceService:
    """
    Coordinates forensic evidence ingestion, streaming upload, defensive archive inspection,
    access authorization, safe storage management, tamper-evident custody logging, and audit logging.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.evidence_repo = EvidenceRepository(session)
        self.case_repo = CaseRepository(session)
        self.audit_service = AuditService(session)
        self.custody_service = CustodyService(session)
        self.storage = LocalStorageService()
        self.validator = EvidenceValidator()

    def _format_evidence_response(self, ev: Evidence) -> EvidenceResponse:
        """Transforms DB entity to API schema with sanitized paths."""
        return EvidenceResponse(
            id=ev.id,
            case_id=ev.case_id,
            original_filename=ev.original_filename,
            stored_filename=ev.stored_filename,
            file_size=ev.file_size,
            mime_type=ev.mime_type,
            detected_mime_type=ev.detected_mime_type,
            file_extension=ev.file_extension,
            status=ev.status,
            sha256_hash=ev.sha256_hash,
            integrity_status=ev.integrity_status,
            last_integrity_check_at=ev.last_integrity_check_at,
            uploaded_by=ev.uploaded_by,
            uploader_name=ev.uploader.name if ev.uploader else None,
            uploader_email=ev.uploader.email if ev.uploader else None,
            uploaded_at=ev.uploaded_at,
            created_at=ev.created_at,
            updated_at=ev.updated_at,
        )


    async def _verify_case_and_membership(
        self, case_id: UUID, user: User, required_upload: bool = False
    ):
        """
        Validates case existence and verifies the user has case-level access.
        Enforces strict IDOR defense.
        """
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise CaseNotFoundException(f"Case with ID {case_id} does not exist.")

        if user.role == UserRole.ADMIN:
            return case, None

        membership = await self.case_repo.get_membership(case_id, user.id)
        if not membership:
            raise PermissionDeniedException("You are not an authorized member of this case.")

        if required_upload:
            if user.role == UserRole.VIEWER:
                raise PermissionDeniedException("System role 'VIEWER' is not permitted to upload evidence.")
            if membership.access_role not in (CaseAccessRole.LEAD, CaseAccessRole.CONTRIBUTOR):
                raise PermissionDeniedException(
                    f"Case access role '{membership.access_role.value}' does not permit evidence upload."
                )

        return case, membership

    async def upload_evidence(
        self,
        current_user: User,
        case_id: UUID,
        file: UploadFile,
        client_ip: str = "unknown",
    ) -> EvidenceResponse:
        """
        Handles secure, streaming multipart upload of forensic archives:
        1. Authorizes case access & upload permission.
        2. Validates filename and allowed extension.
        3. Streams file directly to isolated staging storage while calculating SHA-256 in-flight.
        4. Defensively inspects archive (magic bytes, ZipSlip, ZipBomb ratio) without full extraction.
        5. Atomically commits to immutable storage and records database entry.
        6. Emits tamper-evident audit logs.
        """
        # 1. Authorization
        await self._verify_case_and_membership(case_id, current_user, required_upload=True)

        # 2. Filename & extension validation
        original_name = file.filename or "unknown_evidence.bin"
        # Sanitize original name to prevent header injection or control characters in display
        safe_display_name = os.path.basename(original_name).strip()
        is_valid_ext, ext_err, file_ext = self.validator.validate_file_extension(safe_display_name)
        if not is_valid_ext:
            await self.audit_service.record_event(
                action=AuditAction.EVIDENCE_VALIDATION_FAILED.value,
                resource_type="evidence",
                user_id=current_user.id,
                case_id=case_id,
                status="FAILURE",
                client_ip=client_ip,
                details={"filename": safe_display_name, "reason": ext_err},
            )
            raise ForensicAppException(
                message=ext_err or "Invalid file extension.",
                code="INVALID_FILE_TYPE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        settings = get_settings()
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        evidence_id = uuid4()
        storage_key = self.storage.get_safe_storage_key(case_id, evidence_id, file_ext)

        # Audit upload started
        await self.audit_service.record_event(
            action=AuditAction.EVIDENCE_UPLOAD_STARTED.value,
            resource_type="evidence",
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            client_ip=client_ip,
            details={"filename": safe_display_name, "evidence_id": str(evidence_id)},
        )

        # 3. Stream upload directly to disk with in-flight SHA-256 hashing
        async def file_stream():
            while True:
                chunk = await file.read(65536)
                if not chunk:
                    break
                yield chunk

        try:
            total_bytes, sha256_hash = await self.storage.store_stream(
                file_stream(), storage_key, max_size_bytes=max_bytes
            )
        except Exception as upload_err:
            await self.audit_service.record_event(
                action=AuditAction.EVIDENCE_UPLOAD_FAILED.value,
                resource_type="evidence",
                user_id=current_user.id,
                case_id=case_id,
                status="FAILURE",
                client_ip=client_ip,
                details={"filename": safe_display_name, "error": str(upload_err)},
            )
            raise upload_err

        # 4. Defensive archive inspection
        abs_file_path = self.storage.get_absolute_path_for_validation(storage_key)
        is_valid_archive, archive_err, detected_mime = self.validator.validate_stored_archive(
            abs_file_path, file_ext
        )

        if not is_valid_archive:
            # Purge the invalid stored file to avoid corrupted/dangerous artifacts
            await self.storage.delete(storage_key)

            await self.audit_service.record_event(
                action=AuditAction.EVIDENCE_VALIDATION_FAILED.value,
                resource_type="evidence",
                user_id=current_user.id,
                case_id=case_id,
                status="FAILURE",
                client_ip=client_ip,
                details={
                    "filename": safe_display_name,
                    "sha256": sha256_hash,
                    "reason": archive_err,
                },
            )
            raise ForensicAppException(
                message=f"Archive validation failed: {archive_err}",
                code="EVIDENCE_VALIDATION_FAILED",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 5. Persist Evidence DB record
        stored_filename = os.path.basename(storage_key)
        evidence = Evidence(
            id=evidence_id,
            case_id=case_id,
            original_filename=safe_display_name,
            stored_filename=stored_filename,
            storage_path_or_key=storage_key,
            file_size=total_bytes,
            mime_type=file.content_type or "application/octet-stream",
            detected_mime_type=detected_mime,
            file_extension=file_ext,
            status=EvidenceStatus.VALID,
            sha256_hash=sha256_hash,
            uploaded_by=current_user.id,
        )

        try:
            saved_evidence = await self.evidence_repo.create(evidence)
        except Exception as db_err:
            # Failure recovery: if DB write fails, eliminate stored file to prevent inconsistency
            logger.error(f"Database commit failed for evidence record: {db_err}")
            await self.storage.delete(storage_key)
            raise ForensicAppException(
                message="Failed to persist evidence record in database.",
                code="DATABASE_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 6. Record Initial Chain of Custody Events
        await self.custody_service.record_event(
            evidence_id=saved_evidence.id,
            case_id=case_id,
            event_type=CustodyEventType.EVIDENCE_UPLOADED,
            actor_user_id=current_user.id,
            metadata={"original_filename": safe_display_name, "file_size": total_bytes},
        )
        await self.custody_service.record_event(
            evidence_id=saved_evidence.id,
            case_id=case_id,
            event_type=CustodyEventType.EVIDENCE_HASHED,
            actor_user_id=None,  # System-calculated
            metadata={"sha256": sha256_hash, "algorithm": "SHA-256"},
        )
        await self.custody_service.record_event(
            evidence_id=saved_evidence.id,
            case_id=case_id,
            event_type=CustodyEventType.EVIDENCE_VALIDATED,
            actor_user_id=None,  # System-validated
            metadata={"detected_mime": detected_mime, "file_extension": file_ext},
        )

        # 7. Audit Log: Upload Completed
        await self.audit_service.record_event(
            action=AuditAction.EVIDENCE_UPLOAD_COMPLETED.value,
            resource_type="evidence",
            resource_id=str(saved_evidence.id),
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            client_ip=client_ip,
            details={
                "evidence_id": str(saved_evidence.id),
                "original_filename": safe_display_name,
                "file_size": total_bytes,
                "sha256": sha256_hash,
            },
        )

        return self._format_evidence_response(saved_evidence)


    async def list_evidence(
        self,
        current_user: User,
        case_id: UUID,
        skip: int = 0,
        limit: int = 50,
        client_ip: str = "unknown",
    ) -> List[EvidenceResponse]:
        """Lists evidence items strictly belonging to authorized case."""
        await self._verify_case_and_membership(case_id, current_user, required_upload=False)

        items = await self.evidence_repo.list_by_case(case_id, skip=skip, limit=limit)

        await self.audit_service.record_event(
            action=AuditAction.EVIDENCE_ACCESSED.value,
            resource_type="evidence",
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            client_ip=client_ip,
            details={"action": "list", "count": len(items)},
        )

        return [self._format_evidence_response(ev) for ev in items]

    async def get_evidence(
        self,
        current_user: User,
        case_id: UUID,
        evidence_id: UUID,
        client_ip: str = "unknown",
    ) -> EvidenceResponse:
        """Retrieves individual evidence item metadata with IDOR verification."""
        await self._verify_case_and_membership(case_id, current_user, required_upload=False)

        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence record not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Record Custody Event: Metadata Accessed
        await self.custody_service.record_event(
            evidence_id=evidence_id,
            case_id=case_id,
            event_type=CustodyEventType.EVIDENCE_ACCESSED,
            actor_user_id=current_user.id,
            metadata={"action": "view_details", "filename": evidence.original_filename},
        )

        await self.audit_service.record_event(
            action=AuditAction.EVIDENCE_ACCESSED.value,
            resource_type="evidence",
            resource_id=str(evidence_id),
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            client_ip=client_ip,
            details={"action": "view_details", "filename": evidence.original_filename},
        )

        return self._format_evidence_response(evidence)

    async def quarantine_evidence(
        self,
        current_user: User,
        case_id: UUID,
        evidence_id: UUID,
        client_ip: str = "unknown",
    ) -> EvidenceResponse:
        """
        Controlled lifecycle operation: marks evidence as QUARANTINED.
        Forensic preservation: original files are never deleted or erased through this action.
        """
        case, membership = await self._verify_case_and_membership(
            case_id, current_user, required_upload=False
        )

        is_lead_or_admin = (
            current_user.role == UserRole.ADMIN
            or (membership and membership.access_role == CaseAccessRole.LEAD)
        )
        if not is_lead_or_admin:
            raise PermissionDeniedException("Only Case LEAD or ADMIN can quarantine evidence.")

        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence record not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        updated_evidence = await self.evidence_repo.update_status(
            evidence_id, EvidenceStatus.QUARANTINED
        )

        # Record Custody Event: Evidence Quarantined
        await self.custody_service.record_event(
            evidence_id=evidence_id,
            case_id=case_id,
            event_type=CustodyEventType.EVIDENCE_QUARANTINED,
            actor_user_id=current_user.id,
            metadata={"reason": "Manual investigator quarantine action"},
        )

        await self.audit_service.record_event(
            action=AuditAction.EVIDENCE_QUARANTINED.value,
            resource_type="evidence",
            resource_id=str(evidence_id),
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            client_ip=client_ip,
            details={"filename": evidence.original_filename, "status": "QUARANTINED"},
        )

        return self._format_evidence_response(updated_evidence)

    async def get_download_stream(
        self,
        current_user: User,
        case_id: UUID,
        evidence_id: UUID,
        client_ip: str = "unknown",
    ) -> Tuple[AsyncIterator[bytes], Evidence]:
        """
        Retrieves streaming binary content for authorized investigator download.
        """
        await self._verify_case_and_membership(case_id, current_user, required_upload=False)

        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence record not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if evidence.status in (EvidenceStatus.FAILED, EvidenceStatus.INVALID):
            raise ForensicAppException(
                message="Cannot download invalid or failed evidence archive.",
                code="EVIDENCE_INVALID_STATUS",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        exists = await self.storage.exists(evidence.storage_path_or_key)
        if not exists:
            raise ForensicAppException(
                message="Evidence file not found in storage.",
                code="FILE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        stream = self.storage.get_stream(evidence.storage_path_or_key)

        # Record Custody Event: Evidence Downloaded
        await self.custody_service.record_event(
            evidence_id=evidence_id,
            case_id=case_id,
            event_type=CustodyEventType.EVIDENCE_DOWNLOADED,
            actor_user_id=current_user.id,
            metadata={
                "filename": evidence.original_filename,
                "sha256": evidence.sha256_hash,
                "file_size": evidence.file_size,
            },
        )

        await self.audit_service.record_event(
            action=AuditAction.EVIDENCE_DOWNLOADED.value,
            resource_type="evidence",
            resource_id=str(evidence_id),
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            client_ip=client_ip,
            details={
                "filename": evidence.original_filename,
                "sha256": evidence.sha256_hash,
                "file_size": evidence.file_size,
            },
        )

        return stream, evidence

