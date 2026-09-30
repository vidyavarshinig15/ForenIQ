# AI-Driven Intelligent UFDR Analysis System
## Architecture Specification Document

**Document Version:** 1.2.0  
**Current Phase:** Phase 2 — Authentication, RBAC & Case Management  
**Status:** Active Implementation  

---

## 1. System Implementation Status Matrix

The platform tracks components implemented across completed phases versus future scheduled modules.

| Subsystem / Layer | Component | Status | Phase Implementation Details |
| :--- | :--- | :--- | :--- |
| **API Perimeter** | FastAPI Entrypoint & Lifecycle | **Implemented (Phase 1)** | `backend/app/main.py` with lifespan hooks. |
| **API Perimeter** | API Versioning (`/api/v1`) | **Implemented (Phase 1)** | `backend/app/api/v1/router.py`. |
| **API Perimeter** | Health Check (`/api/v1/health`) | **Implemented (Phase 1)** | `backend/app/api/v1/endpoints/health.py`. |
| **API Perimeter** | Security Headers Middleware | **Implemented (Phase 1)** | `backend/app/core/security.py` (nosniff, DENY, no-store). |
| **API Perimeter** | Safe CORS Middleware | **Implemented (Phase 1)** | Environment-driven whitelist in `core/config.py`. |
| **Security & Auth** | Argon2id Password Hashing | **Implemented (Phase 2)** | `backend/app/core/security.py` (memory=64MB, t=3, p=2). |
| **Security & Auth** | Cryptographic JWT Tokens | **Implemented (Phase 2)** | HS256/RS256 short-lived access tokens with subject UUIDs. |
| **Security & Auth** | Brute-Force Rate Limiter | **Implemented (Phase 2)** | `LoginRateLimiter` throttling after 5 consecutive failures. |
| **Security & Auth** | RBAC Architecture | **Implemented (Phase 2)** | Roles: `ADMIN`, `INVESTIGATOR`, `ANALYST`, `VIEWER`. |
| **Case Management** | Case Lifecycle & Storage | **Implemented (Phase 2)** | `Case` model with unique numbering (`CASE-YYYY-XXXXXX`). |
| **Case Management** | Dual-Tier Authorization | **Implemented (Phase 2)** | Case-scoping boundary preventing IDOR (`verify_case_access`). |
| **Case Management** | Case Membership Roles | **Implemented (Phase 2)** | `CaseMember` (`LEAD`, `CONTRIBUTOR`, `ANALYST`, `VIEWER`). |
| **Audit Engine** | Tamper-Evident Audit Trail | **Implemented (Phase 2)** | Append-only `AuditLog` for auth and case operations. |
| **Database** | Relational Schema & Alembic | **Implemented (Phase 2)** | Async SQLAlchemy 2.0 with migrations for users, cases, audit. |
| **Frontend Shell** | React Workstation Shell | **Implemented (Phase 1-2)**| AuthContext, Protected Routes, Login view, Case Manager. |
| **Evidence Engine** | UFDR Streaming Ingestion | *Planned (Phase 3)* | Multipart upload, in-flight SHA-256 calculation. |
| **Evidence Engine** | Modular XML/Artifact Parsers | *Planned (Phase 3)* | Iterative parsing, ZipSlip and XXE defense. |
| **Database** | MongoDB Document Store | *Planned (Phase 3)* | Polymorphic raw artifact JSON/XML storage. |
| **Worker Cluster** | Redis Task Broker & Workers | *Planned (Phase 3)* | Celery / ARQ background processing cluster. |
| **Search Subsystem** | Inverted Full-Text & Exact Search| *Planned (Phase 4)* | OpenSearch / Postgres inverted index. |
| **Search Subsystem** | Semantic Vector Index | *Planned (Phase 4)* | Sentence-BERT chunk embeddings + FAISS. |
| **Analytics Engine** | Unified Chronological Timeline | *Planned (Phase 4)* | Multi-source event temporal aggregation. |
| **Analytics Engine** | Communication Interaction Graph | *Planned (Phase 5)* | NetworkX entity graphs, centrality & communities. |
| **Analytics Engine** | Statistical Anomaly Detection | *Planned (Phase 5)* | Scikit-Learn Isolation Forest outlier scoring. |
| **Workspace** | Investigator Workspace | *Planned (Phase 5)* | Bookmarking, tagging, and formal hypothesis logs. |
| **AI / RAG Subsystem**| Grounded LLM Provider Engine | *Planned (Phase 6)* | Evidence-grounded answers with mandatory citations. |
| **Reporting Engine**| Court-Ready Forensic Reporting | *Planned (Phase 6)* | PDF/HTML structured forensic report generation. |

---

## 2. High-Level System Architecture

```
                              ┌──────────────────────────────────────────────┐
                              │           INVESTIGATOR WORKSPACE             │
                              │    (React SPA: High-Density UI Workstation)  │
                              │  - Auth Protected Routes   - Case Management │
                              └──────────────────────┬───────────────────────┘
                                                     │ HTTPS (Bearer JWT)
                                                     ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 API GATEWAY & SECURITY PERIMETER [Phase 1-2]                           │
│  - Security Headers Middleware    - Environment-Driven CORS    - JWT Token & RBAC Authorization Gate   │
└────────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                     │
                                                     ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     FASTAPI APPLICATION SERVICES                                       │
│  - /api/v1/auth [Phase 2]                           - /api/v1/cases [Phase 2]                          │
│  - /api/v1/audit [Phase 2]                          - /api/v1/users [Phase 2]                          │
│  - /api/v1/health [Phase 1]                         - IDOR Defense & Case Scoping [Phase 2]            │
└──────────────────┬─────────────────────────────────┬──────────────────────────────────┬────────────────┘
                   │ [Planned Phase 3]               │ [Phase 2 Implemented]            │ [Phase 2 Active]
                   ▼                                 ▼                                  ▼
        ┌─────────────────────┐          ┌───────────────────────────┐     ┌────────────────────────┐
        │   REDIS BROKER      │          │  SQLAlchemy Relational DB │     │   AUDIT LOG STORE      │
        │   - Task Queues     │          │ - Cases (Case-YYYY-XXXXXX)│     │ - Tamper-evident logs  │
        │   - Status Cache    │          │ - Users & Roles (Argon2id)│     │ - Auth & Case events   │
        └──────────┬──────────┘          │ - CaseMember Access Scopes│     │ - Append-only          │
                   │                     └─────────────┬─────────────┘     └────────────────────────┘
                   ▼                                   │
┌──────────────────────────────────────┐               │
│      EVIDENCE WORKER CLUSTER         │               │
│  - ZIP Archive Validator             │               │
│  - Streaming XML/Artifact Extractor  │               │
│  - Forensic Normalizer               │               │
│  - Integrity Hasher (SHA-256)        │               │
└──────────────────┬───────────────────┘               │
                   │                                   │
                   ├───────────────────────────────────┼───────────────────────────────────┐
                   ▼                                   ▼                                   ▼
        ┌─────────────────────┐             ┌─────────────────────┐             ┌─────────────────────┐
        │   MONGODB (DOCS)    │             │   SEARCH ENGINE     │             │    VECTOR STORE     │
        │ - Raw Artifact Pay- │             │ - Full-Text Search  │             │ - Sentence-BERT     │
        │   loads             │             │ - Exact / Filter    │             │   Embeddings        │
        │ - Semi-structured   │             │ - Faceted Querying  │             │ - Semantic Index    │
        │   app messages      │             │   (OpenSearch)      │             │   (FAISS / Qdrant)  │
        └─────────────────────┘             └─────────────────────┘             └─────────────────────┘
```

---

## 3. Phase 2 Component Details

### 3.1 Authentication Subsystem
* **Password Hashing:** `Argon2id` via `argon2-cffi` configured with 64 MB memory cost, 3 iterations, 2 lanes, salt length 16 bytes.
* **Token Issuance:** Short-lived cryptographic JWT tokens embedding the subject UUID and system role.
* **Brute-Force Defense:** `LoginRateLimiter` enforces account lockouts after 5 consecutive failed authentication attempts.
* **Bootstrap Administrator:** Seeded automatically on startup using environment variables (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`).

### 3.2 Dual-Tier Authorization & IDOR Protection
* **Tier 1 (System RBAC):** `ADMIN`, `INVESTIGATOR`, `ANALYST`, `VIEWER` roles enforced via FastAPI dependency `require_role`.
* **Tier 2 (Case-Level Scoping):** All case-related operations require explicit case membership (`CaseMember`) or administrative rights.
* **IDOR Prevention:** Unauthorized requests to `/cases/{case_id}` are rejected without disclosing whether the targeted case exists.
* **Database Query Scoping:** Non-administrative case listings execute an inner join against `case_members`, preventing memory-level filtering leaks.

### 3.3 Case Management Engine
* **Controlled Status Lifecycle:** Strict state transitions (`OPEN`, `IN_PROGRESS`, `CLOSED`, `ARCHIVED`). Closing a case automatically records the `closed_at` timestamp.
* **Non-Destructive Archiving:** Cases cannot be hard-deleted through the UI; archiving preserves records and audit trails.
* **Membership Governance:** Case Leads and Administrators can assign investigators, analysts, or viewers to specific cases.

### 3.4 Forensic Audit Subsystem
* Records security-critical events: `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT`, `USER_CREATE`, `CASE_CREATE`, `CASE_UPDATE`, `CASE_MEMBER_ADD`, `CASE_MEMBER_UPDATE`, `CASE_MEMBER_REMOVE`, `UNAUTHORIZED_ACCESS`.
* Masks credentials and raw payload contents automatically.
