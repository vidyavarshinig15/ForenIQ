# AI-Driven Intelligent UFDR Analysis System
## API Architecture & Route Specifications

**Document Version:** 1.2.0  
**Current Phase:** Phase 2 — Authentication, RBAC & Case Management  
**Status:** Active API Specifications  

---

## 1. API Design Principles & Standard Conventions

1. **Protocol:** Strict HTTPS / TLS in production; HTTP for local development.
2. **Standard Serialization:** UTF-8 encoded JSON for all data exchanges.
3. **Authentication:** Bearer JWT in `Authorization` header (`Authorization: Bearer <token>`).
4. **Deterministic Status Codes:** Strict semantic alignment with HTTP specification:
   * `200 OK` — Successful query or state retrieval
   * `201 Created` — Successful resource creation (user, case, member)
   * `400 Bad Request` — Malformed input, business constraint violation
   * `401 Unauthorized` — Missing, expired, or invalid JWT credentials
   * `403 Forbidden` — Insufficient system role or case-level permissions
   * `404 Not Found` — Resource missing or access unauthorized (IDOR defense)
   * `409 Conflict` — Email or case number duplicate
   * `422 Unprocessable Entity` — Schema validation error
   * `429 Too Many Requests` — Authentication brute-force rate limit lockout
   * `500 Internal Server Error` — Unexpected server fault (sanitized, non-leaking)

---

## 2. Standard Response Envelopes

### 2.1 Success Envelope
Standard responses return serialized JSON data models directly or enveloped with metadata:
```json
{
  "id": "e9a0f44b-4b13-4ec3-bf30-5f0e9b9868d1",
  "case_number": "CASE-2026-000001",
  "title": "Operation Silent Beacon",
  "status": "OPEN",
  "created_at": "2026-09-30T17:00:00Z"
}
```

### 2.2 Error Envelope
All application errors follow the uniform, non-leaking structure:
```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Invalid email or password."
  }
}
```

---

## 3. Implemented API Endpoints (Phase 1 & 2)

### 3.1 Operational Health Check
* `GET /api/v1/health` — Public health verification endpoint. Returns `{"status": "ok"}`.

### 3.2 Authentication & User Profile (`/api/v1/auth`)
* `POST /api/v1/auth/register` — Register a new investigator account.
  * Request Body: `{ "email": "user@ufdr.org", "name": "Officer Name", "password": "...", "role": "INVESTIGATOR" }`
  * Response: `UserResponse` (HTTP 201).
* `POST /api/v1/auth/login` — Authenticate credentials via Argon2id; returns Bearer JWT.
  * Request Body: `{ "email": "user@ufdr.org", "password": "..." }`
  * Response: `{ "access_token": "...", "token_type": "bearer", "expires_in_seconds": 3600, "user": { ... } }`
* `POST /api/v1/auth/logout` — Revoke active session and log audit event.
* `GET  /api/v1/auth/me` — Retrieve profile, active status, and RBAC role of authenticated user.

### 3.3 Case Management (`/api/v1/cases`)
* `POST /api/v1/cases` — Create a new forensic case. Assigns creator as `LEAD` member.
  * Request Body: `{ "title": "...", "description": "...", "case_number": "OPTIONAL" }`
  * Role requirement: `ADMIN` or `INVESTIGATOR`.
* `GET /api/v1/cases` — List authorized cases for authenticated user (enforced at database level).
  * Query parameters: `status` (`ALL`, `OPEN`, `IN_PROGRESS`, `CLOSED`, `ARCHIVED`), `skip`, `limit`.
* `GET /api/v1/cases/{case_id}` — Retrieve case details and member list.
  * Enforces case-scoping (rejects unauthorized users with 404 to prevent IDOR enumeration).
* `PATCH /api/v1/cases/{case_id}` — Update case title, description, or lifecycle status.
  * Role requirement: `ADMIN` or case `LEAD`/`CONTRIBUTOR`.
* `GET /api/v1/cases/{case_id}/members` — List authorized members for the case.
* `POST /api/v1/cases/{case_id}/members` — Assign an investigator or analyst to the case.
  * Request Body: `{ "email": "officer@ufdr.org", "access_role": "CONTRIBUTOR" }`
  * Role requirement: `ADMIN` or case `LEAD`.
* `PATCH /api/v1/cases/{case_id}/members/{user_id}` — Update case member role.
  * Role requirement: `ADMIN` or case `LEAD`.
* `DELETE /api/v1/cases/{case_id}/members/{user_id}` — Revoke case access for a member.
  * Role requirement: `ADMIN` or case `LEAD`.

### 3.4 User Directory (`/api/v1/users`)
* `GET /api/v1/users` — List system user accounts for member assignment.
  * Role requirement: `ADMIN` or `INVESTIGATOR`.

### 3.5 Forensic Audit Trail (`/api/v1/audit`)
* `GET /api/v1/audit` — Query append-only audit trail logs.
  * Query parameters: `case_id`, `user_id`, `skip`, `limit`.
  * Role requirement: `ADMIN`.

---

### 3.6 Forensic Evidence Ingestion (`/api/v1/cases/{case_id}/evidence`)
* `POST /api/v1/cases/{case_id}/evidence` — Secure streaming multipart upload of forensic evidence (.ufdr, .zip).
  * Enforces case-level scoping and role verification (rejects `VIEWER` and unassigned investigators).
  * Inspects magic bytes, detects ZipSlip directory traversal, and enforces ZipBomb compression ratio limits (>100x uncompressed-to-compressed).
  * Calculates cryptographic SHA-256 digest in-flight during chunked streaming without buffering into RAM.
  * Formats: `multipart/form-data` with `file: UploadFile`.
  * Response: `EvidenceUploadResult` (HTTP 201 Created).
* `GET /api/v1/cases/{case_id}/evidence` — List evidence files uploaded to the specified case.
  * Scoped strictly to the case; physical disk paths and storage keys are redacted.
  * Query parameters: `skip`, `limit`.
  * Response: `List[EvidenceResponse]` (HTTP 200 OK).
* `GET /api/v1/cases/{case_id}/evidence/{evidence_id}` — Retrieve detailed forensic metadata for a specific evidence item.
  * Returns original filename, file size, SHA-256 digest, mime types, upload officer, and status.
  * Response: `EvidenceResponse` (HTTP 200 OK).
* `DELETE /api/v1/cases/{case_id}/evidence/{evidence_id}` — Soft-quarantine an evidence item.
  * Forensic immutability safeguard: Raw evidence files are NEVER permanently erased through normal API calls. The status transitions to `QUARANTINED`.
  * Role requirement: `ADMIN` or case `LEAD`.
  * Response: `EvidenceResponse` (HTTP 200 OK).
* `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/download` — Secure streaming download of the raw forensic evidence file.
  * Verifies case authorization and streams chunks directly from isolated evidence storage.
  * Includes `X-Evidence-SHA256` header for client-side integrity validation.
  * Response: Binary stream with `application/octet-stream` (HTTP 200 OK).

### 3.7 Forensic Evidence Integrity & Chain of Custody (`/api/v1/cases/{case_id}/evidence/{evidence_id}`)
* `POST /api/v1/cases/{case_id}/evidence/{evidence_id}/verify-integrity` — On-demand streaming SHA-256 storage verification.
  * Streams stored physical file in 64KB chunks and recalculates hash in-flight.
  * Compares against baseline recorded at upload.
  * If valid, updates `integrity_status = VALID` and emits `INTEGRITY_VERIFIED` custody event.
  * If mismatched, strictly preserves baseline hash, updates `integrity_status = MISMATCH`, transitions evidence to `QUARANTINED`, and emits `INTEGRITY_MISMATCH` custody event.
  * Role requirement: `ADMIN` or case `LEAD`/`CONTRIBUTOR` (`VIEWER` rejected).
  * Response: `IntegrityVerificationResult` (HTTP 200 OK).
* `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/custody` — Retrieve chronological chain of custody events.
  * Returns ordered history of immutable lifecycle records (`EVIDENCE_UPLOADED`, `EVIDENCE_HASHED`, `INTEGRITY_VERIFIED`, etc.) with sequence numbers, actor info, and SHA-256 event hash linkage.
  * Response: `List[EvidenceCustodyEventResponse]` (HTTP 200 OK).
* `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/verify-custody-chain` — Verify cryptographic integrity of the custody hash chain.
  * Iterates across sequential events, recalculates each canonical event hash, and verifies `previous_event_hash` linkage.
  * Returns validation report with count of checked events.
  * Response: `CustodyChainVerificationResult` (HTTP 200 OK).

### 3.8 Forensic Processing & Raw Artifacts (`/api/v1/cases/{case_id}`)
* `POST /api/v1/cases/{case_id}/evidence/{evidence_id}/parse` — Trigger asynchronous UFDR ingestion and parsing.
  * Query params: `priority` (`HIGH`, `NORMAL`, `LOW`; default: `NORMAL`). Non-admin callers requesting `HIGH` are automatically normalized to `NORMAL`.
  * Validates case authorization (rejects `VIEWER`), checks baseline integrity (rejects if `MISMATCH`), checks for existing active job.
  * Enqueues job into persistent priority queue (Redis or Transactional Database Queue).
  * Emits `EVIDENCE_PROCESSING_STARTED` custody event and `PROCESSING_JOB_CREATED` audit log.
  * Response: `ProcessingJobResponse` (HTTP 202 Accepted).
* `GET /api/v1/cases/{case_id}/processing-jobs/{job_id}` — Get real-time status and telemetry of a processing job.
  * Returns:
    * `status`: `QUEUED`, `STARTING`, `RUNNING`, `PAUSED`, `RETRYING`, `COMPLETED`, `PARTIAL`, `FAILED`, `CANCEL_REQUESTED`, `CANCELLED`
    * `priority`: `HIGH`, `NORMAL`, `LOW`
    * `current_stage`: `VALIDATING`, `INSPECTING_ARCHIVE`, `PARSING`, `PERSISTING`, `FINALIZING`, `COMPLETED`
    * `current_file`: Current archive member being parsed
    * `worker_id`: Worker cluster identifier (e.g. `worker-a1b2c3`)
    * `processing_rate`: Real throughput in records per second
    * `estimated_remaining_seconds`: Real-time remaining time estimate
    * `records_processed`, `records_failed`, `files_processed`, `files_total`
    * `checkpoint_data`: Resumable checkpoint catalog
    * `last_heartbeat_at`, `lease_expires_at`
  * Response: `ProcessingJobResponse` (HTTP 200 OK).
* `POST /api/v1/cases/{case_id}/processing-jobs/{job_id}/cancel` — Cooperative cancellation of an active processing job.
  * Sets status to `CANCEL_REQUESTED`. Active worker aborts cleanly at the next file boundary and cleans up scratch sandboxes.
  * Emits `PROCESSING_JOB_CANCEL_REQUESTED` and `PROCESSING_JOB_CANCELLED` audit events.
  * Response: `ProcessingJobResponse` (HTTP 200 OK).
* `POST /api/v1/cases/{case_id}/processing-jobs/{job_id}/retry` — Resumable retry of a failed or cancelled processing job.
  * Resumes from the latest saved checkpoint, skipping already completed files.
  * Emits `PROCESSING_JOB_RETRIED` audit event.
  * Response: `ProcessingJobResponse` (HTTP 202 Accepted).
* `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/processing-jobs` — List processing job history for evidence package.
  * Response: `List[ProcessingJobResponse]` (HTTP 200 OK).
* `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/artifacts` — Retrieve paginated raw forensic artifact records.
  * Query params: `artifact_type` (optional filter: `CALL`, `MESSAGE`, `CONTACT`, `LOCATION`, `BROWSER`, `APPLICATION`, `FILESYSTEM`), `page` (default 1), `page_size` (default 50).
  * Returns records preserving complete provenance (`source_file`, `source_path`, `record_identifier`, `raw_data`).
  * Response: `RawArtifactListResponse` (HTTP 200 OK).
* `GET /api/v1/cases/{case_id}/artifacts/{artifact_id}` — Get single raw artifact detail with complete raw payload.
  * Response: `RawArtifactResponse` (HTTP 200 OK).

---

## 4. Planned Future API Namespaces

## Phase 7 Endpoints: Evidence Normalization & Canonical Data Model

### `POST /api/v1/cases/{case_id}/evidence/{evidence_id}/normalize`
* **Description:** Asynchronously triggers a normalization worker job for all raw artifacts within an evidence container.
* **Headers:** `Authorization: Bearer <token>`
* **Permissions:** Case LEAD / CONTRIBUTOR or System ADMIN (requires write permission). Blocked if evidence integrity is `MISMATCH` or status is `QUARANTINED`.
* **Request Body:**
  ```json
  {
    "priority": "HIGH"
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "id": "f188c036-95e8-4619-adef-4e6a0dba64bb",
    "case_id": "b6b06823-27fb-4c61-af9a-c2615bbfa034",
    "evidence_id": "0413af5f-afe2-4877-8436-c2e96a9fc4d6",
    "job_type": "NORMALIZATION",
    "priority": "HIGH",
    "status": "QUEUED",
    "current_stage": "VALIDATING",
    "created_at": "2026-10-01T13:30:47.009165Z"
  }
  ```

### `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/canonical-records`
* **Description:** Retrieves paginated canonical evidence records with multi-dimensional filtering.
* **Headers:** `Authorization: Bearer <token>`
* **Query Parameters:**
  * `artifact_type`: (Optional) Filter by `CALL`, `MESSAGE`, `CONTACT`, `LOCATION`, `BROWSER`, `APPLICATION`, `FILE_SYSTEM`, `GENERIC`.
  * `application`: (Optional) Filter by normalized application name (e.g. `WhatsApp`, `Chrome`, `Signal`).
  * `data_quality_status`: (Optional) Filter by `VALID`, `PARTIAL`, `INVALID`.
  * `page`: (Optional, default: 1)
  * `page_size`: (Optional, default: 50, max: 200)
* **Response (200 OK):**
  ```json
  {
    "items": [
      {
        "id": "e98b8567-9ebd-597e-a988-eda2631d04e4",
        "case_id": "b6b06823-27fb-4c61-af9a-c2615bbfa034",
        "evidence_id": "0413af5f-afe2-4877-8436-c2e96a9fc4d6",
        "raw_artifact_id": "088672ed-79c9-519e-95a5-6ebb97d2c8c1",
        "artifact_type": "BROWSER",
        "canonical_fingerprint": "32345d96e65869e61ebd63040c9bdb6b600d7178b8bb383810647b51eee81a91",
        "event_timestamp": "2026-09-30T15:59:00Z",
        "timestamp_precision": "SECOND",
        "timestamp_status": "VALID",
        "application": "Chrome",
        "content": "Secure Portal 59 (https://suspicious-site-59.org/login)",
        "entities": [
          { "entity_type": "URL", "entity_value": "https://suspicious-site-59.org/login", "role": "visited_url" }
        ],
        "metadata": { "url": "https://suspicious-site-59.org/login", "title": "Secure Portal 59" },
        "data_quality_status": "VALID",
        "validation_warnings": []
      }
    ],
    "total": 1050,
    "page": 1,
    "page_size": 50,
    "total_pages": 21
  }
  ```

### `GET /api/v1/cases/{case_id}/canonical-records/{record_id}`
* **Description:** Retrieves an individual canonical record by primary UUID with case membership authorization.
* **Headers:** `Authorization: Bearer <token>`
* **Response (200 OK):** `CanonicalEvidenceResponse`

### `GET /api/v1/cases/{case_id}/canonical-records/{record_id}/raw`
* **Description:** Traces a canonical record directly back to its exact originating RawArtifact and raw XML payload, guaranteeing unbroken bidirectional forensic provenance.
* **Headers:** `Authorization: Bearer <token>`
* **Response (200 OK):** `RawArtifactResponse` (contains `id`, `source_file`, `source_path`, `record_identifier`, `raw_data`).

## Planned Future Phase Route Inclusions:

* `/api/v1/search` — Exact, full-text, and semantic vector discovery (Phase 8).
* `/api/v1/timeline` — Cross-artifact chronological alignment (Phase 9).
* `/api/v1/graph` — Entity interaction graphs and network metrics (Phase 10).
* `/api/v1/anomalies` — Statistical outlier scoring (Phase 11).
* `/api/v1/investigation` — Bookmarking, tagging, and formal hypothesis notes (Phase 12).
* `/api/v1/reports` — Court-ready forensic PDF/HTML generation (Phase 13).



