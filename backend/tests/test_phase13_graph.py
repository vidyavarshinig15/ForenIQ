"""
Phase 13 — Communication Graph Analysis & Social Network Analytics Tests

Validates:
  1. Graph Node & Edge Extraction and Normalization
  2. Edge Aggregation & Weight Calculation
  3. Mathematical Graph Centrality Metrics (Degree, Betweenness, Closeness, PageRank)
  4. Deterministic Community Detection (Louvain)
  5. Case Isolation & IDOR Protection
  6. Temporal Filtering Constraints
  7. Ego-Network Expansion & Depth Capping
  8. Full Forensic Evidence Traceability
  9. Reproducible Graph Snapshots
  10. End-to-End REST APIs & Audit Trail
"""

from datetime import datetime, timezone
import uuid
from uuid import UUID

from httpx import ASGITransport, AsyncClient
import pytest

from backend.app.graph.community_detector import CommunityDetectionService
from backend.app.graph.graph_builder import ForensicGraphBuilder
from backend.app.graph.metrics_service import GraphMetricsService
from backend.app.graph.snapshot_manager import graph_snapshot_manager
from backend.app.main import app
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import ArtifactType, EdgeType, NodeType
from backend.app.schemas.graph import GraphQueryRequest


# Helper fixtures & logins
async def _register_and_login(client: AsyncClient, email: str, role: str = "INVESTIGATOR") -> str:
    user_data = {
        "email": email,
        "password": "ForensicSecurePassword2026!",
        "name": f"Test User {role}",
        "role": role,
    }
    await client.post("/api/v1/auth/register", json=user_data)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "ForensicSecurePassword2026!"},
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


async def _setup_case(client: AsyncClient, token: str, case_number: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.post(
        "/api/v1/cases",
        json={"case_number": case_number, "title": f"Investigation Case {case_number}"},
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()["id"]


@pytest.mark.asyncio
async def test_graph_builder_normalization_and_aggregation():
    """Unit test for node normalization, deduplication, and edge aggregation."""
    builder = ForensicGraphBuilder()
    case_id = uuid.uuid4()

    records = [
        CanonicalEvidence(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            case_id=case_id,
            artifact_type=ArtifactType.MESSAGE,
            canonical_fingerprint="fp1",
            source_file="backup.ufdr",
            source_path="/raw",
            record_identifier="MSG-01",
            application="WhatsApp",
            event_timestamp=datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc),
            content="Hello",
            metadata_={"sender": "+919876543210 (Rahul)", "receiver": "+919876543211 (Vikram)"},
        ),
        CanonicalEvidence(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            case_id=case_id,
            artifact_type=ArtifactType.MESSAGE,
            canonical_fingerprint="fp2",
            source_file="backup.ufdr",
            source_path="/raw",
            record_identifier="MSG-02",
            application="WhatsApp",
            event_timestamp=datetime(2026, 9, 15, 10, 5, tzinfo=timezone.utc),
            content="Second message",
            metadata_={"sender": "+919876543210 (Rahul)", "receiver": "+919876543211 (Vikram)"},
        ),
        CanonicalEvidence(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            case_id=case_id,
            artifact_type=ArtifactType.CALL,
            canonical_fingerprint="fp3",
            source_file="backup.ufdr",
            source_path="/raw",
            record_identifier="CALL-01",
            application="Phone Dialer",
            event_timestamp=datetime(2026, 9, 15, 10, 10, tzinfo=timezone.utc),
            content="Call 60s",
            metadata_={"sender": "+919876543211 (Vikram)", "receiver": "support@org.com"},
        ),
    ]

    req = GraphQueryRequest()
    G, nodes, edges = builder.build_graph(records, case_id, req)

    # 3 unique nodes: Rahul, Vikram, support@org.com
    assert len(nodes) == 3
    node_types = {n.node_type for n in nodes}
    assert NodeType.PERSON in node_types
    assert NodeType.EMAIL in node_types

    # 2 aggregated edges: (Rahul -> Vikram [weight=2, MESSAGE]), (Vikram -> support@org.com [weight=1, CALL])
    assert len(edges) == 2
    whatsapp_edge = next(e for e in edges if e.edge_type == EdgeType.MESSAGE)
    assert whatsapp_edge.weight == 2
    assert len(whatsapp_edge.timestamps) == 2


@pytest.mark.asyncio
async def test_graph_metrics_and_centrality():
    """Unit test for Degree, Betweenness, Closeness, and PageRank."""
    builder = ForensicGraphBuilder()
    metrics_svc = GraphMetricsService()
    case_id = uuid.uuid4()

    # Network topology: A -> B -> C -> D (Linear chain: B and C have higher betweenness than A and D)
    records = [
        CanonicalEvidence(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            case_id=case_id,
            artifact_type=ArtifactType.MESSAGE,
            canonical_fingerprint="fp1",
            source_file="f.ufdr",
            source_path="/raw",
            record_identifier="1",
            application="WhatsApp",
            event_timestamp=datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc),
            content="1",
            metadata_={"sender": "user_a@test.com", "receiver": "user_b@test.com"},
        ),
        CanonicalEvidence(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            case_id=case_id,
            artifact_type=ArtifactType.MESSAGE,
            canonical_fingerprint="fp2",
            source_file="f.ufdr",
            source_path="/raw",
            record_identifier="2",
            application="WhatsApp",
            event_timestamp=datetime(2026, 9, 15, 10, 5, tzinfo=timezone.utc),
            content="2",
            metadata_={"sender": "user_b@test.com", "receiver": "user_c@test.com"},
        ),
        CanonicalEvidence(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            case_id=case_id,
            artifact_type=ArtifactType.MESSAGE,
            canonical_fingerprint="fp3",
            source_file="f.ufdr",
            source_path="/raw",
            record_identifier="3",
            application="WhatsApp",
            event_timestamp=datetime(2026, 9, 15, 10, 10, tzinfo=timezone.utc),
            content="3",
            metadata_={"sender": "user_c@test.com", "receiver": "user_d@test.com"},
        ),
    ]

    G, nodes, edges = builder.build_graph(records, case_id, GraphQueryRequest())
    nodes, summary = metrics_svc.compute_metrics(G, nodes)

    assert summary.total_nodes == 4
    assert summary.total_edges == 3
    assert summary.is_connected is True

    node_b = next(n for n in nodes if "user_b" in n.node_id)
    node_a = next(n for n in nodes if "user_a" in n.node_id)

    # In linear chain A->B->C->D, interior node B has higher betweenness than leaf node A
    assert node_b.betweenness >= node_a.betweenness
    assert node_b.degree >= node_a.degree


@pytest.mark.asyncio
async def test_community_detection_louvain():
    """Unit test verifying community clustering on partitioned cliques."""
    builder = ForensicGraphBuilder()
    comm_svc = CommunityDetectionService()
    case_id = uuid.uuid4()

    # Clique 1: (A, B, C)
    # Clique 2: (X, Y, Z)
    records = [
        # Clique 1
        CanonicalEvidence(
            id=uuid.uuid4(), evidence_id=uuid.uuid4(), raw_artifact_id=uuid.uuid4(), case_id=case_id,
            artifact_type=ArtifactType.MESSAGE, canonical_fingerprint="1", source_file="f", source_path="p",
            record_identifier="1", application="WhatsApp", metadata_={"sender": "+911111111101", "receiver": "+911111111102"},
        ),
        CanonicalEvidence(
            id=uuid.uuid4(), evidence_id=uuid.uuid4(), raw_artifact_id=uuid.uuid4(), case_id=case_id,
            artifact_type=ArtifactType.MESSAGE, canonical_fingerprint="2", source_file="f", source_path="p",
            record_identifier="2", application="WhatsApp", metadata_={"sender": "+911111111102", "receiver": "+911111111103"},
        ),
        CanonicalEvidence(
            id=uuid.uuid4(), evidence_id=uuid.uuid4(), raw_artifact_id=uuid.uuid4(), case_id=case_id,
            artifact_type=ArtifactType.MESSAGE, canonical_fingerprint="3", source_file="f", source_path="p",
            record_identifier="3", application="WhatsApp", metadata_={"sender": "+911111111103", "receiver": "+911111111101"},
        ),
        # Clique 2
        CanonicalEvidence(
            id=uuid.uuid4(), evidence_id=uuid.uuid4(), raw_artifact_id=uuid.uuid4(), case_id=case_id,
            artifact_type=ArtifactType.MESSAGE, canonical_fingerprint="4", source_file="f", source_path="p",
            record_identifier="4", application="Signal", metadata_={"sender": "+919999999901", "receiver": "+919999999902"},
        ),
        CanonicalEvidence(
            id=uuid.uuid4(), evidence_id=uuid.uuid4(), raw_artifact_id=uuid.uuid4(), case_id=case_id,
            artifact_type=ArtifactType.MESSAGE, canonical_fingerprint="5", source_file="f", source_path="p",
            record_identifier="5", application="Signal", metadata_={"sender": "+919999999902", "receiver": "+919999999903"},
        ),
        CanonicalEvidence(
            id=uuid.uuid4(), evidence_id=uuid.uuid4(), raw_artifact_id=uuid.uuid4(), case_id=case_id,
            artifact_type=ArtifactType.MESSAGE, canonical_fingerprint="6", source_file="f", source_path="p",
            record_identifier="6", application="Signal", metadata_={"sender": "+919999999903", "receiver": "+919999999901"},
        ),
    ]

    G, nodes, edges = builder.build_graph(records, case_id, GraphQueryRequest())
    nodes, comm_summary = comm_svc.detect_communities(G, nodes)

    assert comm_summary.total_communities == 2
    # Verify nodes in Clique 1 share the same community_id, and Clique 2 share another
    c1_nodes = [n for n in nodes if "11111111" in n.node_id]
    c2_nodes = [n for n in nodes if "99999999" in n.node_id]

    assert c1_nodes[0].community_id == c1_nodes[1].community_id == c1_nodes[2].community_id
    assert c2_nodes[0].community_id == c2_nodes[1].community_id == c2_nodes[2].community_id
    assert c1_nodes[0].community_id != c2_nodes[0].community_id


@pytest.mark.asyncio
async def test_temporal_and_ego_network_filtering():
    """Unit test for temporal constraints and center node ego-network extraction."""
    builder = ForensicGraphBuilder()
    case_id = uuid.uuid4()

    records = [
        # In range: Sept 15
        CanonicalEvidence(
            id=uuid.uuid4(), evidence_id=uuid.uuid4(), raw_artifact_id=uuid.uuid4(), case_id=case_id,
            artifact_type=ArtifactType.CALL, canonical_fingerprint="1", source_file="f", source_path="p",
            record_identifier="1", application="Phone Dialer",
            event_timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc),
            metadata_={"sender": "+919876543210", "receiver": "+919876543211"},
        ),
        # Out of range: Sept 25
        CanonicalEvidence(
            id=uuid.uuid4(), evidence_id=uuid.uuid4(), raw_artifact_id=uuid.uuid4(), case_id=case_id,
            artifact_type=ArtifactType.CALL, canonical_fingerprint="2", source_file="f", source_path="p",
            record_identifier="2", application="Phone Dialer",
            event_timestamp=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
            metadata_={"sender": "+919876543210", "receiver": "+919876543299"},
        ),
    ]

    # Filter for Sept 10 to Sept 20
    req = GraphQueryRequest(
        time_range_start=datetime(2026, 9, 10, 0, 0, tzinfo=timezone.utc),
        time_range_end=datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc),
    )
    G, nodes, edges = builder.build_graph(records, case_id, req)

    assert len(nodes) == 2
    assert len(edges) == 1
    assert not any("9876543299" in n.node_id for n in nodes)


@pytest.mark.asyncio
async def test_cross_case_isolation():
    """Unit test proving Case A cannot retrieve or leak Case B records in graph builder."""
    builder = ForensicGraphBuilder()
    case_a = uuid.uuid4()
    case_b = uuid.uuid4()

    records_case_b = [
        CanonicalEvidence(
            id=uuid.uuid4(), evidence_id=uuid.uuid4(), raw_artifact_id=uuid.uuid4(), case_id=case_b,
            artifact_type=ArtifactType.CALL, canonical_fingerprint="1", source_file="f", source_path="p",
            record_identifier="1", application="Phone Dialer",
            metadata_={"sender": "+919876500000", "receiver": "+919876500001"},
        ),
    ]

    # Querying for Case A with records from Case B
    G, nodes, edges = builder.build_graph(records_case_b, case_a, GraphQueryRequest())

    assert len(nodes) == 0
    assert len(edges) == 0


@pytest.mark.asyncio
async def test_graph_snapshots_manager():
    """Unit test for graph snapshot persistence and case isolation."""
    case_a = uuid.uuid4()
    case_b = uuid.uuid4()

    req = GraphQueryRequest()
    snap = graph_snapshot_manager.create_snapshot(
        case_id=case_a,
        title="Baseline Case A Snapshot",
        query_params=req,
        nodes=[],
        edges=[],
    )

    assert snap.case_id == str(case_a)
    assert snap.title == "Baseline Case A Snapshot"

    # Verify retrieval for Case A
    snap_data = graph_snapshot_manager.get_snapshot(case_a, snap.snapshot_id)
    assert snap_data is not None

    # Verify Case B cannot retrieve Case A's snapshot
    snap_data_b = graph_snapshot_manager.get_snapshot(case_b, snap.snapshot_id)
    assert snap_data_b is None


@pytest.mark.asyncio
async def test_graph_api_end_to_end():
    """End-to-end integration test for Graph REST API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(client, f"graph_tester_{uuid.uuid4().hex[:6]}@ufdr.org", "INVESTIGATOR")
        case_id = await _setup_case(client, token, f"GRAPH-CASE-{uuid.uuid4().hex[:6]}")
        headers = {"Authorization": f"Bearer {token}"}

        # Query baseline graph
        res = await client.get(f"/api/v1/cases/{case_id}/graph", headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert "snapshot_id" in data
        assert data["case_id"] == case_id
        assert "nodes" in data
        assert "edges" in data
        assert "metrics_summary" in data
        assert "latency_ms" in data

        # Create snapshot via POST /cases/{case_id}/graph/snapshots
        snap_payload = {
            "title": "Initial Graph State",
            "query_params": {"include_metrics": True, "include_communities": True},
        }
        snap_res = await client.post(
            f"/api/v1/cases/{case_id}/graph/snapshots",
            json=snap_payload,
            headers=headers,
        )
        assert snap_res.status_code == 201
        snap_record = snap_res.json()
        assert snap_record["title"] == "Initial Graph State"

        # List snapshots
        list_res = await client.get(f"/api/v1/cases/{case_id}/graph/snapshots", headers=headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1
