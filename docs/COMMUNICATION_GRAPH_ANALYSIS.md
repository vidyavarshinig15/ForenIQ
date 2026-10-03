# Phase 13 — Communication Graph Analysis & Social Network Analytics (SNA)

**AI-Driven Intelligent UFDR Analysis System for Advanced Digital Forensic Investigations**  
**Team:** Vidyavarshini G, Suhani A N, Vyshanth S U  
**Guide:** Dr. Prasad M R  

---

## 1. Executive Summary & Forensic Context
Phase 13 introduces a deterministic, case-scoped Communication Graph Construction and Social Network Analysis (SNA) engine derived directly from canonical forensic records (`CanonicalEvidence`). 

Forensic investigations often involve thousands of call logs, SMS threads, chat conversations, emails, and contact records across multiple mobile extractions. Phase 13 structures these interactions into directed, weighted multi-graphs and ego-networks to provide investigators with mathematical clarity on communication topologies while preserving complete evidence traceability and strictly enforcing non-speculative forensic boundaries.

```
UFDR Evidence
      ↓
Canonical Communication Records
      ↓
Forensic Graph Construction (Deterministic Case-Scoped Nodes & Edges)
      ↓
NetworkX Analysis (Centrality, Weighted Metrics, Network Density)
      ↓
Community Detection (Louvain / Modularity-Optimized Clustering)
      ↓
Temporal & Multi-Type Graph Filtering
      ↓
Interactive Canvas Visualization & Evidence Inspector
      ↓
Full Chain-of-Custody & Audit Traceability
```

---

## 2. Graph Data Models

### 2.1 Graph Node Model (`GraphNode`)
Nodes represent forensic entities identified in canonical records:
- **`PHONE_NUMBER`**: E.164 normalized phone numbers.
- **`EMAIL`**: Lowercase RFC-compliant email addresses.
- **`PERSON`**: Contact/Person identities explicitly extracted from evidence.
- **`ACCOUNT`**: User accounts or application handles.
- **`DEVICE`**: Physical device identifiers (IMEI, Serial).
- **`APPLICATION`**: Communication applications (WhatsApp, Signal, Telegram, SMS).

Deterministic ID Generation:
```python
node_id = f"{case_id}:{node_type}:{normalized_value.strip().lower()}"
```

### 2.2 Graph Edge Model (`GraphEdge`)
Edges represent directed communication events aggregated between entities:
- **`CALL`**: Phone calls (Duration, call status preserved).
- **`SMS` / `MMS`**: Short messaging service events.
- **`MESSAGE`**: Instant messaging (WhatsApp, Signal, etc.).
- **`EMAIL`**: Electronic mail exchanges.
- **`OTHER_COMMUNICATION`**: Contact links and peripheral channels.

Deterministic ID Generation:
```python
edge_id = f"{case_id}:{source_id}->{target_id}:{edge_type}"
```
Attributes:
- `weight`: Measurable interaction count (number of calls, messages, etc.).
- `timestamps`: List of ISO-8601 timestamps when interactions occurred.
- `first_seen` / `last_seen`: Temporal envelope of the communication channel.
- `source_artifact_ids`: List of UUIDs pointing directly to canonical evidence records.
- `metadata`: Communication-specific metrics (e.g., total call duration in seconds).

---

## 3. Mathematical Metrics & Topological Measures

All centrality measures and graph metrics are computed using NetworkX over verified case data.

| Metric | Mathematical Description | Forensic Interpretation Standard |
| :--- | :--- | :--- |
| **Degree** | $k_i = \sum_{j} A_{ij}$ | Number of distinct entities directly connected to the node. |
| **In-Degree** | $k_i^{in} = \sum_{j} A_{ji}$ | Number of distinct incoming communication sources. |
| **Out-Degree** | $k_i^{out} = \sum_{j} A_{ij}$ | Number of distinct outgoing communication destinations. |
| **Weighted Degree** | $s_i = \sum_{j} w_{ij}$ | Total interaction volume (call count + message count). |
| **Betweenness Centrality** | $C_B(v) = \sum_{s \neq v \neq t} \frac{\sigma_{st}(v)}{\sigma_{st}}$ | Proportion of shortest topological paths passing through node $v$ (communication bridge). |
| **Closeness Centrality** | $C_C(v) = \frac{N - 1}{\sum_{u \neq v} d(v, u)}$ | Inverse sum of shortest distances to all reachable entities. |
| **PageRank** | $\mathbf{p} = \alpha \mathbf{A D}^{-1} \mathbf{p} + \frac{1-\alpha}{N}\mathbf{1}$ | Structural centrality based on recursive link prestige. |

---

## 4. Community Detection & Partitioning

Community structures are detected using the Louvain modularity-maximization algorithm (`networkx.algorithms.community.louvain_communities`):
$$Q = \frac{1}{2m} \sum_{ij} \left[ A_{ij} - \frac{k_i k_j}{2m} \right] \delta(c_i, c_j)$$

- **Deterministic Seed**: Fixed `random_state=42` to ensure 100% reproducible cluster partitions.
- **Fallback**: Greedy Modularity Partitioning if Louvain conditions are unfulfilled.
- **Partition Tagging**: Every node is assigned a zero-indexed `community_id` and structural color grouping.

---

## 5. Security, Case Isolation & Large-Data Safeguards

1. **Cross-Case Isolation**: All graph generation, querying, metric calculation, and snapshot retrieval enforces `case_id` filtering at the SQL and graph layers. Nodes and edges from Case A cannot be queried or rendered in Case B.
2. **Resource Throttling**:
   - `GRAPH_MAX_NODES = 5000`
   - `GRAPH_MAX_EDGES = 20000`
   - `GRAPH_MAX_DEPTH_LIMIT = 4`
   - `GRAPH_DEFAULT_MAX_DEPTH = 2`
3. **Audit Logging**: Every graph query, snapshot creation, and metric execution triggers an immutable audit log entry with SHA-256 verifiable parameters.

---

## 6. Forensic Safety & Non-Speculative Policy

> [!IMPORTANT]
> **Strict Forensic Standards**:
> - Centrality scores and community clusters are **topological indicators only**.
> - The system strictly prohibits automated suspect ranking, criminal profiling, guilt inference, or conspiracy claims.
> - High betweenness signifies a communication broker/bridge in the dataset, not criminal leadership.
> - Weight represents purely recorded interaction count, never "trust" or "threat".

---

## 7. API Reference

- `GET /api/v1/cases/{case_id}/graph`: Baseline communication graph.
- `POST /api/v1/cases/{case_id}/graph/query`: Parameterized query (filters, depth, center node).
- `POST /api/v1/cases/{case_id}/graph/metrics`: Compute specific centrality measures.
- `POST /api/v1/cases/{case_id}/graph/communities`: Execute community detection.
- `GET /api/v1/cases/{case_id}/graph/snapshots`: List reproducible graph snapshots.
- `POST /api/v1/cases/{case_id}/graph/snapshots`: Create snapshot of current graph state.
- `GET /api/v1/cases/{case_id}/graph/snapshots/{snapshot_id}`: Retrieve exact historical snapshot.
