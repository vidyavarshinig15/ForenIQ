# Phase 15 — Intelligent Forensic Report Generation, Evidence Citation & Export

## 1. Executive Summary & Objective
Phase 15 delivers a court-ready, evidence-grounded **Forensic Report Generation Engine** for the AI-Driven Intelligent UFDR Analysis System. It synthesizes verified outputs across the forensic investigation lifecycle:
- **Evidence Ingestion & Canonical Records** (Phases 3–7)
- **Forensic Search & Semantic Retrieval** (Phases 9–10)
- **Natural Language Query Engine & RAG Grounding** (Phases 11–12)
- **Communication Graph & Social Network Analytics** (Phase 13)
- **Unified Forensic Timeline & Statistical Anomaly Detection** (Phase 14)

The engine enforces strict referential integrity, deterministic citation verification, tamper-evident SHA-256 digital hashing, incremental document versioning, human review approval workflows, and multi-format court export (PDF, JSON, CSV).

---

## 2. Forensic Safety & Ethical Boundaries (Non-Negotiable)
In strict compliance with forensic science standards:
- ❌ **No Determination of Guilt or Innocence:** The report generator never determines guilt, innocence, criminal intent, or conspiracy.
- ❌ **No Subjective Risk Scoring:** Anomaly scores and graph centrality metrics are never converted into suspect rankings or criminal probability.
- ❌ **Zero Hallucination Tolerance:** Language models are strictly barred from independently querying databases or inventing facts. All narrative statements must map to verified citations.
- ❌ **Preservation of Uncertainty & Conflicts:** Conflicting evidence timestamps and missing sources are explicitly surfaced rather than concealed.

---

## 3. Architecture & Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    Forensic Case Database                    │
│ (Canonical Artifacts, Graph Snapshots, Anomalies, Custody)   │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                 Forensic Report Service                      │
│ • Case Scoping & RBAC Verification                           │
│ • Section Modular Ingestion & Synthesis                      │
│ • Evidence Inventory & Custody Chain Compilation             │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                  Evidence Citation Engine                    │
│ • Deterministic Citation ID Allocation (CIT-001... CIT-N)    │
│ • DB Referential Validation (Rejects Fake/Unscoped IDs)      │
│ • Provenance Linking (Finding -> Citation -> Canonical Rec)  │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                  Forensic Export Service                     │
│ • SHA-256 Digest Calculation over Normalized Content         │
│ • ReportLab PDF Layout Engine (Page Budgeting & Wrapping)    │
│ • Machine-Readable JSON & Tabular CSV Exporters              │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│             Human Review & Versioning Lifecycle              │
│    DRAFT (v1) ──> REVIEW_REQUIRED ──> APPROVED ──> EXPORTED  │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Report Taxonomy & Types
The system provides specialized templates according to investigative needs:

| Report Type | Target Scope & Inclusions |
|---|---|
| `CASE_SUMMARY` | Case metadata, evidence overview, high-level summary, methodology, limitations. |
| `EVIDENCE_SUMMARY` | Exhaustive evidence inventory, SHA-256 container hashes, chain of custody ledger. |
| `TIMELINE_REPORT` | Multi-source chronological timeline with per-event citation references and actor mappings. |
| `COMMUNICATION_ANALYSIS_REPORT` | Network topology, node/edge counts, density, community partitions, top degree nodes. |
| `ANOMALY_ANALYSIS_REPORT` | Statistical deviations, Isolation Forest outlier scores, window observed vs baseline rates. |
| `INVESTIGATION_QUERY_REPORT` | Natural language queries, parsed entities, temporal constraints, RAG answers with citations. |
| `COMPREHENSIVE_FORENSIC_ANALYSIS_REPORT` | Full aggregate forensic dossier uniting all 14 previous phases into a unified document. |

---

## 5. Evidence Citation & Validation Engine
Every finding and timeline entry in the report references a structured `EvidenceCitation`:
```json
{
  "citation_id": "CIT-001",
  "evidence_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "evidence_number": "EVD-3FA85F64",
  "record_identifier": "CALL-101",
  "source_file": "calls.ufdr",
  "timestamp": "2026-09-15T14:32:00Z",
  "summary": "Incoming call record from unknown party"
}
```

### Referential Integrity Rules:
1. **Case Boundary Scoping:** The referenced evidence must belong to the active case.
2. **Record Existence:** The referenced evidence ID and artifact ID must actively exist in the database.
3. **Automated Rejection:** Any report containing unverified or fabricated citation references is immediately flagged with `REFERENTIAL_INTEGRITY_VIOLATION` and rejected.

---

## 6. Document Versioning & Tamper-Evident SHA-256 Signatures
- **Incremental Versioning:** Modifying analyst notes or parameters creates an immutable incremented revision (`v1` -> `v2`).
- **Cryptographic Digest:** Each finalized report computes a deterministic SHA-256 digest over normalized, sorted JSON fields (`report_sha256_hash`), enabling independent verification by court officers.

---

## 7. Export Engines
1. **PDF Generation (`ReportLab`):**
   - Professional cover/title block with case and investigator metadata.
   - Dynamic page numbering (`Page X of Y`).
   - Auto-wrapping tabular layouts for evidence, custody, timelines, and anomalies.
   - Distinct status watermarks (`DRAFT`, `APPROVED`).
2. **Machine-Readable JSON:**
   - Retains full structured schema, citation graph, reproducibility manifests, and configuration parameters.
3. **Tabular CSV:**
   - Exports chronological timeline events for cross-platform spreadsheet and external timeline tool ingestion.

---

## 8. Asynchronous Background Jobs for Large Extractions
For large case extractions (10,000+ artifacts):
- The `ReportJobManager` provides background thread generation (`QUEUED` -> `GENERATING` -> `COMPLETED`).
- Non-blocking polling API endpoints (`/api/v1/cases/{case_id}/reports/jobs/{job_id}`).
