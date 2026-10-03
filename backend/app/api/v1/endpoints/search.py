"""
Phase 9 — Forensic Search API Endpoints

All routes are case-scoped: /api/v1/cases/{case_id}/search

Endpoints:
  GET  /{case_id}/search          → Execute forensic search
  GET  /{case_id}/search/history  → Retrieve search history for case/user

Security:
  - Every endpoint requires authentication (get_current_user dependency)
  - Case authorization is enforced in the service layer
  - SQL injection prevention: all inputs go through ORM parameterization
  - Wildcard protection: service rejects bare %% queries
  - Page size cap: MAX_SEARCH_PAGE_SIZE enforced in service
  - Query length cap: MAX_QUERY_LENGTH enforced in service

NOTE: The /search/history literal route is registered BEFORE any wildcard
path parameters on this router to prevent route shadowing.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_client_ip, get_current_user
from backend.app.core.database import get_db
from backend.app.models.enums import ArtifactType, DataQualityStatus, JobPriority, SearchMode, TimestampPrecision
from backend.app.models.user import User
from backend.app.schemas.processing_job import ProcessingJobResponse
from backend.app.schemas.search import (
    ALLOWED_SORT_FIELDS,
    MAX_SEARCH_PAGE_SIZE,
    EmbeddingRebuildResponse,
    EmbeddingStatsResponse,
    ForensicSearchResponse,
    SearchHistoryResponse,
)
from backend.app.services.search_service import ForensicSearchService

router = APIRouter()


# ============================================================= #
# Literal path routes FIRST — before any path-param wildcards   #
# ============================================================= #

@router.get(
    "/{case_id}/search/history",
    response_model=SearchHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Case Search History",
    description=(
        "Returns the authenticated user's forensic search history for this case. "
        "ADMIN users can see all history for the case. "
        "Results are ordered by most recent search first."
    ),
)
async def get_search_history(
    case_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="Number of history entries to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SearchHistoryResponse:
    service = ForensicSearchService(session)
    return await service.get_search_history(
        case_id=case_id,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{case_id}/embeddings/stats",
    response_model=EmbeddingStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Case Embedding Statistics",
    description="Returns vector embedding status, coverage percentage, and counts for a case.",
)
async def get_embedding_stats(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EmbeddingStatsResponse:
    service = ForensicSearchService(session)
    return await service.get_embedding_stats(case_id=case_id, current_user=current_user)


@router.post(
    "/{case_id}/embeddings/generate",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate Embeddings",
    description="Enqueue an asynchronous job to generate vector embeddings for canonical evidence.",
)
async def generate_embeddings(
    case_id: UUID,
    evidence_id: Optional[UUID] = Query(None, description="Optional evidence package filter"),
    priority: JobPriority = Query(JobPriority.NORMAL, description="Queue scheduling priority"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProcessingJobResponse:
    service = ForensicSearchService(session)
    job = await service.trigger_embedding_generation(
        case_id=case_id,
        current_user=current_user,
        evidence_id=evidence_id,
        priority=priority,
    )
    return ProcessingJobResponse.model_validate(job)


@router.post(
    "/{case_id}/embeddings/rebuild",
    response_model=EmbeddingRebuildResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Rebuild Case Vector Index",
    description="Marks existing embeddings as stale and triggers a full vector index rebuild job.",
)
async def rebuild_embeddings(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EmbeddingRebuildResponse:
    service = ForensicSearchService(session)
    job = await service.rebuild_embeddings(case_id=case_id, current_user=current_user)
    return EmbeddingRebuildResponse(
        case_id=case_id,
        job_id=job.id,
        status="ACCEPTED",
        message="Vector index rebuild job enqueued successfully.",
    )


# ============================================================= #
# Main search endpoint                                           #
# ============================================================= #

@router.get(
    "/{case_id}/search",
    response_model=ForensicSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Forensic Evidence Search",
    description=(
        "Case-scoped forensic evidence search. "
        "Supports EXACT, LEXICAL, SEMANTIC (Sentence-BERT), and HYBRID retrieval modes. "
        "Searches normalized canonical evidence records with metadata filters. "
        "Supports cursor-based pagination for large result sets. "
        "Every result includes full source traceability back to the originating "
        "evidence package."
    ),
)
async def search_evidence(
    case_id: UUID,
    request: Request,
    # General text query
    q: Optional[str] = Query(
        None,
        max_length=500,
        description="Search term. Partial match against: content, application, source_file, record_identifier, device_id.",
    ),
    mode: SearchMode = Query(
        SearchMode.LEXICAL,
        description="Retrieval mode: EXACT, LEXICAL, SEMANTIC, or HYBRID (default: LEXICAL).",
    ),
    # Structured filters
    artifact_type: Optional[ArtifactType] = Query(
        None,
        description="Filter by artifact type (CALL, MESSAGE, CONTACT, LOCATION, BROWSER, APPLICATION, FILESYSTEM, etc.)",
    ),
    evidence_id: Optional[UUID] = Query(
        None,
        description="Restrict results to a specific evidence package (must belong to this case).",
    ),
    device_id: Optional[str] = Query(
        None,
        max_length=100,
        description="Exact device identifier filter.",
    ),
    application: Optional[str] = Query(
        None,
        max_length=100,
        description="Application name filter (case-insensitive partial match).",
    ),
    entity_type: Optional[str] = Query(
        None,
        max_length=50,
        description="Entity type filter (PHONE_NUMBER, EMAIL, ACCOUNT, DEVICE, etc.)",
    ),
    entity_value: Optional[str] = Query(
        None,
        max_length=500,
        description="Entity value to search for within the entities array.",
    ),
    start_time: Optional[datetime] = Query(
        None,
        description="Filter records with event_timestamp >= start_time (ISO-8601, UTC).",
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="Filter records with event_timestamp <= end_time (ISO-8601, UTC).",
    ),
    timestamp_precision: Optional[TimestampPrecision] = Query(
        None,
        description="Filter by timestamp precision (YEAR, MONTH, DAY, HOUR, MINUTE, SECOND, MILLISECOND, UNKNOWN).",
    ),
    source_file: Optional[str] = Query(
        None,
        max_length=255,
        description="Exact source file name filter (e.g. messages.xml).",
    ),
    data_quality_status: Optional[DataQualityStatus] = Query(
        None,
        description="Filter by data quality status (VALID, PARTIAL, INVALID, UNKNOWN).",
    ),
    # Sorting
    sort: str = Query(
        "timestamp_desc",
        description=f"Sort order. Allowed: {sorted(ALLOWED_SORT_FIELDS)}",
    ),
    # Pagination
    page_size: int = Query(
        50,
        ge=1,
        le=MAX_SEARCH_PAGE_SIZE,
        description=f"Results per page. Maximum: {MAX_SEARCH_PAGE_SIZE}.",
    ),
    cursor: Optional[str] = Query(
        None,
        description="Opaque cursor token from the previous search response for pagination.",
    ),
    # Optional facets
    include_facets: bool = Query(
        False,
        description="If true, include aggregate counts by artifact type. Runs an additional DB query.",
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ForensicSearchResponse:
    client_ip = get_client_ip(request)
    service = ForensicSearchService(session)
    return await service.search(
        case_id=case_id,
        current_user=current_user,
        q=q,
        mode=mode,
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
        sort=sort,
        page_size=page_size,
        cursor=cursor,
        include_facets=include_facets,
        client_ip=client_ip,
    )
