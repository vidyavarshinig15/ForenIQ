# AI-Driven Intelligent UFDR Analysis System
## API Architecture & Route Specifications

**Document Version:** 1.0.0  
**Classification:** RESTful API Design Specification  
**Status:** Foundation Phase  

---

## 1. API Design Principles & Standard Conventions

1. **Protocol:** Strict HTTPS / TLS 1.3 in production environments.
2. **Standard Serialization:** UTF-8 encoded JSON for all data exchanges.
3. **Authentication:** Bearer JWT in `Authorization` header (`Authorization: Bearer <token>`).
4. **Idempotency:** Sensitive write operations (evidence submission, case creation) support `Idempotency-Key` headers.
5. **Deterministic Status Codes:** Strict semantic alignment with HTTP specification (200, 201, 202, 400, 401, 403, 404, 422, 500).
6. **Asynchronous Operations:** Long-running jobs (evidence processing, large report generation, graph re-indexing) return `202 Accepted` with a `job_id` resource handle.

---

## 2. Standard Response Envelopes

### 2.1 Success Envelope
```json
{
  "status": "success",
  "data": { ... },
  "meta": {
    "page": 1,
    "page_size": 50,
    "total_records": 142857,
    "timestamp_utc": "2026-09-30T16:40:00Z"
  }
}
```

### 2.2 Error Envelope
```json
{
  "status": "error",
  "error_code": "CASE_ACCESS_DENIED",
  "message": "User does not hold investigative authorization for Case #2026-0042.",
  "details": {},
  "request_id": "req-9b8f2a14-4a5c-42b7-8d99"
}
```

---

## 3. Planned Route Namespaces & Core Endpoints

### 3.1 Authentication & Profile (`/api/v1/auth`)
* `POST /api/v1/auth/login` — Authenticate credentials; return access and refresh tokens.
* `POST /api/v1/auth/refresh` — Refresh expired access token using valid refresh token.
* `POST /api/v1/auth/logout` — Revoke active token and invalidate session.
* `GET  /api/v1/auth/me` — Retrieve active user identity, system role, and accessible cases.

### 3.2 Case Management (`/api/v1/cases`)
* `GET    /api/v1/cases` — List accessible cases for authenticated user with pagination and status filters.
* `POST   /api/v1/cases` — Create a new forensic case.
* `GET    /api/v1/cases/{case_id}` — Retrieve case overview, assigned investigators, and evidence metrics.
* `PATCH  /api/v1/cases/{case_id}` — Update case title, description, or status (Open, Closed, Archived).
* `POST   /api/v1/cases/{case_id}/members` — Assign an investigator or analyst to the case.
* `DELETE /api/v1/cases/{case_id}/members/{user_id}` — Revoke case access for a member.

### 3.3 Evidence Ingestion & Management (`/api/v1/evidence`)
* `GET  /api/v1/cases/{case_id}/evidence` — List evidence files and extractions uploaded to a case.
* `POST /api/v1/cases/{case_id}/evidence/upload` — Multipart streaming upload of UFDR archive. Generates SHA-256 hash in flight and enqueues validation job.
* `GET  /api/v1/evidence/{evidence_id}` — Retrieve evidence metadata, acquisition hash, verification status, and extraction statistics.
* `POST /api/v1/evidence/{evidence_id}/process` — Trigger or resume background extraction and normalization.

### 3.4 Processing Jobs & Background Progress (`/api/v1/jobs`)
* `GET /api/v1/jobs/{job_id}` — Query execution status of an asynchronous processing job.
  * Status states: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`, `PARTIALLY_COMPLETED`.
  * Response includes percentage, processed record counter, and processing step description.
* `POST /api/v1/jobs/{job_id}/cancel` — Request graceful abort of active processing job.

### 3.5 Artifact Discovery & Provenance (`/api/v1/artifacts`)
* `GET /api/v1/cases/{case_id}/artifacts` — Filter normalized artifacts by type (`CALL`, `MESSAGE`, etc.), date range, sender, and receiver.
* `GET /api/v1/artifacts/{artifact_id}` — Retrieve canonical artifact metadata and associated MongoDB raw document payload.
* `GET /api/v1/artifacts/{artifact_id}/provenance` — Retrieve forensic provenance: source archive path, extraction offset, XML node hash.

### 3.6 Search Subsystem (`/api/v1/search`)
* `POST /api/v1/cases/{case_id}/search/exact` — Query exact identifiers (phone numbers, IMEIs, hashes, usernames).
* `POST /api/v1/cases/{case_id}/search/fulltext` — Inverted index full-text query with term weighting and field matching.
* `POST /api/v1/cases/{case_id}/search/semantic` — Natural language vector retrieval using Sentence-BERT embeddings.
* `POST /api/v1/cases/{case_id}/search/hybrid` — Combined reciprocal rank fusion (RRF) across keyword and semantic search.

### 3.7 Investigator Workspace & Findings (`/api/v1/investigation`)
* `GET  /api/v1/cases/{case_id}/findings` — Retrieve investigator bookmarks, tagged items, and working hypotheses.
* `POST /api/v1/cases/{case_id}/findings` — Create a validated investigative finding linked to explicit evidence records.
* `POST /api/v1/cases/{case_id}/tags` — Apply tags or classifications to specific artifact IDs.

### 3.8 Forensic Analytics (`/api/v1/analytics`)
* `GET /api/v1/cases/{case_id}/analytics/timeline` — Unified chronological timeline with temporal density histogram.
* `GET /api/v1/cases/{case_id}/analytics/graph` — Filtered entity communication subgraph (nodes, edges, metrics).
* `GET /api/v1/cases/{case_id}/analytics/anomalies` — Scikit-Learn Isolation Forest statistical outlier events with explanation metrics.

### 3.9 Grounded AI & Natural Language Assistance (`/api/v1/ai`)
* `POST /api/v1/cases/{case_id}/ai/query` — Natural language investigative question. Returns grounded answer with mandatory evidence record citations.
* `POST /api/v1/cases/{case_id}/ai/summarize-entity` — Evidence-grounded summary of communication history for an entity.

### 3.10 Forensic Report Generation (`/api/v1/reports`)
* `POST /api/v1/cases/{case_id}/reports/generate` — Enqueue generation of court-ready forensic report (PDF/HTML).
* `GET  /api/v1/reports/{report_id}` — Retrieve report status and download link.

### 3.11 Tamper-Evident Audit Trail (`/api/v1/audit`)
* `GET /api/v1/cases/{case_id}/audit-logs` — Retrieve immutable case activity logs with user, timestamp, action, and resource identifiers.
