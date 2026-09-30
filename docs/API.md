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

## 4. Planned Future API Namespaces

* `/api/v1/evidence` — Multipart UFDR archive upload, streaming decompression, SHA-256 verification (Phase 3).
* `/api/v1/jobs` — Asynchronous evidence processing task tracking (Phase 3).
* `/api/v1/search` — Exact, full-text, and semantic vector discovery (Phase 4).
* `/api/v1/timeline` — Cross-artifact chronological alignment (Phase 4).
* `/api/v1/graph` — Entity interaction graphs and network metrics (Phase 5).
* `/api/v1/anomalies` — Statistical outlier scoring (Phase 5).
* `/api/v1/investigation` — Bookmarking, tagging, and formal hypothesis notes (Phase 5).
* `/api/v1/reports` — Court-ready forensic PDF/HTML generation (Phase 6).
* `/api/v1/ai` — Grounded RAG query assistance with mandatory citations (Phase 6).
