# AI-Driven Intelligent UFDR Analysis System
## Canonical Forensic Data Model & Storage Schema

**Document Version:** 1.3.0  
**Current Phase:** Phase 3 — Secure Forensic Evidence Ingestion & Upload  
**Status:** Active Relational Models (Cases, Users, Memberships, Audit, Evidence)  


---

## 1. Storage Architecture Overview

The platform uses a polyglot persistence architecture separating structured relational governance, dynamic document artifact extraction, and high-dimensional semantic search:

```
┌─────────────────────────────────┐
│     SQLAlchemy Relational DB    │  Cases, Users (RBAC), Case Memberships (Scoping),
│    [Phase 2 - Implemented]      │  and Append-Only Audit Logs.
└────────────────┬────────────────┘
                 │
┌────────────────┴────────────────┐
│      MongoDB Document Store     │  Polymorphic raw artifact dumps, unnormalized app
│     [Phase 3 - Scheduled]       │  blobs (WhatsApp, Telegram, Location Fixes).
└────────────────┬────────────────┘
                 │
┌────────────────┴────────────────┐
│   Search & Vector Subsystems    │  OpenSearch / PostgreSQL inverted full-text index
│     [Phase 4 - Scheduled]       │  and Sentence-BERT chunk embeddings (FAISS).
└─────────────────────────────────┘
```

---

## 2. Active Relational Models (Phase 2 Implemented)

### 2.1 Users (`users`)
Stores authenticated investigator accounts and their system-level RBAC role.
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL, -- Argon2id hash
    role VARCHAR(32) NOT NULL,           -- ADMIN, INVESTIGATOR, ANALYST, VIEWER
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_login_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX ix_users_email ON users(email);
```

### 2.2 Cases (`cases`)
The primary organizational boundary for digital evidence and investigative scope.
```sql
CREATE TABLE cases (
    id UUID PRIMARY KEY,
    case_number VARCHAR(100) UNIQUE NOT NULL, -- CASE-YYYY-XXXXXX
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN', -- OPEN, IN_PROGRESS, CLOSED, ARCHIVED
    created_by UUID REFERENCES users(id) ON DELETE RESTRICT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    closed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX ix_cases_case_number ON cases(case_number);
```

### 2.3 Case Memberships (`case_members`)
Explicit dual-tier authorization scoping linking users to cases.
```sql
CREATE TABLE case_members (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    access_role VARCHAR(32) NOT NULL DEFAULT 'CONTRIBUTOR', -- LEAD, CONTRIBUTOR, ANALYST, VIEWER
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE RESTRICT NOT NULL,
    CONSTRAINT uq_case_user_member UNIQUE(case_id, user_id)
);
CREATE INDEX ix_case_members_case_id ON case_members(case_id);
CREATE INDEX ix_case_members_user_id ON case_members(user_id);
```

### 2.4 Audit Trail (`audit_logs`)
Append-only forensic audit trail capturing security and case-level operations.
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,          -- LOGIN_SUCCESS, CASE_CREATE, etc.
    resource_type VARCHAR(100) NOT NULL,   -- AUTH, CASE, CASE_MEMBER, USER
    resource_id VARCHAR(255),
    case_id UUID REFERENCES cases(id) ON DELETE SET NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) NOT NULL,           -- SUCCESS, FAILED, LOCKED_OUT, DENIED
    details_json TEXT,                     -- Sanitized structured attributes
    client_ip VARCHAR(100)
);
CREATE INDEX ix_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX ix_audit_logs_action ON audit_logs(action);
CREATE INDEX ix_audit_logs_case_id ON audit_logs(case_id);
CREATE INDEX ix_audit_logs_user_id ON audit_logs(user_id);
```

### 2.5 Evidence Records (`evidence`)
Tracks uploaded forensic UFDR archives, provenance metadata, in-flight SHA-256 hashes, cryptographic integrity state, and ingestion status.
```sql
CREATE TABLE evidence (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    storage_path_or_key VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(127) NOT NULL,
    detected_mime_type VARCHAR(127),
    file_extension VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'UPLOADED', -- UPLOADING, UPLOADED, VALIDATING, VALID, INVALID, FAILED, QUARANTINED
    sha256_hash VARCHAR(64) NOT NULL,
    integrity_status VARCHAR(32) NOT NULL DEFAULT 'VALID', -- UNKNOWN, VALID, MISMATCH, MISSING, ERROR
    last_integrity_check_at TIMESTAMP WITH TIME ZONE,
    uploaded_by UUID REFERENCES users(id) ON DELETE RESTRICT NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX ix_evidence_case_id ON evidence(case_id);
CREATE INDEX ix_evidence_status ON evidence(status);
CREATE INDEX ix_evidence_integrity_status ON evidence(integrity_status);
CREATE INDEX ix_evidence_uploaded_by ON evidence(uploaded_by);
CREATE INDEX ix_evidence_uploaded_at ON evidence(uploaded_at);
CREATE INDEX ix_evidence_sha256_hash ON evidence(sha256_hash);
```

### 2.6 Evidence Chain of Custody Events (`evidence_custody_events`)
Append-only, cryptographically linked lifecycle history tracking every custody change for ingested evidence.
```sql
CREATE TABLE evidence_custody_events (
    id UUID PRIMARY KEY,
    evidence_id UUID REFERENCES evidence(id) ON DELETE CASCADE NOT NULL,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE NOT NULL,
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL, -- EVIDENCE_UPLOADED, EVIDENCE_HASHED, INTEGRITY_VERIFIED, etc.
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    sequence_number INTEGER NOT NULL,
    previous_event_id UUID REFERENCES evidence_custody_events(id) ON DELETE SET NULL,
    previous_event_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL,
    metadata_json TEXT
);
CREATE INDEX ix_custody_evidence_sequence ON evidence_custody_events(evidence_id, sequence_number);
CREATE INDEX ix_evidence_custody_events_evidence_id ON evidence_custody_events(evidence_id);
CREATE INDEX ix_evidence_custody_events_case_id ON evidence_custody_events(case_id);
CREATE INDEX ix_evidence_custody_events_actor_user_id ON evidence_custody_events(actor_user_id);
CREATE INDEX ix_evidence_custody_events_timestamp ON evidence_custody_events(timestamp);
CREATE INDEX ix_evidence_custody_events_event_type ON evidence_custody_events(event_type);
CREATE INDEX ix_evidence_custody_events_event_hash ON evidence_custody_events(event_hash);
```

### 2.7 Forensic Processing Jobs (`processing_jobs`)
Tracks asynchronous ingestion and artifact parsing execution across evidence packages.
```sql
CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE NOT NULL,
    evidence_id UUID REFERENCES evidence(id) ON DELETE CASCADE NOT NULL,
    job_type VARCHAR(32) NOT NULL, -- UFDR_PARSE, NORMALIZATION, INDEXING, EMBEDDING, ANALYSIS, REPORT_GENERATION
    status VARCHAR(32) NOT NULL,   -- QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
    progress INTEGER NOT NULL DEFAULT 0,
    files_total INTEGER NOT NULL DEFAULT 0,
    files_processed INTEGER NOT NULL DEFAULT 0,
    artifacts_total INTEGER NOT NULL DEFAULT 0,
    warnings_count INTEGER NOT NULL DEFAULT 0,
    errors_count INTEGER NOT NULL DEFAULT 0,
    summary_json JSON,
    error_message TEXT,
    created_by UUID REFERENCES users(id) ON DELETE RESTRICT NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX ix_processing_jobs_case_evidence ON processing_jobs(case_id, evidence_id);
CREATE INDEX ix_processing_jobs_status_type ON processing_jobs(status, job_type);
CREATE INDEX ix_processing_jobs_case_id ON processing_jobs(case_id);
CREATE INDEX ix_processing_jobs_evidence_id ON processing_jobs(evidence_id);
CREATE INDEX ix_processing_jobs_created_at ON processing_jobs(created_at);
```

### 2.8 Raw Parsed Forensic Artifacts (`raw_artifacts`)
Stores raw structured artifacts extracted from UFDR containers, preserving full source provenance for downstream AI grounding and verification.
```sql
CREATE TABLE raw_artifacts (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE NOT NULL,
    evidence_id UUID REFERENCES evidence(id) ON DELETE CASCADE NOT NULL,
    processing_job_id UUID REFERENCES processing_jobs(id) ON DELETE CASCADE NOT NULL,
    artifact_type VARCHAR(32) NOT NULL, -- CALL, MESSAGE, CONTACT, LOCATION, BROWSER, APPLICATION, FILESYSTEM
    source_file VARCHAR(255) NOT NULL,
    source_path TEXT NOT NULL,
    record_identifier VARCHAR(255) NOT NULL,
    raw_data JSON NOT NULL,
    parsed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX ix_raw_artifacts_case_evidence_type ON raw_artifacts(case_id, evidence_id, artifact_type);
CREATE INDEX ix_raw_artifacts_job_type ON raw_artifacts(processing_job_id, artifact_type);
CREATE INDEX ix_raw_artifacts_evidence_source ON raw_artifacts(evidence_id, source_file);
CREATE INDEX ix_raw_artifacts_traceability ON raw_artifacts(evidence_id, record_identifier);
CREATE INDEX ix_raw_artifacts_record_identifier ON raw_artifacts(record_identifier);
CREATE INDEX ix_raw_artifacts_artifact_type ON raw_artifacts(artifact_type);
CREATE INDEX ix_raw_artifacts_created_at ON raw_artifacts(created_at);
```

### 2.9 Canonical Forensic Evidence Records (`canonical_evidence`)
Stores standardized, normalized forensic records transformed from `raw_artifacts` with explicit timestamp precision, extracted entity references, structured metadata, and strict quality auditing.

```sql
CREATE TABLE canonical_evidence (
    id CHAR(32) PRIMARY KEY, -- Deterministic UUIDv5
    case_id CHAR(32) REFERENCES cases(id) ON DELETE CASCADE NOT NULL,
    evidence_id CHAR(32) REFERENCES evidence(id) ON DELETE CASCADE NOT NULL,
    raw_artifact_id CHAR(32) REFERENCES raw_artifacts(id) ON DELETE CASCADE NOT NULL,
    processing_job_id CHAR(32) REFERENCES processing_jobs(id) ON DELETE SET NULL,
    artifact_type VARCHAR(32) NOT NULL, -- CALL, MESSAGE, CONTACT, LOCATION, BROWSER, APPLICATION, FILE_SYSTEM, GENERIC
    canonical_fingerprint VARCHAR(64) NOT NULL, -- SHA-256 digest
    source_file VARCHAR(255) NOT NULL,
    source_path TEXT NOT NULL,
    record_identifier VARCHAR(255) NOT NULL,
    event_timestamp TIMESTAMP WITH TIME ZONE,
    timestamp_precision VARCHAR(16) NOT NULL, -- SECOND, MILLISECOND, MINUTE, HOUR, DAY, MONTH, YEAR, UNKNOWN
    timestamp_status VARCHAR(16) NOT NULL, -- VALID, ESTIMATED, UNCERTAIN, MISSING, INVALID
    original_timestamp TEXT,
    original_timezone VARCHAR(64),
    device_id VARCHAR(128),
    application VARCHAR(128),
    original_application VARCHAR(128),
    content TEXT,
    entities JSON NOT NULL, -- Array of EntityReference { entity_type, entity_value, normalized_value, role }
    metadata JSON NOT NULL, -- Strongly-typed domain metadata
    data_quality_status VARCHAR(16) NOT NULL, -- VALID, PARTIAL, INVALID
    validation_warnings JSON NOT NULL, -- Array of ValidationWarning { field, code, message, severity }
    parser_version VARCHAR(32) NOT NULL,
    normalizer_version VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_canonical_evidence_identity UNIQUE (evidence_id, canonical_fingerprint),
    CONSTRAINT uq_canonical_evidence_raw_artifact UNIQUE (raw_artifact_id)
);
CREATE INDEX ix_canonical_evidence_case_id ON canonical_evidence(case_id);
CREATE INDEX ix_canonical_evidence_evidence_id ON canonical_evidence(evidence_id);
CREATE INDEX ix_canonical_evidence_raw_artifact_id ON canonical_evidence(raw_artifact_id);
CREATE INDEX ix_canonical_evidence_type ON canonical_evidence(artifact_type);
CREATE INDEX ix_canonical_evidence_event_timestamp ON canonical_evidence(event_timestamp);
CREATE INDEX ix_canonical_evidence_quality ON canonical_evidence(data_quality_status);
CREATE INDEX ix_canonical_evidence_app ON canonical_evidence(application);
CREATE INDEX ix_canonical_evidence_fingerprint ON canonical_evidence(canonical_fingerprint);
CREATE INDEX ix_canonical_evidence_composite_timeline ON canonical_evidence(case_id, evidence_id, artifact_type, event_timestamp);
```

---

## 3. Forensic Traceability & Pipeline Boundary Distinction

* **Phase 5 & 6:** `RawArtifact` preserves heterogeneous raw XML extractions from UFDR archives with exact provenance (`source_file`, `source_path`, `record_identifier`, `raw_data`).
* **Phase 7 (Current Implementation):** `CanonicalEvidence` standardizes all artifacts into a unified forensic model with:
  1. **Deterministic Identity:** UUIDv5 and SHA-256 canonical fingerprints guarantee repeatable IDs and idempotent persistence.
  2. **Timestamp Normalization:** Explicit precision tracking (`SECOND`, `DAY`, `YEAR`), timezone normalization to UTC, preserving verbatim `original_timestamp` without fabricating values.
  3. **Entity Normalization:** Standardized phone numbers (E.164), emails, and canonical application names stored with role definitions (`caller`, `recipient`, `visited_url`).
  4. **Strict Quality Auditing:** Validation warnings captured per record, flagging out-of-bounds coordinates or corrupt data as `INVALID` or `PARTIAL`.
  5. **Bidirectional Lineage:** Every `CanonicalEvidence` links directly to its source `raw_artifact_id` and parent `evidence_id`, queryable via `GET /cases/{case_id}/canonical-records/{record_id}/raw`.

