from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
import uuid
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.errors import ForensicAppException
from backend.app.graph.community_detector import CommunityDetectionService
from backend.app.graph.graph_builder import ForensicGraphBuilder
from backend.app.graph.metrics_service import GraphMetricsService
from backend.app.graph.snapshot_manager import graph_snapshot_manager
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import ArtifactType, AuditAction
from backend.app.models.user import User
from backend.app.repositories.case_repo import CaseRepository
from backend.app.schemas.graph import (
    GraphEdge,
    GraphNode,
    GraphQueryRequest,
    GraphQueryResponse,
    GraphSnapshotRecord,
)
from backend.app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class ForensicGraphService:
    """
    Orchestrates Phase 13 Communication Graph & Social Network Analytics.
    Coordinates evidence retrieval, NetworkX graph modeling, centrality computations,
    deterministic community clustering, snapshot versioning, and forensic audit logging.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.case_repo = CaseRepository(session)
        self.audit_service = AuditService(session)
        self.graph_builder = ForensicGraphBuilder()
        self.metrics_service = GraphMetricsService()
        self.community_service = CommunityDetectionService()

    async def _verify_case_access(self, case_id: UUID, user: User) -> None:
        """Verify case exists and user has authorization."""
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

    async def generate_communication_graph(
        self,
        case_id: UUID,
        current_user: User,
        request: GraphQueryRequest,
        client_ip: Optional[str] = None,
    ) -> GraphQueryResponse:
        t_start = time.monotonic()
        await self._verify_case_access(case_id, current_user)

        case_id_str = str(case_id)
        snapshot_id = f"graph-{uuid.uuid4().hex[:12]}"

        # Step 1: Query canonical communication records for this case
        stmt = (
            select(CanonicalEvidence)
            .where(
                CanonicalEvidence.case_id == case_id,
                CanonicalEvidence.artifact_type.in_([
                    ArtifactType.CALL,
                    ArtifactType.MESSAGE,
                    ArtifactType.CONTACT,
                    ArtifactType.SOCIAL,
                ]),
            )
            .order_by(CanonicalEvidence.event_timestamp.asc())
        )
        result = await self.session.execute(stmt)
        canonical_records = list(result.scalars().all())

        # Step 2: Build NetworkX DiGraph and schema representations
        G, schema_nodes, schema_edges = self.graph_builder.build_graph(
            records=canonical_records,
            case_id=case_id,
            request=request,
        )

        # Step 3: Compute Centrality & Structural Metrics
        metrics_summary = None
        if request.include_metrics:
            schema_nodes, metrics_summary = self.metrics_service.compute_metrics(G, schema_nodes)

        # Step 4: Community Detection
        communities_summary = None
        if request.include_communities:
            schema_nodes, communities_summary = self.community_service.detect_communities(G, schema_nodes)

        latency_ms = round((time.monotonic() - t_start) * 1000, 2)

        reproducibility = {
            "graph_version": settings.GRAPH_VERSION,
            "algorithm": "NetworkX-DiGraph",
            "community_algorithm": settings.GRAPH_COMMUNITY_ALGORITHM,
            "community_random_seed": settings.GRAPH_COMMUNITY_RANDOM_SEED,
            "total_canonical_records_evaluated": len(canonical_records),
            "filters_applied": request.model_dump(mode="json") if hasattr(request, "model_dump") else request,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Step 5: Audit Logging
        await self.audit_service.record_event(
            action=AuditAction.GRAPH_ANALYSIS_EXECUTED.value if hasattr(AuditAction.GRAPH_ANALYSIS_EXECUTED, "value") else str(AuditAction.GRAPH_ANALYSIS_EXECUTED),
            resource_type="communication_graph",
            status="SUCCESS",
            user_id=current_user.id,
            resource_id=snapshot_id,
            case_id=case_id,
            details={
                "snapshot_id": snapshot_id,
                "node_count": len(schema_nodes),
                "edge_count": len(schema_edges),
                "center_node": request.center_node,
                "depth": request.depth,
                "latency_ms": latency_ms,
            },
            client_ip=client_ip,
        )

        return GraphQueryResponse(
            snapshot_id=snapshot_id,
            case_id=case_id_str,
            nodes=schema_nodes,
            edges=schema_edges,
            metrics_summary=metrics_summary,
            communities_summary=communities_summary,
            reproducibility=reproducibility,
            latency_ms=latency_ms,
        )

    async def get_node_details(
        self,
        case_id: UUID,
        node_id: str,
        current_user: User,
    ) -> GraphNode:
        await self._verify_case_access(case_id, current_user)
        # Generate baseline graph to extract current node state
        req = GraphQueryRequest(depth=1, center_node=node_id)
        graph_res = await self.generate_communication_graph(case_id, current_user, req)
        for n in graph_res.nodes:
            if n.node_id == node_id:
                return n
        raise ForensicAppException(
            message=f"Node '{node_id}' not found in case graph.",
            code="NODE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    async def get_edge_details(
        self,
        case_id: UUID,
        edge_id: str,
        current_user: User,
    ) -> GraphEdge:
        await self._verify_case_access(case_id, current_user)
        req = GraphQueryRequest()
        graph_res = await self.generate_communication_graph(case_id, current_user, req)
        for e in graph_res.edges:
            if e.edge_id == edge_id:
                return e
        raise ForensicAppException(
            message=f"Edge '{edge_id}' not found in case graph.",
            code="EDGE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    async def create_snapshot(
        self,
        case_id: UUID,
        current_user: User,
        title: str,
        query_params: GraphQueryRequest,
        client_ip: Optional[str] = None,
    ) -> GraphSnapshotRecord:
        await self._verify_case_access(case_id, current_user)
        graph_res = await self.generate_communication_graph(case_id, current_user, query_params, client_ip)

        snapshot_record = graph_snapshot_manager.create_snapshot(
            case_id=case_id,
            title=title,
            query_params=query_params,
            nodes=graph_res.nodes,
            edges=graph_res.edges,
            metrics_summary=graph_res.metrics_summary.model_dump() if graph_res.metrics_summary else None,
            reproducibility=graph_res.reproducibility,
            user_id=str(current_user.id),
        )

        await self.audit_service.record_event(
            action=AuditAction.GRAPH_SNAPSHOT_CREATED.value if hasattr(AuditAction.GRAPH_SNAPSHOT_CREATED, "value") else str(AuditAction.GRAPH_SNAPSHOT_CREATED),
            resource_type="graph_snapshot",
            status="SUCCESS",
            user_id=current_user.id,
            resource_id=snapshot_record.snapshot_id,
            case_id=case_id,
            details={
                "snapshot_id": snapshot_record.snapshot_id,
                "title": title,
                "node_count": snapshot_record.node_count,
                "edge_count": snapshot_record.edge_count,
            },
            client_ip=client_ip,
        )

        return snapshot_record

    async def list_snapshots(
        self,
        case_id: UUID,
        current_user: User,
    ) -> List[GraphSnapshotRecord]:
        await self._verify_case_access(case_id, current_user)
        return graph_snapshot_manager.list_snapshots_for_case(case_id)

    async def get_snapshot_data(
        self,
        case_id: UUID,
        snapshot_id: str,
        current_user: User,
    ) -> Dict[str, Any]:
        await self._verify_case_access(case_id, current_user)
        snap = graph_snapshot_manager.get_snapshot(case_id, snapshot_id)
        if not snap:
            raise ForensicAppException(
                message=f"Snapshot '{snapshot_id}' not found in case.",
                code="SNAPSHOT_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return snap
