"""
Phase 9 — Forensic Search Service

ForensicSearchService orchestrates:
  1. Case authorization (every search is case-scoped)
  2. Evidence ID authorization (verify evidence belongs to this case)
  3. Input validation (query length, page size, date range ordering)
  4. Wildcard protection (reject bare %% queries)
  5. Delegation to ForensicSearchRepository (query builder lives there)
  6. Result mapping to SearchResultItem (content preview, traceability)
  7. Search history persistence (only for completed operations)
  8. Audit logging via AuditService

Design constraints from Phase 9 spec:
  - Never modify stored evidence content
  - Every result exposes: canonical_id, raw_artifact_id, evidence_id, source_file,
    record_identifier, timestamp  (full traceability chain)
  - content_preview is truncated server-side (PREVIEW_MAX_CHARS) — original not modified
  - Match type classification: EXACT_MATCH vs TEXT_MATCH vs FILTER_MATCH
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import ForensicAppException
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import (
    ArtifactType,
    AuditAction,
    DataQualityStatus,
    JobPriority,
    JobStatus,
    JobType,
    SearchMode,
    TimestampPrecision,
)
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.user import User
from backend.app.queue.factory import get_job_queue
from backend.app.repositories.canonical_evidence_repo import CanonicalEvidenceRepository
from backend.app.repositories.case_repo import CaseRepository
from backend.app.repositories.embedding_repo import EmbeddingRepository
from backend.app.repositories.evidence_repo import EvidenceRepository
from backend.app.repositories.processing_job_repo import ProcessingJobRepository
from backend.app.repositories.search_repo import ForensicSearchRepository
from backend.app.schemas.search import (
    ALLOWED_SORT_FIELDS,
    MAX_QUERY_LENGTH,
    MAX_SEARCH_PAGE_SIZE,
    EmbeddingStatsResponse,
    ForensicSearchResponse,
    SearchFacets,
    SearchHistoryItem,
    SearchHistoryResponse,
    SearchPagination,
    SearchResultItem,
    SearchResultSource,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.embedding_service import get_embedding_service
from backend.app.services.retrieval_ranker import RetrievalRanker
from backend.app.vector_store import get_vector_store

# Number of characters to expose in content_preview — stored original is never modified
PREVIEW_MAX_CHARS = 300


class ForensicSearchService:
    """
    Phase 9 & 10: Case-scoped forensic evidence search & semantic retrieval service.

    Supports:
      - EXACT search (identifiers, phone numbers, exact match)
      - LEXICAL search (partial text, keywords, metadata filters)
      - SEMANTIC search (Sentence-BERT dense vector retrieval)
      - HYBRID search (Ranked fusion of lexical + dense semantic candidates)

    All public methods require an authorized User and a specific case_id.
    Search never operates across cases.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.search_repo = ForensicSearchRepository(session)
        self.case_repo = CaseRepository(session)
        self.evidence_repo = EvidenceRepository(session)
        self.canonical_repo = CanonicalEvidenceRepository(session)
        self.embedding_repo = EmbeddingRepository(session)
        self.job_repo = ProcessingJobRepository(session)
        self.audit_service = AuditService(session)
        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store()
        self.ranker = RetrievalRanker()

    # ---------------------------------------------------------------------- #
    # Authorization helpers                                                    #
    # ---------------------------------------------------------------------- #

    async def _verify_case_access(self, case_id: UUID, user: User) -> None:
        """Verify case exists and user is a member. Raises 403/404 on failure."""
        case = await self.case_repo.get_by_id(case_id)
        if not case:
            raise ForensicAppException(
                message="Case not found.",
                code="CASE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        member = await self.case_repo.get_membership(case_id, user.id)
        if not member and user.role.value not in ("ADMIN",):
            raise ForensicAppException(
                message="Access denied to this case.",
                code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    async def _verify_evidence_in_case(
        self, case_id: UUID, evidence_id: UUID
    ) -> None:
        """Verify evidence exists AND belongs to the given case."""
        evidence = await self.evidence_repo.get_by_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise ForensicAppException(
                message="Evidence not found in this case.",
                code="EVIDENCE_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    # ---------------------------------------------------------------------- #
    # Input validation                                                         #
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _validate_inputs(
        q: Optional[str],
        page_size: int,
        sort: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> None:
        """Validate and reject dangerous or malformed search inputs."""

        # Query length cap
        if q is not None and len(q) > MAX_QUERY_LENGTH:
            raise ForensicAppException(
                message=f"Search query exceeds maximum length of {MAX_QUERY_LENGTH} characters.",
                code="QUERY_TOO_LONG",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Wildcard-only protection: reject queries that are only % or _ characters
        if q is not None and q.strip():
            stripped = q.strip().replace("%", "").replace("_", "").replace(" ", "")
            if len(stripped) == 0:
                raise ForensicAppException(
                    message="Search query must contain at least one non-wildcard character.",
                    code="WILDCARD_ONLY_QUERY",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        # Page size cap
        if page_size > MAX_SEARCH_PAGE_SIZE:
            raise ForensicAppException(
                message=f"page_size cannot exceed {MAX_SEARCH_PAGE_SIZE}.",
                code="PAGE_SIZE_EXCEEDED",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if page_size < 1:
            raise ForensicAppException(
                message="page_size must be at least 1.",
                code="INVALID_PAGE_SIZE",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Sort field validation
        if sort not in ALLOWED_SORT_FIELDS:
            raise ForensicAppException(
                message=f"Invalid sort value. Allowed: {sorted(ALLOWED_SORT_FIELDS)}",
                code="INVALID_SORT_FIELD",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Date range ordering
        if start_time is not None and end_time is not None:
            if start_time > end_time:
                raise ForensicAppException(
                    message="start_time must not be after end_time.",
                    code="INVALID_DATE_RANGE",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

    # ---------------------------------------------------------------------- #
    # Result mapping                                                           #
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _classify_match(
        record: CanonicalEvidence,
        q: Optional[str],
        entity_value: Optional[str],
    ) -> str:
        """
        Classify the match type for display purposes only.
        EXACT_MATCH: query matches record_identifier, device_id, or source_file exactly.
        TEXT_MATCH: query found in content or application via LIKE.
        FILTER_MATCH: result returned by filter predicates only.
        """
        if q is None or not q.strip():
            return "FILTER_MATCH"

        q_lower = q.strip().lower()

        # Exact match against structured identifier fields
        if (
            (record.record_identifier and record.record_identifier.lower() == q_lower)
            or (record.device_id and record.device_id.lower() == q_lower)
            or (record.source_file and record.source_file.lower() == q_lower)
        ):
            return "EXACT_MATCH"

        return "TEXT_MATCH"

    @staticmethod
    def _make_content_preview(content: Optional[str]) -> Optional[str]:
        """
        Return at most PREVIEW_MAX_CHARS of the content field.
        The stored original is NEVER modified — this is a view-only truncation.
        """
        if not content:
            return None
        if len(content) <= PREVIEW_MAX_CHARS:
            return content
        return content[:PREVIEW_MAX_CHARS] + "…"

    @staticmethod
    def _extract_matched_entities(
        record: CanonicalEvidence,
        entity_type: Optional[str],
        entity_value: Optional[str],
    ) -> List[Dict]:
        """
        When an entity search was performed, return the matching entity dicts.
        Otherwise return empty list. Never modifies the stored entity list.
        """
        if not entity_type and not entity_value:
            return []

        matched = []
        for ent in (record.entities or []):
            type_match = (
                not entity_type
                or str(ent.get("type", "")).lower() == entity_type.lower()
            )
            value_match = (
                not entity_value
                or entity_value.lower() in str(ent.get("value", "")).lower()
            )
            if type_match and value_match:
                matched.append(ent)
        return matched

    def _map_to_result_item(
        self,
        record: CanonicalEvidence,
        q: Optional[str],
        entity_type: Optional[str],
        entity_value: Optional[str],
    ) -> SearchResultItem:
        """Map a CanonicalEvidence ORM object to a SearchResultItem response."""
        return SearchResultItem(
            id=record.id,
            artifact_type=record.artifact_type,
            event_timestamp=record.event_timestamp,
            timestamp_precision=record.timestamp_precision,
            application=record.application,
            device_id=record.device_id,
            content_preview=self._make_content_preview(record.content),
            matched_entities=self._extract_matched_entities(record, entity_type, entity_value),
            data_quality_status=record.data_quality_status,
            match_type=self._classify_match(record, q, entity_value),
            source=SearchResultSource(
                evidence_id=record.evidence_id,
                raw_artifact_id=record.raw_artifact_id,
                source_file=record.source_file,
                source_path=record.source_path,
                record_identifier=record.record_identifier,
            ),
        )

    # ---------------------------------------------------------------------- #
    # Semantic & Hybrid helpers                                                #
    # ---------------------------------------------------------------------- #

    async def _execute_semantic_search(
        self,
        case_id: UUID,
        q: Optional[str],
        *,
        artifact_type: Optional[ArtifactType] = None,
        evidence_id: Optional[UUID] = None,
        device_id: Optional[str] = None,
        application: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        source_file: Optional[str] = None,
        data_quality_status: Optional[DataQualityStatus] = None,
        top_k: int = 50,
    ) -> List[SearchResultItem]:
        """
        Executes dense vector similarity search within the case boundary.
        Resolves candidate vectors back to CanonicalEvidence records.
        """
        if not q or not q.strip():
            return []

        clean_q = q.strip()
        try:
            # 1. Generate query embedding
            query_vector = self.embedding_service.embed_query(clean_q)

            # 2. Search case-scoped vector index
            vector_matches = self.vector_store.search(
                case_id=case_id,
                query_vector=query_vector,
                top_k=top_k,
            )
            if not vector_matches:
                return []

            score_map = {record_id: score for record_id, score in vector_matches}
            candidate_ids = [record_id for record_id, _ in vector_matches]

            # 3. Retrieve canonical records and apply SQL metadata filters
            records = await self.search_repo.fetch_canonical_by_ids(
                case_id=case_id,
                record_ids=candidate_ids,
                artifact_type=artifact_type,
                evidence_id=evidence_id,
                device_id=device_id,
                application=application,
                start_time=start_time,
                end_time=end_time,
                source_file=source_file,
                data_quality_status=data_quality_status,
            )

            # 4. Map to SearchResultItem and maintain vector score ordering
            record_dict = {rec.id: rec for rec in records}
            results: List[SearchResultItem] = []

            for rec_id, score in vector_matches:
                if rec_id in record_dict:
                    rec = record_dict[rec_id]
                    item = self._map_to_result_item(rec, q, None, None)
                    item.match_type = "SEMANTIC_MATCH"
                    item.similarity_score = round(score, 4)
                    item.retrieval_explanation = f"Matched via Semantic vector similarity ({score:.2f})"
                    results.append(item)

            return results

        except Exception as e:
            logger.error(f"[ForensicSearchService] Semantic search error: {e}")
            raise ForensicAppException(
                message=f"Semantic retrieval unavailable: {e}",
                code="SEMANTIC_SEARCH_UNAVAILABLE",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    # ---------------------------------------------------------------------- #
    # Main search entrypoint                                                   #
    # ---------------------------------------------------------------------- #

    async def search(
        self,
        case_id: UUID,
        current_user: User,
        *,
        q: Optional[str] = None,
        mode: SearchMode = SearchMode.LEXICAL,
        artifact_type: Optional[ArtifactType] = None,
        evidence_id: Optional[UUID] = None,
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
        include_facets: bool = False,
        client_ip: Optional[str] = None,
    ) -> ForensicSearchResponse:
        """
        Execute a forensic evidence search scoped to a single authorized case.
        Supports EXACT, LEXICAL, SEMANTIC, and HYBRID retrieval modes.
        """
        t_start = time.monotonic()

        # Step 1: Case authorization
        await self._verify_case_access(case_id, current_user)

        # Step 2: Input validation
        self._validate_inputs(q, page_size, sort, start_time, end_time)

        # Step 3: Evidence ID cross-case authorization
        if evidence_id is not None:
            await self._verify_evidence_in_case(case_id, evidence_id)

        # Normalize mode string or enum
        if isinstance(mode, str):
            try:
                mode = SearchMode(mode.upper())
            except Exception:
                mode = SearchMode.LEXICAL

        result_items: List[SearchResultItem] = []
        next_cursor: Optional[str] = None

        # Step 4: Mode dispatch
        if mode == SearchMode.SEMANTIC:
            # Dense vector retrieval only
            result_items = await self._execute_semantic_search(
                case_id=case_id,
                q=q,
                artifact_type=artifact_type,
                evidence_id=evidence_id,
                device_id=device_id,
                application=application,
                start_time=start_time,
                end_time=end_time,
                source_file=source_file,
                data_quality_status=data_quality_status,
                top_k=page_size,
            )

        elif mode == SearchMode.HYBRID:
            # 1. Fetch lexical candidates
            lex_records, _ = await self.search_repo.search(
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
                sort=sort,
                page_size=page_size * 2,
            )
            lexical_items = [
                self._map_to_result_item(rec, q, entity_type, entity_value)
                for rec in lex_records
            ]

            # 2. Fetch semantic candidates (if query text present)
            semantic_items: List[SearchResultItem] = []
            if q and q.strip():
                try:
                    semantic_items = await self._execute_semantic_search(
                        case_id=case_id,
                        q=q,
                        artifact_type=artifact_type,
                        evidence_id=evidence_id,
                        device_id=device_id,
                        application=application,
                        start_time=start_time,
                        end_time=end_time,
                        source_file=source_file,
                        data_quality_status=data_quality_status,
                        top_k=page_size * 2,
                    )
                except Exception as e:
                    logger.warning(f"[SearchService] Semantic leg failed in hybrid mode, falling back to lexical: {e}")

            # 3. Hybrid fusion and ranking
            result_items = self.ranker.rank_hybrid(
                lexical_items=lexical_items,
                semantic_items=semantic_items,
                query=q or "",
                top_k=page_size,
            )

        else:
            # EXACT or LEXICAL search (Phase 9 database engine)
            if cursor:
                try:
                    self.search_repo._decode_cursor(cursor)
                except ValueError as exc:
                    raise ForensicAppException(
                        message=str(exc),
                        code="INVALID_SEARCH_CURSOR",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    ) from exc

            items, next_cursor = await self.search_repo.search(
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
                sort=sort,
                page_size=page_size,
                cursor=cursor,
            )
            result_items = [
                self._map_to_result_item(record, q, entity_type, entity_value)
                for record in items
            ]

        # Step 5: Facets (optional — separate DB query)
        facets: Optional[SearchFacets] = None
        if include_facets:
            facets = await self.search_repo.get_facets(
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

        duration_ms = int((time.monotonic() - t_start) * 1000)

        # Step 6: Persist search history (non-blocking)
        filters_dict: Dict[str, Any] = {
            k: str(v) for k, v in {
                "mode": mode.value if hasattr(mode, "value") else str(mode),
                "artifact_type": artifact_type,
                "evidence_id": evidence_id,
                "device_id": device_id,
                "application": application,
                "entity_type": entity_type,
                "entity_value": entity_value,
                "start_time": start_time,
                "end_time": end_time,
                "timestamp_precision": timestamp_precision,
                "source_file": source_file,
                "data_quality_status": data_quality_status,
                "sort": sort,
            }.items() if v is not None
        }
        try:
            await self.search_repo.save_search_history(
                case_id=case_id,
                user_id=current_user.id,
                query=q,
                filters=filters_dict,
                result_count=len(result_items),
                duration_ms=duration_ms,
            )
        except Exception:
            pass

        # Step 7: Audit log
        try:
            audit_action = (
                AuditAction.SEMANTIC_SEARCH_EXECUTED.value
                if mode in (SearchMode.SEMANTIC, SearchMode.HYBRID)
                else AuditAction.FORENSIC_SEARCH_EXECUTED.value
            )
            await self.audit_service.record_event(
                action=audit_action,
                resource_type="canonical_evidence",
                status="SUCCESS",
                user_id=current_user.id,
                case_id=case_id,
                details={
                    "query": q,
                    "mode": mode.value if hasattr(mode, "value") else str(mode),
                    "filters": filters_dict,
                    "result_count": len(result_items),
                    "duration_ms": duration_ms,
                },
                client_ip=client_ip,
            )
        except Exception:
            pass

        return ForensicSearchResponse(
            results=result_items,
            facets=facets,
            pagination=SearchPagination(
                next_cursor=next_cursor,
                has_more=next_cursor is not None,
                page_size=page_size,
            ),
            search_mode=mode,
            duration_ms=duration_ms,
        )

    # ---------------------------------------------------------------------- #
    # Embedding Management Operations                                         #
    # ---------------------------------------------------------------------- #

    async def get_embedding_stats(
        self,
        case_id: UUID,
        current_user: User,
    ) -> EmbeddingStatsResponse:
        """Retrieve embedding generation statistics and coverage for a case."""
        await self._verify_case_access(case_id, current_user)
        stats = await self.embedding_repo.get_case_embedding_stats(case_id)
        return EmbeddingStatsResponse(**stats)

    async def trigger_embedding_generation(
        self,
        case_id: UUID,
        current_user: User,
        evidence_id: Optional[UUID] = None,
        priority: JobPriority = JobPriority.NORMAL,
    ) -> ProcessingJob:
        """Enqueue an asynchronous EMBEDDING job for canonical evidence in a case."""
        await self._verify_case_access(case_id, current_user)
        if evidence_id:
            await self._verify_evidence_in_case(case_id, evidence_id)

        # Enforce non-admin priority cap
        if priority == JobPriority.HIGH and current_user.role.value not in ("ADMIN",):
            priority = JobPriority.NORMAL

        job = await self.job_repo.create_job(
            case_id=case_id,
            evidence_id=evidence_id,
            job_type=JobType.EMBEDDING,
            priority=priority,
            created_by=current_user.id,
        )

        queue = get_job_queue()
        await queue.enqueue(job_id=job.id, priority=priority)

        await self.audit_service.record_event(
            action=AuditAction.EMBEDDING_JOB_CREATED.value,
            resource_type="processing_job",
            resource_id=str(job.id),
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            details={"priority": priority.value, "evidence_id": str(evidence_id) if evidence_id else None},
        )
        await self.session.commit()
        return job

    async def rebuild_embeddings(
        self,
        case_id: UUID,
        current_user: User,
    ) -> ProcessingJob:
        """Mark existing embeddings as STALE and enqueue an EMBEDDING job to rebuild vectors."""
        await self._verify_case_access(case_id, current_user)

        # Only LEAD, CONTRIBUTOR or ADMIN can rebuild embeddings
        member = await self.case_repo.get_membership(case_id, current_user.id)
        if member and member.access_role.value in ("VIEWER", "ANALYST") and current_user.role.value not in ("ADMIN",):
            raise ForensicAppException(
                message="Insufficient privileges to trigger vector index rebuild.",
                code="PERMISSION_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        # Mark existing embeddings as STALE
        await self.embedding_repo.mark_all_case_embeddings_stale(case_id)

        job = await self.job_repo.create_job(
            case_id=case_id,
            evidence_id=None,
            job_type=JobType.EMBEDDING,
            priority=JobPriority.HIGH if current_user.role.value in ("ADMIN",) else JobPriority.NORMAL,
            created_by=current_user.id,
        )

        queue = get_job_queue()
        await queue.enqueue(job_id=job.id, priority=job.priority)

        await self.audit_service.record_event(
            action=AuditAction.VECTOR_INDEX_REBUILT.value,
            resource_type="processing_job",
            resource_id=str(job.id),
            user_id=current_user.id,
            case_id=case_id,
            status="SUCCESS",
            details={"job_id": str(job.id)},
        )
        await self.session.commit()
        return job

    # ---------------------------------------------------------------------- #
    # Search history retrieval                                                 #
    # ---------------------------------------------------------------------- #

    async def get_search_history(
        self,
        case_id: UUID,
        current_user: User,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchHistoryResponse:
        """Return case-scoped search history for the authenticated user."""
        await self._verify_case_access(case_id, current_user)

        # Users see their own history; ADMINs can see all case history
        user_id_filter: Optional[UUID] = None
        if current_user.role.value not in ("ADMIN",):
            user_id_filter = current_user.id

        items, total = await self.search_repo.list_search_history(
            case_id=case_id,
            user_id=user_id_filter,
            limit=min(limit, 100),
            offset=offset,
        )

        return SearchHistoryResponse(
            items=[
                SearchHistoryItem(
                    id=h.id,
                    query=h.query,
                    filters_json=h.filters_json,
                    result_count=h.result_count,
                    executed_at=h.executed_at,
                    duration_ms=h.duration_ms,
                )
                for h in items
            ],
            total=total,
        )
