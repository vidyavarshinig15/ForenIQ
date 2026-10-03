import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import (
    CaseNotFoundException,
    ForensicAppException,
    PermissionDeniedException,
)
from backend.app.models.enums import (
    ArtifactType,
    AuditAction,
    CaseAccessRole,
    DataQualityStatus,
    EvidenceStatus,
    IntegrityStatus,
    JobPriority,
    JobStatus,
    JobType,
    ProcessingStage,
    UserRole,
)
from backend.app.queue.factory import get_job_queue
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.raw_artifact import RawArtifact
from backend.app.models.user import User
from backend.app.repositories.canonical_evidence_repo import CanonicalEvidenceRepository
from backend.app.repositories.case_repo import CaseRepository
from backend.app.repositories.evidence_repo import EvidenceRepository
from backend.app.repositories.processing_job_repo import ProcessingJobRepository
from backend.app.repositories.raw_artifact_repo import RawArtifactRepository
from backend.app.schemas.canonical_evidence import (
    CanonicalCursorPageResponse,
    CanonicalEvidenceListResponse,
    CanonicalEvidenceResponse,
    CaseCanonicalSummaryResponse,
)
from backend.app.schemas.processing_job import ProcessingJobResponse
from backend.app.schemas.raw_artifact import RawArtifactListResponse, RawArtifactResponse
from backend.app.services.audit_service import AuditService
from backend.app.services.normalization_worker import EvidenceNormalizationWorker
from backend.app.services.parser_worker import UFDRParserWorker

logger = logging.getLogger(__name__)


class ProcessingService:
    """
    Forensic Processing Service.
    Coordinates job lifecycle management, case authorization, worker dispatch,
    and raw & canonical artifact access with source provenance.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = ProcessingJobRepository(session)
        self.evidence_repo = EvidenceRepository(session)
        self.case_repo = CaseRepository(session)
        self.artifact_repo = RawArtifactRepository(session)
        self.canonical_repo = CanonicalEvidenceRepository(session)
        self.audit_service = AuditService(session)
        self.worker = UFDRParserWorker()
        self.norm_worker = EvidenceNormalizationWorker()

    async def _verify_case_and_membership(
        self, case_id: UUID, user: User, require_write: bool = False
    ):
        """Authorizes case access and enforces role-based restrictions."""
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise CaseNotFoundException(f"Case with ID {case_id} does not exist.")

        if user.role == UserRole.ADMIN:
            return case, None

        membership = await self.case_repo.get_membership(case_id, user.id)
        if not membership:
            raise PermissionDeniedException("You are not an authorized member of this case.")

        if require_write:
            if user.role == UserRole.VIEWER:
                raise PermissionDeniedException("System role 'VIEWER' is not permitted to initiate parsing.")
            if membership.access_role == CaseAccessRole.VIEWER:
                raise PermissionDeniedException("Case access role 'VIEWER' is not permitted to initiate parsing.")

        return case, membership

    async def start_parsing_job(
        self,
        case_id: UUID,
        evidence_id: UUID,
        current_user: User,
        background_tasks: BackgroundTasks,
        priority: JobPriority = JobPriority.NORMAL,
        client_ip: Optional[str] = None,
    ) -> ProcessingJobResponse:
        """
        Validates evidence pre-conditions, creates an asynchronous ProcessingJob,
        and enqueues the worker execution.
        """
        await self._verify_case_and_membership(case_id, current_user, require_write=True)

        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence record not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Integrity status verification
        if evidence.integrity_status == IntegrityStatus.MISMATCH or evidence.status == EvidenceStatus.QUARANTINED:
            logger.warning(
                f"User {current_user.id} attempted to parse compromised evidence {evidence.id} in case {case_id}."
            )
            await self.audit_service.record_event(
                action=AuditAction.PROCESSING_JOB_FAILED.value,
                resource_type="processing_job",
                resource_id=str(evidence.id),
                user_id=current_user.id,
                case_id=case_id,
                status="BLOCKED",
                client_ip=client_ip,
                details={"reason": "INTEGRITY_MISMATCH_PREVENTED_PARSING"},
            )
            raise ForensicAppException(
                message="Cannot parse evidence: Cryptographic integrity mismatch detected. Original evidence is quarantined.",
                code="INTEGRITY_MISMATCH",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check for existing active job
        active_job = await self.job_repo.get_active_job_for_evidence(evidence_id)
        if active_job:
            logger.info(f"Active processing job {active_job.id} already exists for evidence {evidence_id}")
            return ProcessingJobResponse.model_validate(active_job)

        # Enforce non-admin priority limit (prevent queue starvation)
        final_priority = priority
        if current_user.role != UserRole.ADMIN and priority == JobPriority.HIGH:
            final_priority = JobPriority.NORMAL

        # Create new processing job
        job = await self.job_repo.create_job(
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=current_user.id,
            job_type=JobType.UFDR_PARSE,
            priority=final_priority,
        )

        # Enqueue into persistent queue
        queue = await get_job_queue()
        await queue.enqueue(job.id, priority=final_priority)

        # Dispatch background task for immediate local processing
        background_tasks.add_task(self.worker.execute_job, job.id)

        await self.audit_service.record_event(
            action=AuditAction.PROCESSING_JOB_CREATED.value,
            resource_type="processing_job",
            resource_id=str(job.id),
            user_id=current_user.id,
            case_id=case_id,
            status="QUEUED",
            client_ip=client_ip,
            details={"evidence_id": str(evidence_id), "priority": final_priority.value},
        )

        return ProcessingJobResponse.model_validate(job)

    async def cancel_job(
        self, case_id: UUID, job_id: UUID, current_user: User, client_ip: Optional[str] = None
    ) -> ProcessingJobResponse:
        """Cooperative job cancellation."""
        await self._verify_case_and_membership(case_id, current_user, require_write=True)

        job = await self.job_repo.get_by_id(job_id)
        if not job or job.case_id != case_id:
            raise ForensicAppException(
                message="Processing job not found in this case.",
                code="PROCESSING_JOB_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            raise ForensicAppException(
                message=f"Cannot cancel job in terminal state '{job.status.value}'.",
                code="JOB_TERMINAL",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        cancelled = await self.job_repo.request_cancellation(job_id)
        await self.audit_service.record_event(
            action=AuditAction.PROCESSING_JOB_CANCEL_REQUESTED.value,
            resource_type="processing_job",
            resource_id=str(job_id),
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            client_ip=client_ip,
        )
        return ProcessingJobResponse.model_validate(cancelled)

    async def retry_job(
        self,
        case_id: UUID,
        job_id: UUID,
        current_user: User,
        background_tasks: BackgroundTasks,
        client_ip: Optional[str] = None,
    ) -> ProcessingJobResponse:
        """Retry a failed or cancelled processing job."""
        await self._verify_case_and_membership(case_id, current_user, require_write=True)

        job = await self.job_repo.get_by_id(job_id)
        if not job or job.case_id != case_id:
            raise ForensicAppException(
                message="Processing job not found in this case.",
                code="PROCESSING_JOB_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.PARTIAL):
            raise ForensicAppException(
                message=f"Only failed or cancelled jobs can be retried (current status: {job.status.value}).",
                code="INVALID_RETRY_STATE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        job.status = JobStatus.QUEUED
        job.error_message = None
        job.completed_at = None
        job.current_stage = ProcessingStage.VALIDATING.value
        await self.session.commit()
        await self.session.refresh(job)

        queue = await get_job_queue()
        await queue.enqueue(job.id, priority=job.priority)
        background_tasks.add_task(self.worker.execute_job, job.id)

        await self.audit_service.record_event(
            action=AuditAction.PROCESSING_JOB_RETRIED.value,
            resource_type="processing_job",
            resource_id=str(job_id),
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            client_ip=client_ip,
        )
        return ProcessingJobResponse.model_validate(job)

    async def get_job_status(
        self, case_id: UUID, job_id: UUID, current_user: User
    ) -> ProcessingJobResponse:
        """Fetch current processing job status."""
        await self._verify_case_and_membership(case_id, current_user, require_write=False)

        job = await self.job_repo.get_by_id(job_id)
        if not job or job.case_id != case_id:
            raise ForensicAppException(
                message="Processing job not found in this case.",
                code="PROCESSING_JOB_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return ProcessingJobResponse.model_validate(job)

    async def list_jobs_for_evidence(
        self, case_id: UUID, evidence_id: UUID, current_user: User
    ) -> List[ProcessingJobResponse]:
        """Fetch processing history for an evidence item."""
        await self._verify_case_and_membership(case_id, current_user, require_write=False)

        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence record not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        jobs = await self.job_repo.list_by_evidence(evidence_id)
        return [ProcessingJobResponse.model_validate(j) for j in jobs]

    async def list_artifacts_for_evidence(
        self,
        case_id: UUID,
        evidence_id: UUID,
        current_user: User,
        artifact_type: Optional[ArtifactType] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> RawArtifactListResponse:
        """Fetch paginated raw artifacts with strict source provenance."""
        await self._verify_case_and_membership(case_id, current_user, require_write=False)

        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence record not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        items, total = await self.artifact_repo.list_by_evidence(
            evidence_id=evidence_id,
            artifact_type=artifact_type,
            page=page,
            page_size=page_size,
        )

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return RawArtifactListResponse(
            items=[RawArtifactResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_artifact_by_id(
        self, case_id: UUID, artifact_id: UUID, current_user: User
    ) -> RawArtifactResponse:
        """Fetch an individual raw artifact by ID."""
        await self._verify_case_and_membership(case_id, current_user, require_write=False)

        artifact = await self.artifact_repo.get_by_id(artifact_id)
        if not artifact or artifact.case_id != case_id:
            raise ForensicAppException(
                message="Artifact record not found in this case.",
                code="ARTIFACT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return RawArtifactResponse.model_validate(artifact)

    async def start_normalization_job(
        self,
        case_id: UUID,
        evidence_id: UUID,
        background_tasks: BackgroundTasks,
        current_user: User,
        priority: JobPriority = JobPriority.NORMAL,
        client_ip: Optional[str] = None,
    ) -> ProcessingJobResponse:
        """Trigger asynchronous normalization job for raw artifacts in an evidence container."""
        await self._verify_case_and_membership(case_id, current_user, require_write=True)

        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence record not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if evidence.integrity_status == IntegrityStatus.MISMATCH or evidence.status == EvidenceStatus.QUARANTINED:
            raise ForensicAppException(
                message="Normalization blocked: Evidence archive has an integrity mismatch or is quarantined.",
                code="INTEGRITY_MISMATCH",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce non-admin priority limit
        final_priority = priority
        if current_user.role != UserRole.ADMIN and priority == JobPriority.HIGH:
            final_priority = JobPriority.NORMAL

        # Create normalization processing job
        job = await self.job_repo.create_job(
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=current_user.id,
            job_type=JobType.NORMALIZATION,
            priority=final_priority,
        )

        queue = await get_job_queue()
        await queue.enqueue(job.id, priority=final_priority)

        background_tasks.add_task(self.norm_worker.execute_job, job.id)

        await self.audit_service.record_event(
            action=AuditAction.PROCESSING_JOB_CREATED.value,
            resource_type="processing_job",
            resource_id=str(job.id),
            user_id=current_user.id,
            case_id=case_id,
            status="QUEUED",
            client_ip=client_ip,
            details={"evidence_id": str(evidence_id), "job_type": JobType.NORMALIZATION.value, "priority": final_priority.value},
        )

        return ProcessingJobResponse.model_validate(job)

    async def list_canonical_records_for_evidence(
        self,
        case_id: UUID,
        evidence_id: UUID,
        current_user: User,
        artifact_type: Optional[ArtifactType] = None,
        application: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> CanonicalEvidenceListResponse:
        """Fetch paginated canonical records with multi-dimensional filtering."""
        await self._verify_case_and_membership(case_id, current_user, require_write=False)

        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence record not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        items, total = await self.canonical_repo.list_by_evidence(
            evidence_id=evidence_id,
            artifact_type=artifact_type,
            application=application,
            data_quality_status=data_quality_status,
            page=page,
            page_size=page_size,
        )

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return CanonicalEvidenceListResponse(
            items=[CanonicalEvidenceResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_canonical_record_by_id(
        self, case_id: UUID, record_id: UUID, current_user: User
    ) -> CanonicalEvidenceResponse:
        """Fetch an individual canonical evidence record by ID with case verification."""
        await self._verify_case_and_membership(case_id, current_user, require_write=False)

        record = await self.canonical_repo.get_by_id(record_id)
        if not record or record.case_id != case_id:
            raise ForensicAppException(
                message="Canonical evidence record not found in this case.",
                code="CANONICAL_RECORD_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return CanonicalEvidenceResponse.model_validate(record)

    async def get_canonical_record_raw_artifact(
        self, case_id: UUID, record_id: UUID, current_user: User
    ) -> RawArtifactResponse:
        """Trace a canonical record back to its exact originating RawArtifact."""
        await self._verify_case_and_membership(case_id, current_user, require_write=False)

        record = await self.canonical_repo.get_by_id(record_id)
        if not record or record.case_id != case_id:
            raise ForensicAppException(
                message="Canonical evidence record not found in this case.",
                code="CANONICAL_RECORD_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        raw = await self.artifact_repo.get_by_id(record.raw_artifact_id)
        if not raw or raw.case_id != case_id:
            raise ForensicAppException(
                message="Originating raw artifact not found.",
                code="RAW_ARTIFACT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return RawArtifactResponse.model_validate(raw)

    # ------------------------------------------------------------------ #
    # Phase 8: Cursor-based pagination service methods                     #
    # ------------------------------------------------------------------ #

    async def cursor_canonical_records_by_evidence(
        self,
        case_id: UUID,
        evidence_id: UUID,
        current_user: User,
        cursor: Optional[str] = None,
        page_size: int = 50,
        artifact_type: Optional[ArtifactType] = None,
        application: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
    ) -> CanonicalCursorPageResponse:
        """
        Phase 8: Keyset-paginated canonical records for an evidence package.
        Uses O(log N) indexed scan — no OFFSET, no COUNT(*).
        """
        await self._verify_case_and_membership(case_id, current_user, require_write=False)
        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        try:
            items, next_cursor = await self.canonical_repo.cursor_page_by_evidence(
                evidence_id=evidence_id,
                page_size=page_size,
                cursor=cursor,
                artifact_type=artifact_type,
                application=application,
                data_quality_status=data_quality_status,
            )
        except ValueError as exc:
            raise ForensicAppException(
                message=f"Invalid pagination cursor: {exc}",
                code="INVALID_CURSOR",
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc

        return CanonicalCursorPageResponse(
            items=[CanonicalEvidenceResponse.model_validate(item) for item in items],
            page_size=page_size,
            has_next=next_cursor is not None,
            next_cursor=next_cursor,
        )

    async def cursor_canonical_records_by_case(
        self,
        case_id: UUID,
        current_user: User,
        cursor: Optional[str] = None,
        page_size: int = 50,
        artifact_type: Optional[ArtifactType] = None,
        device_id: Optional[str] = None,
        application: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
    ) -> CanonicalCursorPageResponse:
        """
        Phase 8: Keyset-paginated canonical records spanning the entire case.
        Useful for case-wide forensic timelines without loading full datasets.
        """
        await self._verify_case_and_membership(case_id, current_user, require_write=False)

        try:
            items, next_cursor = await self.canonical_repo.cursor_page_by_case(
                case_id=case_id,
                page_size=page_size,
                cursor=cursor,
                artifact_type=artifact_type,
                device_id=device_id,
                application=application,
                data_quality_status=data_quality_status,
            )
        except ValueError as exc:
            raise ForensicAppException(
                message=f"Invalid pagination cursor: {exc}",
                code="INVALID_CURSOR",
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from exc

        return CanonicalCursorPageResponse(
            items=[CanonicalEvidenceResponse.model_validate(item) for item in items],
            page_size=page_size,
            has_next=next_cursor is not None,
            next_cursor=next_cursor,
        )

    async def get_case_canonical_summary(
        self,
        case_id: UUID,
        current_user: User,
    ) -> CaseCanonicalSummaryResponse:
        """
        Phase 8: Aggregate-only summary of canonical records across a case.
        Returns total count and per-type breakdown via efficient GROUP BY.
        Does not load individual records.
        """
        await self._verify_case_and_membership(case_id, current_user, require_write=False)

        total = await self.canonical_repo.count_for_case(case_id)
        breakdown = await self.canonical_repo.count_by_artifact_type_for_case(case_id)

        return CaseCanonicalSummaryResponse(
            case_id=case_id,
            total_canonical_records=total,
            breakdown_by_type=breakdown,
        )
