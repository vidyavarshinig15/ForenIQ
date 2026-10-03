from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.models.enums import CommunityAlgorithm, EdgeType, NodeType


class GraphNode(BaseModel):
    """
    Normalized forensic graph entity node.
    Represents persons, phone numbers, accounts, emails, devices, or applications.
    """
    node_id: str = Field(..., description="Deterministic unique node identifier within case scope")
    case_id: str = Field(..., description="Case ID enforcing cross-case isolation")
    node_type: NodeType = Field(..., description="Entity classification")
    display_label: str = Field(..., description="Human-readable node label")
    normalized_value: str = Field(..., description="Normalized entity string (E.164 phone, clean email, etc.)")
    source_references: List[Dict[str, Any]] = Field(default_factory=list, description="Traceability references")
    first_observed: Optional[str] = Field(None, description="Earliest recorded event timestamp")
    last_observed: Optional[str] = Field(None, description="Latest recorded event timestamp")
    degree: int = Field(0, description="Total direct connections")
    in_degree: int = Field(0, description="Inbound communication connections")
    out_degree: int = Field(0, description="Outbound communication connections")
    weighted_degree: float = Field(0.0, description="Total interaction count across connected edges")
    betweenness: float = Field(0.0, description="Betweenness centrality score")
    closeness: float = Field(0.0, description="Closeness centrality score")
    pagerank: float = Field(0.0, description="PageRank structural connectivity score")
    community_id: Optional[int] = Field(None, description="Mathematical cluster identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Forensic metadata")


class GraphEdge(BaseModel):
    """
    Normalized forensic communication interaction edge.
    Represents calls, messages, emails, or chats between entity nodes.
    """
    edge_id: str = Field(..., description="Deterministic unique edge identifier")
    case_id: str = Field(..., description="Case ID enforcing cross-case isolation")
    source_node_id: str = Field(..., description="Originating node ID (caller / sender / sender account)")
    target_node_id: str = Field(..., description="Recipient node ID (callee / recipient / target account)")
    edge_type: EdgeType = Field(..., description="Communication interaction category")
    weight: int = Field(1, description="Number of recorded communication interactions")
    first_timestamp: Optional[str] = Field(None, description="Earliest communication timestamp")
    last_timestamp: Optional[str] = Field(None, description="Latest communication timestamp")
    timestamps: List[str] = Field(default_factory=list, description="Chronological timestamps of interactions")
    source_canonical_ids: List[str] = Field(default_factory=list, description="Canonical record IDs")
    source_evidence_ids: List[str] = Field(default_factory=list, description="Evidence upload IDs")
    applications: List[str] = Field(default_factory=list, description="Applications used (WhatsApp, SMS, Signal, etc.)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Edge metadata")


class GraphMetricsSummary(BaseModel):
    """
    Mathematical graph structural metrics and neutral educational explanations.
    """
    total_nodes: int = Field(..., description="Total node count in graph")
    total_edges: int = Field(..., description="Total edge count in graph")
    density: float = Field(..., description="Graph density measure (ratio of actual to possible edges)")
    average_degree: float = Field(..., description="Mean degree across all nodes")
    is_connected: bool = Field(..., description="Whether all nodes are mutually reachable")
    connected_components_count: int = Field(..., description="Number of disconnected subgraphs")
    metric_explanations: Dict[str, str] = Field(
        default_factory=lambda: {
            "degree": "Number of direct communication links connected to this entity in the selected evidence.",
            "in_degree": "Number of inbound communication channels received by this entity.",
            "out_degree": "Number of outbound communication channels initiated by this entity.",
            "weighted_degree": "Total volume of interactions (calls, messages) involving this entity.",
            "betweenness": "Mathematical measure of how often an entity falls on the shortest path between other entities in the network.",
            "closeness": "Mathematical measure of the average distance from this entity to all other reachable entities in the graph.",
            "pagerank": "Structural connectivity metric evaluating the relative centrality of an entity based on the connectivity of its neighbors.",
        }
    )


class CommunitySummary(BaseModel):
    """
    Mathematical community clustering results.
    """
    algorithm: CommunityAlgorithm = Field(..., description="Applied community detection algorithm")
    total_communities: int = Field(..., description="Total number of identified structural clusters")
    modularity_score: Optional[float] = Field(None, description="Modularity metric (Q-score)")
    community_sizes: Dict[int, int] = Field(default_factory=dict, description="Node counts per community cluster")
    description: str = Field(
        "Communities represent mathematical groupings based purely on communication frequency and network topology. "
        "They do not signify criminal conspiracy, coordinated intent, or organizational guilt."
    )


class GraphQueryRequest(BaseModel):
    """
    Investigator request to generate or filter a forensic communication graph.
    """
    time_range_start: Optional[datetime] = Field(None, description="Start date/time filter")
    time_range_end: Optional[datetime] = Field(None, description="End date/time filter")
    communication_types: Optional[List[EdgeType]] = Field(None, description="Restricted communication categories")
    applications: Optional[List[str]] = Field(None, description="Restricted application names (e.g. WhatsApp, SMS)")
    center_node: Optional[str] = Field(None, description="Focal entity identifier for ego-network exploration")
    depth: Optional[int] = Field(2, ge=1, le=4, description="Ego-network expansion depth (hops from center node)")
    min_weight: Optional[int] = Field(1, ge=1, description="Minimum interaction count required for edge inclusion")
    max_nodes: Optional[int] = Field(None, ge=10, le=1000, description="Max node safety limit")
    include_metrics: bool = Field(True, description="Whether to compute centrality and degree metrics")
    include_communities: bool = Field(True, description="Whether to run community detection clustering")


class GraphQueryResponse(BaseModel):
    """
    Case-scoped communication graph response for visualization and analysis.
    """
    snapshot_id: str = Field(..., description="Unique graph snapshot identifier")
    case_id: str = Field(..., description="Active forensic case ID")
    nodes: List[GraphNode] = Field(default_factory=list, description="Extracted entity nodes")
    edges: List[GraphEdge] = Field(default_factory=list, description="Extracted communication edges")
    metrics_summary: Optional[GraphMetricsSummary] = Field(None, description="Graph-level topology metrics")
    communities_summary: Optional[CommunitySummary] = Field(None, description="Community detection summary")
    reproducibility: Dict[str, Any] = Field(default_factory=dict, description="Metadata for reproducing graph")
    latency_ms: float = Field(..., description="Pipeline execution latency in milliseconds")


class GraphSnapshotCreateRequest(BaseModel):
    """
    Request to persist a named graph snapshot.
    """
    title: str = Field(..., min_length=2, max_length=150, description="Snapshot title / description")
    query_params: GraphQueryRequest = Field(..., description="Query parameters used to generate the snapshot")


class GraphSnapshotRecord(BaseModel):
    """
    Persisted reproducible snapshot record.
    """
    snapshot_id: str
    case_id: str
    title: str
    created_at: str
    created_by_user_id: Optional[str]
    node_count: int
    edge_count: int
    query_params: Dict[str, Any]
    reproducibility: Dict[str, Any]
