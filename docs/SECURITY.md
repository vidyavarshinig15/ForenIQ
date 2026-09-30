# AI-Driven Intelligent UFDR Analysis System
## Security Architecture & Threat Model

**Document Version:** 1.2.0  
**Current Phase:** Phase 2 — Authentication, RBAC & Case Management  
**Status:** Active Security Standard  

---

## 1. Principles of Forensic Security

Digital forensic software processes inherently hostile, untrusted, and potentially malformed inputs while operating in environments where chain of custody and data integrity are legally scrutinized.

The platform is designed under four primary security tenets:
1. **Zero Trust for Evidence Payloads:** All evidence archives, XML files, chat transcripts, and media files are treated as adversarial inputs.
2. **Strict Defense in Depth:** Perimeter validation, kernel-level file permissions, memory-bounded streaming, and sandboxed processing.
3. **Mandatory Case-Scoped Authorization:** Access to an evidence record or case resource requires explicit, verified case membership.
4. **Non-Repudiation & Cryptographic Provenance:** Every evidence item, user authentication, and investigative operation is verified with cryptographic checksums and immutable audit events.

---

## 2. Authentication & Identity Management (Phase 2 Implemented)

### 2.1 Password Hashing & Credential Storage
* Passwords are encrypted using **Argon2id** (`argon2-cffi`) with high-security forensic parameters:
  * Memory Cost: 65,536 KiB (64 MB)
  * Time Cost: 3 iterations
  * Parallelism: 2 threads
  * Salt Length: 16 bytes
  * Hash Length: 32 bytes
* Plaintext credentials or reversible encryptions are strictly forbidden. Passwords never appear in application logs or exception tracebacks.

### 2.2 Token & Session Security
* Authentication utilizes signed **JSON Web Tokens (JWT)**:
  * Algorithm: `HS256` in local/staging environments, `RS256` or `EdDSA` in production.
  * Lifetime: Access token expiration is capped at 60 minutes.
  * Token Payload: Encodes subject UUID (`sub`), system role (`role`), issuance timestamp (`iat`), expiration (`exp`), and issuer (`iss`). No sensitive forensic evidence or credentials reside in JWT claims.
  * Validation: Invalided, expired, or malformed tokens trigger standardized `401 Unauthorized` responses without exposing system internals.

### 2.3 Authentication Rate Limiting & Brute-Force Defense
* The backend enforces sliding-window rate limiting via `LoginRateLimiter`:
  * Failed attempts are tracked by composite key (`email` + `client_ip`).
  * Reaching 5 consecutive failures triggers an automated 15-minute temporary lockout (`429 Too Many Requests`).
  * Generic error messages (`"Invalid email or password."`) are returned for both invalid passwords and nonexistent accounts to prevent user enumeration attacks.
  * Throttled and failed login attempts are written to the audit log.

---

## 3. Authorization & Role-Based Access Control (RBAC)

### 3.1 Role Hierarchy
The platform defines four standardized system roles:

| Role | Permissions Overview | Typical Persona |
| :--- | :--- | :--- |
| **ADMIN** | Full system configuration, user provisioning, global audit log review, all-case visibility and management. | System Administrator / Lab Director |
| **INVESTIGATOR** | Case creation, assigned case updates, investigator assignments, future evidence uploads and workspace findings. | Lead Detective / Senior Forensic Examiner |
| **ANALYST** | Read and search assigned case evidence, execute timeline/graph analysis, add analytical notes. Cannot create or reconfigure cases. | Digital Forensic Analyst / Specialist |
| **VIEWER** | Read-only access to assigned cases and finalized reports. Cannot edit metadata, upload evidence, or alter members. | Legal Counsel / Prosecutor / Auditor |

### 3.2 Dual-Tier Authorization: Role + Case Scoping
RBAC alone is insufficient for multi-case forensic environments. Authorization is enforced across two dimensions:
1. **System Role:** Does the user's role permit this action?
2. **Case Membership:** Is the user explicitly assigned to the specific `case_id`?

```
User Request: GET /api/v1/cases/7a3b4c12...
        │
        ▼
Is User Authenticated? (Valid Bearer JWT)
        │ YES
        ▼
Is User System ADMIN?
 ├── YES ──► Grant Global Access
 └── NO
      │
      ▼
Query CaseMember Table: (case_id == 7a3b4c12 AND user_id == user.id)
 ├── Membership Found ──► Grant Case Access (with Member Access Role)
 └── No Membership ────► Reject with 404 NOT FOUND (Prevent IDOR Disclosure)
```

---

## 4. Insecure Direct Object Reference (IDOR) Defenses

* **The Problem:** Attackers attempt to guess or enumerate case UUIDs (`/cases/{case_id}`) to view unauthorized cases.
* **The Defense:**
  1. `CaseRepository.list_for_user()` joins `Case` directly with `CaseMember` at the SQL query level. Unauthorized cases are never sent to the client.
  2. `CaseService.get_case()` checks case membership before returning details. If unauthorized, the service raises `404 Not Found` (rather than revealing case existence) and logs an `UNAUTHORIZED_ACCESS` audit event.
  3. Case mutations (`PATCH`, member additions/deletions) require `LEAD` membership or `ADMIN` role.

---

## 5. Case Lifecycle & Preservation Security

* **Controlled Transitions:** Case statuses are restricted to `OPEN`, `IN_PROGRESS`, `CLOSED`, and `ARCHIVED`.
* **Zero Hard Deletes:** Digital forensic principles require preservation of evidence and procedural history. The platform disallows destructive deletions from the normal UI. Closing or archiving a case locks status while preserving all history and audit logs.

---

## 6. Audit Trail Security

* Every authentication attempt (success, failure, lockout), user creation, case creation, case update, and membership alteration generates an append-only `AuditLog` entry.
* The audit log captures: `timestamp`, `user_id`, `action`, `resource_type`, `resource_id`, `case_id`, `status`, `details_json`, `client_ip`.
* Sensitive data filtering: passwords, tokens, and raw private evidence are strictly stripped before audit serialization.
* Audit log viewing (`GET /api/v1/audit`) is restricted to the `ADMIN` role.
