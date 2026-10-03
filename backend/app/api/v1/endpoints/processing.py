from typing import Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_client_ip, get_current_user
from backend.app.core.database import get_db
from backend.app.models.enums import ArtifactType, DataQualityStatus, JobPriority
from backend.app.models.user import User
from backend.app.schemas.canonical_evidence import (
    CanonicalCursorPageResponse,
    CanonicalEvidenceListResponse,
    CanonicalEvidenceResponse,
    CaseCanonicalSummaryResponse,
)
from backend.app.schemas.processing_job import ProcessingJobCreateRequest, ProcessingJobResponse
from backend.app.schemas.raw_artifact import RawArtifactListResponse, RawArtifactResponse
from backend.app.services.processing_service import ProcessingService

router = APIRouter()


@router.post(
    "/{case_id}/evidence/{evidence_id}/parse",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Asynchronous UFDR Parsing",
    description=(
        "Enqueues a background forensic ingestion and parsing job for an uploaded UFDR evidence archive. "
        "Verifies cryptographic baseline integrity, performs bounded archive inspection, executes "
        "streaming XML artifact extraction, and stores raw forensic artifact records with source provenance."
    ),
)
async def trigger_evidence_parsing(
    case_id: UUID,
    evidence_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    payload: Optional[ProcessingJobCreateRequest] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProcessingJobResponse:
    client_ip = get_client_ip(request)
    priority = payload.priority if payload else JobPriority.NORMAL
    service = ProcessingService(session)
    return await service.start_parsing_job(
        case_id=case_id,
        evidence_id=evidence_id,
        current_user=current_user,
        background_tasks=background_tasks,
        priority=priority,
        client_ip=client_ip,
    )


@router.post(
    "/{case_id}/processing-jobs/{job_id}/cancel",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Processing Job",
    description="Cooperatively requests cancellation of an in-flight processing job.",
)
async def cancel_processing_job(
    case_id: UUID,
    job_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProcessingJobResponse:
    client_ip = get_client_ip(request)
    service = ProcessingService(session)
    return await service.cancel_job(
        case_id=case_id,
        job_id=job_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post(
    "/{case_id}/processing-jobs/{job_id}/retry",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry Processing Job",
    description="Retries a failed or cancelled processing job, resuming from safe checkpoints if available.",
)
async def retry_processing_job(
    case_id: UUID,
    job_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProcessingJobResponse:
    client_ip = get_client_ip(request)
    service = ProcessingService(session)
    return await service.retry_job(
        case_id=case_id,
        job_id=job_id,
        current_user=current_user,
        background_tasks=background_tasks,
        client_ip=client_ip,
    )


@router.get(
    "/{case_id}/processing-jobs/{job_id}",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Processing Job Status",
    description="Returns current execution status, measurable percentage progress, and diagnostic summary metrics.",
)
async def get_processing_job_status(
    case_id: UUID,
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProcessingJobResponse:
    service = ProcessingService(session)
    return await service.get_job_status(
        case_id=case_id,
        job_id=job_id,
        current_user=current_user,
    )


@router.get(
    "/{case_id}/evidence/{evidence_id}/processing-jobs",
    response_model=List[ProcessingJobResponse],
    status_code=status.HTTP_200_OK,
    summary="List Evidence Processing History",
    description="Lists all historical and active processing jobs executed against a forensic evidence package.",
)
async def list_evidence_processing_jobs(
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> List[ProcessingJobResponse]:
    service = ProcessingService(session)
    return await service.list_jobs_for_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        current_user=current_user,
    )


@router.get(
    "/{case_id}/evidence/{evidence_id}/artifacts",
    response_model=RawArtifactListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Extracted Raw Artifacts",
    description=(
        "Retrieves paginated raw forensic artifact records extracted from the evidence package. "
        "Supports filtering by artifact category (CALL, MESSAGE, CONTACT, LOCATION, BROWSER, APPLICATION, FILESYSTEM) "
        "and retains full source traceability."
    ),
)
async def list_raw_artifacts(
    case_id: UUID,
    evidence_id: UUID,
    artifact_type: Optional[ArtifactType] = Query(None, description="Filter by artifact category"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RawArtifactListResponse:
    service = ProcessingService(session)
    return await service.list_artifacts_for_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        current_user=current_user,
        artifact_type=artifact_type,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{case_id}/artifacts/{artifact_id}",
    response_model=RawArtifactResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Raw Artifact Details",
    description="Fetches an individual parsed artifact record including complete raw payload and source provenance.",
)
async def get_raw_artifact(
    case_id: UUID,
    artifact_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RawArtifactResponse:
    service = ProcessingService(session)
    return await service.get_artifact_by_id(
        case_id=case_id,
        artifact_id=artifact_id,
        current_user=current_user,
    )


@router.post(
    "/{case_id}/evidence/{evidence_id}/normalize",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Asynchronous Evidence Normalization",
    description=(
        "Enqueues an asynchronous normalization job to convert heterogeneous RawArtifacts "
        "into the unified CanonicalEvidence model with standardized timestamps, entity references, "
        "and stable deterministic identifiers."
    ),
)
async def trigger_evidence_normalization(
    case_id: UUID,
    evidence_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    payload: Optional[ProcessingJobCreateRequest] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProcessingJobResponse:
    client_ip = get_client_ip(request)
    priority = payload.priority if payload else JobPriority.NORMAL
    service = ProcessingService(session)
    return await service.start_normalization_job(
        case_id=case_id,
        evidence_id=evidence_id,
        background_tasks=background_tasks,
        current_user=current_user,
        priority=priority,
        client_ip=client_ip,
    )


@router.get(
    "/{case_id}/evidence/{evidence_id}/canonical-records",
    response_model=CanonicalEvidenceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Normalized Canonical Records",
    description="Retrieves paginated canonical evidence records with multi-dimensional filtering.",
)
async def list_canonical_records(
    case_id: UUID,
    evidence_id: UUID,
    artifact_type: Optional[ArtifactType] = Query(None, description="Filter by canonical artifact category"),
    application: Optional[str] = Query(None, description="Filter by application"),
    data_quality_status: Optional[DataQualityStatus] = Query(None, description="Filter by data quality status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CanonicalEvidenceListResponse:
    service = ProcessingService(session)
    return await service.list_canonical_records_for_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        current_user=current_user,
        artifact_type=artifact_type,
        application=application,
        data_quality_status=data_quality_status,
        page=page,
        page_size=page_size,
    )


# ============================================================= #
# Phase 8 — Cursor-based pagination (BEFORE wildcard routes)    #
#                                                               #
# IMPORTANT: FastAPI matches routes in registration order.      #
# Literal paths (/stream, /summary, /storage/health) MUST be   #
# registered BEFORE wildcard patterns (/{record_id}) to prevent #
# FastAPI from treating "stream" / "summary" as UUID values.   #
# ============================================================= #

@router.get(
    "/storage/health",
    response_model=Dict[str, object],
    status_code=status.HTTP_200_OK,
    summary="Database Storage Health Check",
    description=(
        "Phase 8 storage health probe. Confirms DB connectivity and returns "
        "lightweight aggregate row counts. Does not perform sequential scans."
    ),
)
async def storage_health_check(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, object]:
    from backend.app.repositories.canonical_evidence_repo import CanonicalEvidenceRepository
    repo = CanonicalEvidenceRepository(session)
    return await repo.health_check()


@router.get(
    "/{case_id}/evidence/{evidence_id}/canonical-records/stream",
    response_model=CanonicalCursorPageResponse,
    status_code=status.HTTP_200_OK,
    summary="Cursor-Paginated Canonical Records (Evidence-Scoped)",
    description=(
        "Returns a page of canonical records using keyset (cursor) pagination. "
        "Unlike offset pagination, cursor pages run in O(log N) time at any depth. "
        "Pass the returned ``next_cursor`` as the ``cursor`` query parameter to "
        "fetch the next page. When ``next_cursor`` is null, the result set is exhausted."
    ),
)
async def cursor_canonical_records_by_evidence(
    case_id: UUID,
    evidence_id: UUID,
    cursor: Optional[str] = Query(None, description="Opaque keyset pagination cursor from the previous response"),
    page_size: int = Query(50, ge=1, le=500, description="Records per page"),
    artifact_type: Optional[ArtifactType] = Query(None, description="Filter by artifact type"),
    application: Optional[str] = Query(None, description="Filter by application"),
    data_quality_status: Optional[DataQualityStatus] = Query(None, description="Filter by data quality"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CanonicalCursorPageResponse:
    service = ProcessingService(session)
    return await service.cursor_canonical_records_by_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        current_user=current_user,
        cursor=cursor,
        page_size=page_size,
        artifact_type=artifact_type,
        application=application,
        data_quality_status=data_quality_status,
    )


@router.get(
    "/{case_id}/canonical-records/stream",
    response_model=CanonicalCursorPageResponse,
    status_code=status.HTTP_200_OK,
    summary="Cursor-Paginated Canonical Records (Case-Scoped)",
    description=(
        "Returns a cursor-paginated page of canonical records spanning ALL evidence "
        "items in a case. Useful for building case-wide timelines and cross-evidence "
        "analysis without loading the entire dataset into memory."
    ),
)
async def cursor_canonical_records_by_case(
    case_id: UUID,
    cursor: Optional[str] = Query(None, description="Opaque keyset cursor from the previous response"),
    page_size: int = Query(50, ge=1, le=500, description="Records per page"),
    artifact_type: Optional[ArtifactType] = Query(None, description="Filter by artifact type"),
    device_id: Optional[str] = Query(None, description="Filter by device identifier"),
    application: Optional[str] = Query(None, description="Filter by application"),
    data_quality_status: Optional[DataQualityStatus] = Query(None, description="Filter by data quality"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CanonicalCursorPageResponse:
    service = ProcessingService(session)
    return await service.cursor_canonical_records_by_case(
        case_id=case_id,
        current_user=current_user,
        cursor=cursor,
        page_size=page_size,
        artifact_type=artifact_type,
        device_id=device_id,
        application=application,
        data_quality_status=data_quality_status,
    )


@router.get(
    "/{case_id}/canonical-records/summary",
    response_model=CaseCanonicalSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Case Canonical Evidence Summary",
    description=(
        "Returns aggregate statistics (total count, per-type breakdown) for all canonical "
        "evidence records across an entire case. Runs efficient GROUP BY aggregate queries — "
        "does not load individual records."
    ),
)
async def get_case_canonical_summary(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CaseCanonicalSummaryResponse:
    service = ProcessingService(session)
    return await service.get_case_canonical_summary(
        case_id=case_id,
        current_user=current_user,
    )


# ============================================================= #
# Wildcard routes — MUST come AFTER literal-path routes above   #
# ============================================================= #

@router.get(
    "/{case_id}/canonical-records/{record_id}",
    response_model=CanonicalEvidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Canonical Record Detail",
    description="Retrieves a single canonical evidence record by ID, including normalized entities and metadata.",
)
async def get_canonical_record(
    case_id: UUID,
    record_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CanonicalEvidenceResponse:
    service = ProcessingService(session)
    return await service.get_canonical_record_by_id(
        case_id=case_id,
        record_id=record_id,
        current_user=current_user,
    )


@router.get(
    "/{case_id}/canonical-records/{record_id}/raw",
    response_model=RawArtifactResponse,
    status_code=status.HTTP_200_OK,
    summary="Trace Canonical Record to Raw Artifact",
    description="Traces a canonical record directly back to its exact originating RawArtifact and raw XML payload.",
)
async def get_canonical_record_originating_raw_artifact(
    case_id: UUID,
    record_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RawArtifactResponse:
    service = ProcessingService(session)
    return await service.get_canonical_record_raw_artifact(
        case_id=case_id,
        record_id=record_id,
        current_user=current_user,
    )
