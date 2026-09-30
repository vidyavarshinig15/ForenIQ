# AI-Driven Intelligent UFDR Analysis System
## Canonical Forensic Data Model & Storage Schema

**Document Version:** 1.2.0  
**Current Phase:** Phase 2 — Authentication, RBAC & Case Management  
**Status:** Active Relational Models & Canonical Specification  

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

---

## 3. Canonical Evidence Model (CEM - Phase 3 Planned)

Planned schema for individual extracted and normalized evidence records:
* `evidence_id`: Primary record UUID
* `case_id`: Foreign key to `cases(id)`
* `evidence_source_id`: Source UFDR archive reference
* `artifact_type`: `CALL_RECORD`, `MESSAGE`, `CONTACT`, `LOCATION_RECORD`, `BROWSER_HISTORY`
* `timestamp_utc`: Normalized ISO 8601 UTC timestamp
* `sender_ref`: Phone number, email, or messaging account ID
* `primary_receiver_ref`: Destination entity
* `sha256_hash`: Cryptographic digest of extracted item
* `raw_document_id`: Pointer to MongoDB raw payload
