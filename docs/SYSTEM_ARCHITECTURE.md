# AI-Driven Intelligent UFDR Analysis System — Comprehensive System Architecture

## 1. High-Level System Architecture & Component Topology

```mermaid
graph TD
    Client[Browser / Investigator UI (React + Vite + Tailwind)] -->|HTTPS / REST API / WSS| NGINX[Reverse Proxy / API Gateway]
    NGINX -->|Forward API Traffic| FastAPI[FastAPI Backend Core Server]
    
    subgraph Core Pipeline & Security Layer
        FastAPI --> Auth[RBAC & JWT Authentication Guard]
        FastAPI --> Ingestion[Streaming Evidence Ingestion Engine]
        FastAPI --> Normalizer[Canonical Normalization Engine]
        FastAPI --> SearchEngine[Forensic Hybrid Search Service]
        FastAPI --> NLP[Investigation Query NLP & Query Planner]
        FastAPI --> RAG[Evidence-Grounded RAG Assistant]
        FastAPI --> GraphEngine[SNA & Communication Graph Analytics]
        FastAPI --> AnomalyEngine[Temporal Pattern & Anomaly Detection]
        FastAPI --> ReportEngine[Structured Forensic Report & PDF Exporter]
    end

    subgraph Asynchronous Task Infrastructure
        FastAPI -->|Enqueue Jobs| Redis[(Redis Job Queue)]
        Redis --> ParserWorker[Streaming XML Ingestion Worker]
        Redis --> NormWorker[Deterministic Normalization Worker]
        Redis --> EmbedWorker[Sentence-BERT Embedding Worker]
    end

    subgraph Data & Storage Layer
        FastAPI --> Postgres[(PostgreSQL Database / SQLite)]
        FastAPI --> FAISS[(FAISS Vector Index)]
        FastAPI --> FileStore[(Immutable Evidence Storage)]
    end
```

---

## 2. Forensic Ingestion & Processing Pipeline

```
+---------------------------+
| Physical / Logical UFDR   |
| (Encrypted or Raw ZIP)    |
+-------------+-------------+
              |
              v (Streaming SHA-256 Checksum Calculation)
+-------------+-------------+
| Immutable Evidence Vault  | ---> (Chain-of-Custody Genesis Event Created)
+-------------+-------------+
              |
              v (Bounded Archive Inspection & Zip-Slip Traversal Verification)
+-------------+-------------+
| XML Streaming Parser      | ---> (RawArtifact Storage: CALL, MESSAGE, CONTACT, LOCATION, BROWSER)
+-------------+-------------+
              |
              v (Asynchronous Deterministic Normalization)
+-------------+-------------+
| Canonical Normalization   | ---> (Standardized Timestamps, E.164 Identity Resolution, SHA-256 Record ID)
+-------------+-------------+
              |
              +-----------------------------------+-----------------------------------+
              |                                   |                                   |
              v                                   v                                   v
+-------------+-------------+       +-------------+-------------+       +-------------+-------------+
| Relational Database       |       | FAISS Dense Vector Index  |       | NetworkX Graph Analytics  |
| (SQL / Metadata / Filters)|       | (384-dim Embeddings)      |       | (Nodes, Edges, Metrics)   |
+---------------------------+       +---------------------------+       +---------------------------+
```

---

## 3. Hybrid Search & Natural Language Investigation Architecture

```
                                  [Investigator NLP Query]
                                              |
                                              v
                              +---------------+---------------+
                              |    NLP Query Normalizer       |
                              +---------------+---------------+
                                              |
                     +------------------------+------------------------+
                     |                                                 |
                     v                                                 v
    +----------------+----------------+               +----------------+----------------+
    | Intent Classification (Rule+ML) |               | Named Entity Extraction (spaCy) |
    +----------------+----------------+               +----------------+----------------+
                     |                                                 |
                     +------------------------+------------------------+
                                              |
                                              v
                              +---------------+---------------+
                              | Dynamic Query Plan Generator  |
                              +---------------+---------------+
                                              |
                     +------------------------+------------------------+
                     | (Exact / Lexical Filter)                         | (Dense Semantic Vector)
                     v                                                 v
    +----------------+----------------+               +----------------+----------------+
    | PostgreSQL BM25 / SQL ILIKE     |               | FAISS Inner-Product Retrieval   |
    +----------------+----------------+               +----------------+----------------+
                     |                                                 |
                     +------------------------+------------------------+
                                              |
                                              v
                              +---------------+---------------+
                              | Forensic Reciprocal Rank Fusion|
                              +---------------+---------------+
                                              |
                                              v
                              +---------------+---------------+
                              | Grounded RAG Generation Engine|
                              +---------------+---------------+
```

---

## 4. Multi-Layer Security & Cross-Case Isolation Boundaries

1. **Authentication & Session Security**:
   - Access tokens signed via HS256 / RS256 with cryptographically randomized secrets.
   - Strict password hashing via `bcrypt` / `Argon2id` (work factor >= 12).
   - Zero-trust token invalidation and strict role-based capability matrices (ADMIN, INVESTIGATOR, ANALYST, VIEWER).

2. **Case Data Isolation & IDOR Protection**:
   - Every SQL query, FAISS vector index partition, NetworkX graph extraction, and audit stream is explicitly scoped by `case_id`.
   - Cross-case access attempts without active case membership trigger immediate `403 Forbidden` / `404 Not Found` exceptions and are recorded in the audit log.

3. **Archive Extraction & Ingestion Hardening**:
   - Prevention of directory traversal (`Zip-Slip`) by strictly validating uncompressed target paths against safe isolation sandboxes.
   - Archive expansion ratios are bounded to prevent decompression bombs.

4. **Forensic Integrity Guardrails**:
   - Original UFDR evidence files are set to read-only permissions and cryptographically hashed with SHA-256 upon reception.
   - Exported reports (PDF, JSON) embed immutable cryptographic digests enabling third-party courtroom validation.
