import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_db
from backend.app.graph.graph_service import ForensicGraphService
from backend.app.models.user import User
from backend.app.schemas.graph import (
    GraphEdge,
    GraphNode,
    GraphQueryRequest,
    GraphQueryResponse,
    GraphSnapshotCreateRequest,
    GraphSnapshotRecord,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/{case_id}/graph/query",
    response_model=GraphQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate or filter forensic communication graph with metrics and communities",
)
async def query_communication_graph(
    case_id: UUID = Path(..., description="Active case ID"),
    request: GraphQueryRequest = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_forwarded_for: Optional[str] = Header(None),
) -> GraphQueryResponse:
    """
    Constructs a case-scoped communication network graph from canonical forensic records:
    - Filters by time range, communication type, applications, or ego-network center node.
    - Computes in/out/weighted degree, betweenness centrality, closeness centrality, and PageRank.
    - Executes deterministic community clustering (Louvain / Modularity).
    - Preserves full forensic evidence and canonical record traceability.
    """
    service = ForensicGraphService(db)
    return await service.generate_communication_graph(
        case_id=case_id,
        current_user=current_user,
        request=request,
        client_ip=x_forwarded_for,
    )


@router.get(
    "/{case_id}/graph",
    response_model=GraphQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve baseline communication graph for case",
)
async def get_baseline_graph(
    case_id: UUID = Path(..., description="Active case ID"),
    center_node: Optional[str] = Query(None, description="Optional center node identifier"),
    depth: int = Query(2, ge=1, le=4, description="Ego-network expansion depth"),
    min_weight: int = Query(1, ge=1, description="Minimum interaction weight threshold"),
    max_nodes: int = Query(500, ge=10, le=1000, description="Max node return cap"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_forwarded_for: Optional[str] = Header(None),
) -> GraphQueryResponse:
    """
    Returns the communication graph structure for visualization.
    """
    req = GraphQueryRequest(
        center_node=center_node,
        depth=depth,
        min_weight=min_weight,
        max_nodes=max_nodes,
    )
    service = ForensicGraphService(db)
    return await service.generate_communication_graph(
        case_id=case_id,
        current_user=current_user,
        request=req,
        client_ip=x_forwarded_for,
    )


@router.get(
    "/{case_id}/graph/nodes/{node_id}",
    response_model=GraphNode,
    status_code=status.HTTP_200_OK,
    summary="Retrieve detailed node entity profile with metrics and source links",
)
async def get_node_details(
    case_id: UUID = Path(..., description="Case ID"),
    node_id: str = Path(..., description="Normalized node identifier"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphNode:
    service = ForensicGraphService(db)
    return await service.get_node_details(case_id, node_id, current_user)


@router.get(
    "/{case_id}/graph/edges/{edge_id}",
    response_model=GraphEdge,
    status_code=status.HTTP_200_OK,
    summary="Retrieve detailed communication edge with interaction history and evidence provenance",
)
async def get_edge_details(
    case_id: UUID = Path(..., description="Case ID"),
    edge_id: str = Path(..., description="Edge identifier"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphEdge:
    service = ForensicGraphService(db)
    return await service.get_edge_details(case_id, edge_id, current_user)


@router.post(
    "/{case_id}/graph/snapshots",
    response_model=GraphSnapshotRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Save a reproducible graph snapshot",
)
async def create_graph_snapshot(
    case_id: UUID = Path(..., description="Case ID"),
    request: GraphSnapshotCreateRequest = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_forwarded_for: Optional[str] = Header(None),
) -> GraphSnapshotRecord:
    service = ForensicGraphService(db)
    return await service.create_snapshot(
        case_id=case_id,
        current_user=current_user,
        title=request.title,
        query_params=request.query_params,
        client_ip=x_forwarded_for,
    )


@router.get(
    "/{case_id}/graph/snapshots",
    response_model=List[GraphSnapshotRecord],
    status_code=status.HTTP_200_OK,
    summary="List reproducible graph snapshots for case",
)
async def list_graph_snapshots(
    case_id: UUID = Path(..., description="Case ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[GraphSnapshotRecord]:
    service = ForensicGraphService(db)
    return await service.list_snapshots(case_id, current_user)


@router.get(
    "/{case_id}/graph/snapshots/{snapshot_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Retrieve full data for a saved graph snapshot",
)
async def get_snapshot_data(
    case_id: UUID = Path(..., description="Case ID"),
    snapshot_id: str = Path(..., description="Snapshot ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = ForensicGraphService(db)
    return await service.get_snapshot_data(case_id, snapshot_id, current_user)
