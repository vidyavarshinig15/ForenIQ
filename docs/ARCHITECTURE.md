# AI-Driven Intelligent UFDR Analysis System
## Architecture Specification Document

**Document Version:** 1.5.0  
**Current Phase:** Phase 5 — Scalable UFDR Ingestion & Parsing Engine  
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
| **Security & Auth** | Cryptographic JWT Tokens | **Implemented (Phase 2)** | HS256 short-lived access tokens with subject UUIDs. |
| **Security & Auth** | Brute-Force Rate Limiter | **Implemented (Phase 2)** | `LoginRateLimiter` throttling after 5 consecutive failures. |
| **Security & Auth** | RBAC Architecture | **Implemented (Phase 2)** | Roles: `ADMIN`, `INVESTIGATOR`, `ANALYST`, `VIEWER`. |
| **Case Management** | Case Lifecycle & Storage | **Implemented (Phase 2)** | `Case` model with unique numbering (`CASE-YYYY-XXXXXX`). |
| **Case Management** | Dual-Tier Authorization | **Implemented (Phase 2)** | Case-scoping boundary preventing IDOR (`verify_case_access`). |
| **Case Management** | Case Membership Roles | **Implemented (Phase 2)** | `CaseMember` (`LEAD`, `CONTRIBUTOR`, `ANALYST`, `VIEWER`). |
| **Audit Engine** | Tamper-Evident Audit Trail | **Implemented (Phase 2-5)**| Append-only `AuditLog` capturing auth, case, evidence, integrity, processing events. |
| **Database** | Relational Schema & Alembic | **Implemented (Phase 2-5)**| Async SQLAlchemy 2.0 with migrations for users, cases, evidence, custody, processing jobs, raw artifacts. |
| **Evidence Engine** | Streaming Upload & Disk Storage | **Implemented (Phase 3)** | Chunk-by-chunk zero-RAM-buffering stream in `LocalStorageService`. |
| **Evidence Engine** | In-Flight SHA-256 Hasher | **Implemented (Phase 3)** | Incremental SHA-256 digest computation during stream. |
| **Evidence Engine** | Defensive Archive Inspection | **Implemented (Phase 3)** | Magic byte check (`PK\x03\x04`), ZipSlip and ZipBomb ratio checks. |
| **Evidence Engine** | Controlled Lifecycle & Quarantine | **Implemented (Phase 3-4)**| Soft quarantine (`QUARANTINED`), immutable raw file preservation. |
| **Integrity Engine**| Streaming Storage Verification | **Implemented (Phase 4)** | `IntegrityService` on-demand 64KB block re-hashing and mismatch alerts. |
| **Custody Engine**  | Tamper-Evident Hash Chain | **Implemented (Phase 4)** | `EvidenceCustodyEvent` linked via SHA-256 event digest sequence. |
| **Frontend Shell** | Workstation & Ingestion UI | **Implemented (Phase 1-5)**| React UI with live integrity verify, custody timeline, processing pipeline, raw artifact explorer. |
| **Evidence Engine** | Scalable UFDR Parser Engine | **Implemented (Phase 5)** | Safe ZIP inspection, streaming `defusedxml` iterparse, registry architecture, 7 artifact parsers. |
| **Worker Engine**   | Asynchronous Processing Jobs | **Implemented (Phase 5)** | `ProcessingJob` async execution, real progress metrics, idempotency clean on retry, sandbox cleanup. |
| **Provenance Engine**| Raw Artifact Storage | **Implemented (Phase 5)** | `RawArtifact` retaining source file, source path, record identifier, raw JSON payload. |
| **Search Subsystem** | Inverted Full-Text & Exact Search| *Planned (Phase 6)* | PostgreSQL tsvector inverted index. |
| **Search Subsystem** | Semantic Vector Index | *Planned (Phase 6)* | Sentence-BERT chunk embeddings + FAISS. |
| **Analytics Engine** | Unified Chronological Timeline | *Planned (Phase 7)* | Multi-source event temporal aggregation. |
| **Analytics Engine** | Communication Interaction Graph | *Planned (Phase 8)* | NetworkX entity graphs, centrality & communities. |
| **Analytics Engine** | Statistical Anomaly Detection | *Planned (Phase 9)* | Scikit-Learn Isolation Forest outlier scoring. |
| **Workspace** | Investigator Workspace | *Planned (Phase 9)* | Bookmarking, tagging, and formal hypothesis logs. |
| **AI / RAG Subsystem**| Grounded LLM Provider Engine | *Planned (Phase 10)*| Evidence-grounded answers with mandatory citations. |
| **Reporting Engine**| Court-Ready Forensic Reporting | *Planned (Phase 10)*| PDF/HTML structured forensic report generation. |


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

---

## 4. Phase 3 & 4 Component Details

### 4.1 Secure Evidence Ingestion
* **Chunked Streaming Storage:** Zero-RAM buffering via `LocalStorageService.store_stream`. Streams uploaded multipart files through a temporary isolated staging area.
* **Concurrent SHA-256:** Computes cryptographic digest during disk write.
* **Archive Hardening:** Magic bytes validation (`PK\x03\x04`), ZipSlip path traversal inspection, and compression ratio heuristic.

### 4.2 Cryptographic Integrity & Chain of Custody
* **On-Demand Verification:** `IntegrityService` re-computes streaming SHA-256 over 64KB blocks and compares to the immutable baseline hash.
* **Tamper Response:** If bytes differ, marks `MISMATCH`, quarantines evidence, emits `INTEGRITY_MISMATCH` audit log and custody event.
* **Hash-Linked Chain of Custody:** `EvidenceCustodyEvent` table with SHA-256 event digest linked to `previous_event_hash`, preventing unrecorded retroactive modifications.

---

## 5. Phase 5 UFDR Ingestion & Parsing Engine

### 5.1 Modular Parser Architecture
* **Decoupled Architecture:** `backend/app/parser/` defines modular components separating container inspection, XML decoding, detection, registry dispatch, and artifact extraction.
* **UFDR Detection:** `UFDRDetector` inspects archive member catalogs and XML hierarchies rather than relying solely on file extensions.
* **Extensible Registry:** `ArtifactParserRegistry` dispatches entries to specialized parsers implementing `BaseArtifactParser`.

### 5.2 Archive & XML Security Hardening
* **ZipSlip Traversal Defense:** Member paths are canonicalized and verified to never resolve outside the temporary sandbox directory. Absolute prefixes and Windows drive letters are explicitly rejected.
* **ZipBomb & Resource Exhaustion Protection:** Configurable thresholds for maximum entries (`MAX_ARCHIVE_ENTRIES`), single entry decompressed size (`MAX_SINGLE_ENTRY_SIZE_MB`), total uncompressed size (`MAX_TOTAL_UNCOMPRESSED_SIZE_MB`), maximum compression ratio (`MAX_COMPRESSION_RATIO`), and nested archive depth (`MAX_ARCHIVE_DEPTH`).
* **XXE & Entity Expansion Defense:** Secure XML streaming via `defusedxml.ElementTree.iterparse` with immediate element clearing (`elem.clear()`, `root.clear()`), bounding memory to O(1) per record.
* **Partial Failure Tolerance:** Malformed XML records/files produce warning diagnostics rather than aborting processing of unrelated valid files.

### 5.3 Asynchronous Worker & Job Engine
* **Asynchronous Execution:** Non-blocking processing via `UFDRParserWorker` running against `ProcessingJob` lifecycle (`QUEUED` → `RUNNING` → `COMPLETED` / `FAILED` / `CANCELLED`).
* **Pre-Flight Integrity Gate:** Recalculates physical evidence SHA-256 prior to parsing. If `MISMATCH`, parsing is immediately aborted to prevent working on tampered or corrupted evidence.
* **Idempotency & Clean Reprocessing:** Reprocessing deletes prior artifacts associated with the job/evidence before re-populating, preventing duplicate records.
* **Sandbox Isolation & Cleanup:** Extracts only needed files to isolated `storage/scratch/jobs/<job-id>/` directory, guaranteed to be removed in the `finally` block.

### 5.4 Extracted Artifact Categories
1. **Calls:** Caller, receiver, phone number, direction, duration, timestamp, status.
2. **Messages:** Sender, receiver, timestamp, message content, direction, application (WhatsApp, Telegram, SMS, Signal, MMS).
3. **Contacts:** Display name, phone numbers, email addresses, accounts.
4. **Location:** Latitude, longitude, timestamp, source provider, accuracy, altitude.
5. **Browser History:** URL, page title, visit timestamp, browser identifier, visit counts.
6. **Applications:** App name, package identifier, version, event type, install/usage timestamps.
7. **Filesystem:** Paths, filenames, sizes, created/modified/access timestamps, hashes.

### 5.5 Source Traceability & Provenance
* Every parsed record in `RawArtifact` preserves:
  * `evidence_id`: Originating evidence container
  * `source_file`: Specific archive member filename
  * `source_path`: Internal archive folder path
  * `record_identifier`: Original record UID or index
  * `raw_data`: Complete structured dictionary of the original XML entry

---

## 6. Phase 6 Large-Scale Processing, Workers, Queues & Resumable Ingestion

### 6.1 Architectural Overview
Phase 6 enhances the UFDR processing architecture for massive, multi-gigabyte forensic extractions containing millions of records. The system decouples request ingestion from worker execution, enforces strict memory bounds, supports resumable checkpoints, prevents duplicate records idempotently, and guarantees high availability through heartbeat leases and automatic crash recovery.

```
                    ┌─────────────────┐
                    │  React Frontend │
                    └────────┬────────┘
                             │ HTTPS / Bearer JWT
                             ▼
                    ┌─────────────────┐
                    │  FastAPI API    │
                    │  (Port 8000)    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Job Manager   │ (Priority & IDOR Gate)
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Queue Layer   │
                    │ (Redis / DB)    │
                    └────────┬────────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
           ┌────────┐   ┌────────┐   ┌────────┐
           │Worker 1│   │Worker 2│   │Worker N│ (Bounded Concurrency)
           └───┬────┘   └───┬────┘   └───┬────┘
               │             │            │
               └─────────────┼────────────┘
                             ▼
                    ┌─────────────────┐
                    │ UFDR Processing │ (Streaming iterparse &
                    │     Engine      │  Backpressure Buffering)
                    └────────┬────────┘
                             │ Batched Inserts (ON CONFLICT DO NOTHING)
                             ▼
                    ┌─────────────────┐
                    │ Artifact Store  │
                    │    Database     │ (PostgreSQL / SQLite)
                    └─────────────────┘
```

### 6.2 Dual Queue Subsystem (`backend/app/queue/`)
* **Redis Priority Queue (`RedisJobQueue`):** Uses Redis Sorted Sets (`ZPOPMIN`) with dynamic priority scoring (`(100 - weight) * 1e10 + timestamp`) and Redis Hashes for atomic worker lease tracking. Provides sub-millisecond scheduling across workers.
* **Transactional Database Queue (`DatabaseJobQueue`):** Fallback backend using row-level locking (`SELECT ... FOR UPDATE SKIP LOCKED` on PostgreSQL; atomic CAS on SQLite) for environments without Redis.
* **Queue Factory (`get_job_queue`):** Automatic failover between Redis and the database queue.
* **Job States:** `QUEUED`, `STARTING`, `RUNNING`, `PAUSED`, `RETRYING`, `COMPLETED`, `PARTIAL`, `FAILED`, `CANCEL_REQUESTED`, `CANCELLED`.
* **Priority Enforcement:** Supports `HIGH`, `NORMAL`, and `LOW` priorities. Non-admin users are strictly throttled to `NORMAL` priority to prevent queue starvation.

### 6.3 Bounded Worker Pool & Concurrency Control
* **Configurable Concurrency:** `WORKER_CONCURRENCY` limits simultaneous execution (default: 2 for dev; scalable per available CPU/RAM).
* **Worker Isolation:** Workers run isolated loops (`WorkerPool`) without shared mutable evidence state.
* **Job Lease & Worker Heartbeats:** Active workers periodically refresh their lease (`last_heartbeat_at`, `lease_expires_at`).
* **Stale Job Reaper:** Stale or crashed workers that fail to update their heartbeat within `JOB_LEASE_TIMEOUT_SECONDS` (default: 30s) are reaped; eligible jobs transition to `RETRYING` with exponential backoff (`delay = 2.0 ** retry_count`) up to `MAX_RETRIES` (default: 3).

### 6.4 Chunked Streaming & Backpressure Buffering
* **Producer-Consumer Streaming:** `defusedxml` incremental parsing produces records into bounded batches (`PARSER_BATCH_SIZE`, default: 1000).
* **Bounded RAM Consumption:** Memory does not scale linearly with file size. Records are flushed to disk in discrete batches, clearing XML elements immediately (`elem.clear()`, `root.clear()`).
* **Controlled Transaction Boundaries:** Each batch of records is committed in its own transaction, avoiding multi-million-row locking transactions. Earlier successful batches remain committed if later files fail.

### 6.5 Checkpointing & Resumable Ingestion
* **Incremental Checkpoints:** Workers save progress (`completed_files`, `records_processed`, `files_failed`, `counts_by_type`) to `ProcessingJob.checkpoint_data`.
* **Resumption on Retry:** When a failed or cancelled job is retried, the worker reads `checkpoint_data` and skips already-completed archive members, resuming directly from the point of failure.

### 6.6 Deterministic Identity & Duplicate Prevention
* **Deterministic Fingerprints:** Every raw artifact receives a deterministic composite key:
  `evidence_id + ":" + source_file + ":" + source_path + ":" + record_identifier + ":" + artifact_type`
* **Artifact UUID & Hash:** An SHA-256 fingerprint and deterministic UUIDv5 namespace are derived.
* **Upsert / Ignore Integrity:** The database enforces a unique constraint `uq_raw_artifact_identity` on `(evidence_id, artifact_fingerprint)`. Batch inserts execute `ON CONFLICT (evidence_id, artifact_fingerprint) DO NOTHING`, ensuring at-least-once queue delivery does not produce duplicate records.

### 6.7 Resource Governance
* `WORKER_CONCURRENCY`: Limits maximum concurrent worker tasks.
* `MAX_TEMP_STORAGE_MB`: Pre-flight disk space verification before extracting archives to avoid filling the host volume.
* `PARSER_BATCH_SIZE`: Limits memory consumption per insert batch (100 to 5,000).
* `JOB_LEASE_TIMEOUT_SECONDS`: Maximum allowable duration between heartbeats before a worker is marked crashed.

### 6.8 Production Scalability Note
The current implementation is designed to operate on a single host or multi-worker cluster with Redis and PostgreSQL. True horizontal elastic scaling across container clusters (e.g. Kubernetes) requires externalizing the storage volume to an S3/Ceph object store and using a dedicated Redis Sentinel/Cluster. The architecture is intentionally decoupled to allow this transition in future deployment phases without rewriting parsing or repository logic.

## 7. Phase 7 Evidence Normalization & Canonical Forensic Data Model

### 7.1 Architecture & Ingestion Pipeline Progression
Phase 7 introduces the canonical normalization layer that sits between raw artifact extraction and downstream intelligence systems. It transforms heterogeneous, vendor-specific raw artifacts into a standardized, strongly-typed `CanonicalEvidence` data model while preserving unbroken bidirectional forensic traceability back to source raw artifacts and evidence containers.

```
Original UFDR Archive
        │
        ▼ (Cryptographic Integrity Verified: SHA-256)
UFDR Ingestion & Parser Engine (Phase 5/6)
        │
        ▼ (Streaming Chunking & Checkpoints)
Raw Artifacts Table (`raw_artifacts`)
   [raw XML payloads, vendor-specific tags]
        │
        ▼ (JobType.NORMALIZATION / Worker Pool)
Modular Normalization Pipeline (`backend/app/normalizers/`)
   ├── Timestamp Engine (ISO-8601 UTC, Precision Badges, Partial Date Detection)
   ├── Entity Extraction (E.164 Phones, Normalized Emails, App Standardizer)
   ├── Domain Normalizers (Calls, Messages, Contacts, Locations, Browser, etc.)
   └── Quality Assessment (Strict Validation, Warning Auditing, Quality Status)
        │
        ▼ (Deterministic UUIDv5 & SHA-256 Fingerprint)
Canonical Evidence Table (`canonical_evidence`)
   [Standardized timestamps, extracted entities, typed metadata, source lineage]
        │
        ▼
Future Downstream Consumers (Search, Analytics, Graph, Timeline)
```

### 7.2 Modular Normalizer Hierarchy
* **`BaseArtifactNormalizer`:** Abstract base class enforcing validation rules, warning capture, and data quality calculation (`VALID`, `PARTIAL`, `INVALID`).
* **Domain Normalizers:**
  * `CallNormalizer`: Direction (`INCOMING`, `OUTGOING`, `MISSED`), participants, duration.
  * `MessageNormalizer`: Verbatim content preservation, thread IDs, attachments, read/delivery statuses.
  * `ContactNormalizer`: Display names, normalized phone numbers, normalized email addresses, accounts.
  * `LocationNormalizer`: Strict WGS-84 coordinate validation (`lat: [-90, 90]`, `lon: [-180, 180]`), altitude, precision, provider.
  * `BrowserNormalizer`: URLs, page titles, visit counts, visit timestamps.
  * `ApplicationNormalizer`: App identifiers, canonical application names, versioning.
  * `FilesystemNormalizer`: File paths, file names, sizes, extension, hashes.
  * `GenericNormalizer`: Fallback normalizer for unhandled or vendor-custom artifact types.
* **`NormalizationRegistry`:** Dynamic registry mapping `ArtifactType` enums to specialized normalizers.

### 7.3 Canonical Identity & Idempotent Persistence
* **UUIDv5 Determinism:** Record primary keys are generated deterministically using UUIDv5 with a fixed DNS namespace:
  `UUIDv5(NAMESPACE, f"{evidence_id}:{raw_artifact_id}:{canonical_fingerprint}")`
* **Canonical Fingerprint:** SHA-256 digest over normalized properties:
  `SHA-256(f"{artifact_type}|{event_timestamp}|{source_file}|{source_path}|{record_identifier}|{json_entities}|{json_metadata}")`
* **Unique Constraints:** `uq_canonical_evidence_identity` on `(evidence_id, canonical_fingerprint)` and `uq_canonical_evidence_raw_artifact` on `raw_artifact_id`.
* **Idempotent Upsert:** Inserts execute `ON CONFLICT (evidence_id, canonical_fingerprint) DO NOTHING`, ensuring complete reruns produce 0 duplicates.


