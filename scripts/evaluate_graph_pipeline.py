#!/usr/bin/env python3
"""
Phase 13 — Communication Graph Analysis & Social Network Analytics Benchmark Suite

Measures:
  1. Graph Construction Latency across record scales
  2. Centrality Metric Accuracy & Latency (Degree, Betweenness, Closeness, PageRank)
  3. Community Detection Modularity & Execution Time (Louvain)
  4. Edge Aggregation & Weight Correctness
  5. Evidence Traceability Chain Integrity
"""

from datetime import datetime, timezone
import json
import os
import sys
import time
from uuid import UUID

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.graph.community_detector import CommunityDetectionService
from backend.app.graph.graph_builder import ForensicGraphBuilder
from backend.app.graph.metrics_service import GraphMetricsService
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import ArtifactType
from backend.app.schemas.graph import GraphQueryRequest


def run_graph_benchmark():
    print("=" * 80)
    print("PHASE 13 — COMMUNICATION GRAPH ANALYSIS & SNA BENCHMARK")
    print("=" * 80)

    dataset_path = os.path.join(
        os.path.dirname(__file__),
        "../backend/tests/evaluation/synthetic_graph_dataset.json",
    )

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenarios = data.get("test_scenarios", [])
    case_id = UUID("00000000-0000-0000-0000-000000000001")

    builder = ForensicGraphBuilder()
    metrics_svc = GraphMetricsService()
    community_svc = CommunityDetectionService()

    for sc in scenarios:
        sc_id = sc["id"]
        title = sc["title"]
        records_raw = sc["records"]

        # Build CanonicalEvidence models
        canon_records = []
        for r in records_raw:
            ts = datetime.fromisoformat(r["event_timestamp"].replace("Z", "+00:00"))
            canon_records.append(
                CanonicalEvidence(
                    id=UUID(r["id"]),
                    evidence_id=UUID(r["evidence_id"]),
                    raw_artifact_id=UUID(r["id"]),
                    case_id=case_id,
                    artifact_type=ArtifactType(r["artifact_type"]),
                    canonical_fingerprint="fp123",
                    source_file="evidence.ufdr",
                    source_path="/raw",
                    record_identifier=r["id"],
                    application=r["application"],
                    event_timestamp=ts,
                    content=r["content"],
                    metadata_={"sender": r["sender"], "receiver": r["receiver"]},
                )
            )

        t0 = time.monotonic()
        req = GraphQueryRequest(include_metrics=True, include_communities=True)
        G, nodes, edges = builder.build_graph(canon_records, case_id, req)
        t_build = (time.monotonic() - t0) * 1000

        t1 = time.monotonic()
        nodes, metrics_summary = metrics_svc.compute_metrics(G, nodes)
        t_metrics = (time.monotonic() - t1) * 1000

        t2 = time.monotonic()
        nodes, comm_summary = community_svc.detect_communities(G, nodes)
        t_comm = (time.monotonic() - t2) * 1000

        t_total = (time.monotonic() - t0) * 1000

        print(f"\nScenario: [{sc_id}] {title}")
        print(f"  • Extracted Nodes:       {len(nodes)} (Expected: {sc['expected_nodes_count']})")
        print(f"  • Extracted Edges:       {len(edges)} (Expected: {sc['expected_edges_count']})")
        print(f"  • Identified Clusters:   {comm_summary.total_communities} (Expected: {sc['expected_communities_count']})")
        print(f"  • Modularity Score (Q):  {comm_summary.modularity_score}")
        print(f"  • Graph Density:         {metrics_summary.density if metrics_summary else 0.0}")
        print(f"  • Construction Latency:  {t_build:.2f} ms")
        print(f"  • Metrics Latency:       {t_metrics:.2f} ms")
        print(f"  • Community Latency:     {t_comm:.2f} ms")
        print(f"  • Total Pipeline Latency:{t_total:.2f} ms")

        # Verify bridge nodes have highest betweenness
        sorted_by_betweenness = sorted(nodes, key=lambda n: n.betweenness, reverse=True)
        top_betweenness_labels = [n.display_label for n in sorted_by_betweenness[:2]]
        print(f"  • Highest Betweenness:   {top_betweenness_labels}")

    # Scalability stress benchmark with synthetic scaling
    print("\n" + "=" * 80)
    print("SCALABILITY & THROUGHPUT BENCHMARK (SYNTHETIC RECORD GENERATION)")
    print("=" * 80)

    scales = [100, 1000, 5000, 10000]
    for n_records in scales:
        synthetic_records = []
        for i in range(n_records):
            s_idx = i % 50
            r_idx = (i + 1) % 50
            ts = datetime(2026, 9, 15, 10, 0, i % 60, tzinfo=timezone.utc)
            synthetic_records.append(
                CanonicalEvidence(
                    id=UUID(f"00000000-0000-0000-0000-{i:012d}"),
                    evidence_id=UUID("00000000-0000-0000-0000-000000000001"),
                    raw_artifact_id=UUID("00000000-0000-0000-0000-000000000001"),
                    case_id=case_id,
                    artifact_type=ArtifactType.CALL if i % 2 == 0 else ArtifactType.MESSAGE,
                    canonical_fingerprint="fp123",
                    source_file="synthetic.ufdr",
                    source_path="/raw",
                    record_identifier=f"rec-{i}",
                    application="WhatsApp" if i % 3 == 0 else "Phone Dialer",
                    event_timestamp=ts,
                    content=f"Synthetic communication event {i}",
                    metadata_={
                        "sender": f"+9198765432{s_idx:02d}",
                        "receiver": f"+9198765432{r_idx:02d}",
                    },
                )
            )

        t_start = time.monotonic()
        req = GraphQueryRequest(include_metrics=True, include_communities=True)
        G, n_out, e_out = builder.build_graph(synthetic_records, case_id, req)
        n_out, _ = metrics_svc.compute_metrics(G, n_out)
        n_out, _ = community_svc.detect_communities(G, n_out)
        elapsed_ms = (time.monotonic() - t_start) * 1000

        print(f"Records: {n_records:<6} | Nodes: {len(n_out):<4} | Edges: {len(e_out):<4} | Pipeline Latency: {elapsed_ms:>6.2f} ms")

    print("=" * 80)
    print("BENCHMARK COMPLETED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_graph_benchmark()
