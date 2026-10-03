"""
Phase 11 — Forensic Investigation Service

Orchestrates natural-language investigation query processing:
Case Authorization → NLP Query Parsing → Retrieval Plan Execution (via Phase 9/10 Search Service) → Audit Logging.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.errors import ForensicAppException
from backend.app.models.enums import (
    ArtifactType,
    AuditAction,
    EntityType,
    SearchMode,
    TimestampPrecision,
)
from backend.app.models.user import User
from backend.app.nlp import get_nlp_pipeline
from backend.app.repositories.case_repo import CaseRepository
from backend.app.schemas.investigation import (
    InvestigationQuery,
    InvestigationQueryInterpretation,
    InvestigationQueryRequest,
    InvestigationQueryResponse,
    InvestigationRetrievalPlan,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.search_service import ForensicSearchService

logger = logging.getLogger(__name__)


class ForensicInvestigationService:
    """Case-scoped investigation query orchestration service."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.case_repo = CaseRepository(session)
        self.audit_service = AuditService(session)
        self.search_service = ForensicSearchService(session)
        self.nlp_pipeline = get_nlp_pipeline()

    async def _verify_case_access(self, case_id: UUID, user: User) -> None:
        """Verify case exists and user is a member with valid permissions."""
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

    async def parse_investigation_query(
        self,
        case_id: UUID,
        user: User,
        request: InvestigationQueryRequest
    ) -> InvestigationQuery:
        """Parse natural language query without executing retrieval (for preview / inspection)."""
        await self._verify_case_access(case_id, user)
        return self.nlp_pipeline.parse_query(
            raw_query=request.query,
            case_id=case_id,
            user_requested_mode=request.retrieval_mode
        )

    async def execute_investigation_query(
        self,
        case_id: UUID,
        user: User,
        request: InvestigationQueryRequest
    ) -> InvestigationQueryResponse:
        """Execute full NLP query understanding, search execution, and audit logging."""
        start_time = time.perf_counter()

        # Step 1: Authorization
        await self._verify_case_access(case_id, user)

        # Step 2: NLP Query Pipeline
        parsed_query: InvestigationQuery = self.nlp_pipeline.parse_query(
            raw_query=request.query,
            case_id=case_id,
            user_requested_mode=request.retrieval_mode
        )

        plan: InvestigationRetrievalPlan = self.nlp_pipeline.query_planner.plan(
            raw_query=parsed_query.normalized_query,
            intent=parsed_query.intent,
            entities=parsed_query.entities,
            temporal_constraints=parsed_query.temporal_constraints,
            user_requested_mode=request.retrieval_mode
        )

        # Step 3: Map Plan to Search Parameters
        artifact_type: Optional[ArtifactType] = None
        if "artifact_type" in plan.filters:
            try:
                artifact_type = ArtifactType(plan.filters["artifact_type"])
            except ValueError:
                pass

        entity_type: Optional[EntityType] = None
        if "entity_type" in plan.filters:
            try:
                entity_type = EntityType(plan.filters["entity_type"])
            except ValueError:
                pass

        start_dt: Optional[datetime] = None
        if "start_time" in plan.filters:
            try:
                start_dt = datetime.fromisoformat(plan.filters["start_time"])
            except Exception:
                pass

        end_dt: Optional[datetime] = None
        if "end_time" in plan.filters:
            try:
                end_dt = datetime.fromisoformat(plan.filters["end_time"])
            except Exception:
                pass

        precision: Optional[TimestampPrecision] = None
        if "timestamp_precision" in plan.filters:
            try:
                precision = TimestampPrecision(plan.filters["timestamp_precision"])
            except ValueError:
                pass

        # Step 4: Execute Retrieval via ForensicSearchService (Phase 9 & 10)
        search_res = await self.search_service.search(
            case_id=case_id,
            current_user=user,
            mode=plan.mode,
            q=plan.search_text if plan.search_text else None,
            artifact_type=artifact_type,
            device_id=plan.filters.get("device_id"),
            application=plan.filters.get("application"),
            entity_type=plan.filters.get("entity_type"),
            entity_value=plan.filters.get("entity_value"),
            start_time=start_dt,
            end_time=end_dt,
            timestamp_precision=precision,
            page_size=request.page_size,
            cursor=request.cursor,
            include_facets=request.include_facets,
        )

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Step 5: Query Transparency Interpretation
        interpretation = self.nlp_pipeline.get_interpretation(parsed_query, plan)

        # Step 6: Audit Logging
        audit_details = {
            "query_id": str(parsed_query.query_id),
            "raw_query": parsed_query.raw_query,
            "intent": parsed_query.intent.type.value,
            "intent_confidence": parsed_query.intent.confidence,
            "entities_count": len(parsed_query.entities),
            "entities": [{"type": e.type.value, "val": e.normalized_value} for e in parsed_query.entities],
            "temporal_constraints_count": len(parsed_query.temporal_constraints),
            "retrieval_mode": plan.mode.value,
            "recommended_mode": plan.recommended_mode.value,
            "result_count": len(search_res.results),
            "parser_version": parsed_query.parser_version,
            "duration_ms": duration_ms
        }

        try:
            action_val = AuditAction.INVESTIGATION_QUERY_EXECUTED.value if hasattr(AuditAction.INVESTIGATION_QUERY_EXECUTED, "value") else str(AuditAction.INVESTIGATION_QUERY_EXECUTED)
            await self.audit_service.record_event(
                action=action_val,
                resource_type="investigation_query",
                status="SUCCESS",
                user_id=user.id,
                case_id=case_id,
                details=audit_details,
            )
        except Exception as e:
            logger.warning("Failed to record audit log for investigation query: %s", e)

        return InvestigationQueryResponse(
            query_id=parsed_query.query_id,
            case_id=case_id,
            raw_query=request.query,
            interpretation=interpretation,
            retrieval_plan=plan,
            results=search_res.results,
            facets=search_res.facets,
            pagination=search_res.pagination,
            duration_ms=duration_ms
        )
