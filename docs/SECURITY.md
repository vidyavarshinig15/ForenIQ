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

* Every authentication attempt (success, failure, lockout), user creation, case creation, case update, membership alteration, evidence upload, download, and quarantine generates an append-only `AuditLog` entry.
* The audit log captures: `timestamp`, `user_id`, `action`, `resource_type`, `resource_id`, `case_id`, `status`, `details_json`, `client_ip`.
* Sensitive data filtering: passwords, tokens, and raw private evidence are strictly stripped before audit serialization.
* Audit log viewing (`GET /api/v1/audit`) is restricted to the `ADMIN` role.

---

## 7. Forensic Evidence Ingestion Security (Phase 3 Implemented)

### 7.1 Defensive Archive Inspection & Anti-Exploit Controls
All incoming archives (`.ufdr`, `.zip`) are treated as hostile, untrusted binaries. The ingestion engine enforces strict defensive checks before committing any file to storage:
* **Magic Byte Signature Verification:** Files must begin with valid PK-ZIP headers (`b"PK\x03\x04"`, `b"PK\x05\x06"`, or `b"PK\x07\x08"`). Masquerading files (e.g. executable binaries or shell scripts renamed with a `.ufdr` extension) are immediately rejected with `422 Unprocessable Entity`.
* **Anti-ZipSlip Path Traversal Protection:** Every internal entry in the archive (`zipfile.ZipInfo.filename`) is inspected. Entries containing directory traversal sequences (`..`), leading slashes (`/`, `\`), absolute paths, or Windows drive prefixes (`C:`) are flagged as malicious exploits and immediately purged.
* **ZipBomb & Resource Exhaustion Defense:** Total entry counts are capped at `100,000` items. Uncompressed sizes exceeding `50MB` are evaluated against a maximum decompression ratio of `100:1` to defend against algorithmic decompression bomb amplification.
* **No Premature Extraction:** Phase 3 performs inspection strictly in read-only mode without extracting contents to disk, completely neutralizing code execution risks.

### 7.2 Memory-Bounded Streaming & In-Flight Hashing
* Uploaded evidence files are processed chunk-by-chunk directly to disk staging buffers (64KB chunks) via `LocalStorageService.store_stream()`.
* Multi-gigabyte archives never buffer into server RAM, preventing memory exhaustion and DoS attacks.
* Cryptographic **SHA-256** checksums are computed incrementally on the fly as chunks arrive. The final digest is saved directly with the `Evidence` record.
* Configurable size enforcement (`MAX_UPLOAD_SIZE_MB`) terminates oversized uploads mid-stream, immediately unlinks temporary staging files, and emits an `EVIDENCE_UPLOAD_FAILED` audit event.

### 7.3 Storage Isolation & Path Traversal Defense
* User-supplied filenames are treated as untrusted metadata. Physical files are stored strictly using non-guessable, cryptographically generated UUIDs:
  `storage/evidence/cases/<case_id>/<evidence_id>/original.<ext>`
* Target storage paths are validated using `Path.resolve().is_relative_to(root)` to prevent filesystem escapes.
* Evidence archives are stored in isolated volumes (`storage/evidence`) and are never placed in public web roots (`frontend/public/`) or exposed to unauthenticated static web handlers.

### 7.4 Non-Destructive Quarantine Lifecycle
* Normal users cannot execute destructive physical deletion of evidence.
* Soft quarantine (`DELETE /cases/{id}/evidence/{evidence_id}`) sets status to `QUARANTINED` while preserving the raw binary on disk for forensic reproducibility and legal scrutiny.

---

---

## 8. UFDR Parsing Engine & Safe Archive Processing (Phase 5 Implemented)

### 8.1 Defensive Archive Inspection & Anti-Exploit Enforcement
Evidence packages entering the parsing pipeline are untrusted forensic payloads. The parser engine (`SafeArchiveInspector`) applies deterministic perimeter validation before extracting any bytes:
* **Anti-ZipSlip Path Traversal:** Every archive entry path is normalized and inspected. Entries with parent traversal (`..`), leading slashes (`/`, `\`), absolute paths, or Windows drive specifications (`C:`) raise `ZipSlipError` and abort processing immediately.
* **ZipBomb & Resource Exhaustion Defense:**
  * `MAX_ARCHIVE_ENTRIES`: Bounded to 100,000 entries max.
  * `MAX_TOTAL_UNCOMPRESSED_SIZE`: Capped at 50 GB.
  * `MAX_SINGLE_ENTRY_SIZE`: Capped at 10 GB.
  * `MAX_COMPRESSION_RATIO`: Entries exceeding a 100:1 uncompressed-to-compressed ratio are rejected with `ZipBombError`.
* **Nested Archive Depth Defense:** Recursive extraction is capped at `MAX_ARCHIVE_DEPTH = 2`. Excessive depth raises `NestedArchiveExceededError` to prevent resource starvation.

### 8.2 Sandboxed Ephemeral Extraction & Guaranteed Cleanup
* Parsing occurs in an isolated, non-public scratch sandbox: `storage/scratch/jobs/<job-id>/`.
* Never extracted into web-accessible or public directories (`frontend/public/`).
* Sandboxes are cleaned up unconditionally in a `finally:` block upon job completion, partial success, or catastrophic failure. Operational failures during cleanup are logged for monitoring.

### 8.3 Hardened Streaming XML Parsing (Anti-XXE & Bounded Memory)
* **Zero Trust XML:** All structured XML files are parsed using `defusedxml.ElementTree.iterparse`.
* **Anti-XXE Protection:** External entity resolution (DTD), parameter entities, and external resource loading are completely disabled. Malicious payloads attempting XXE file disclosure or SSRF are neutralized and recorded as `MalformedXMLError`.
* **Streaming O(1) Memory Footprint:** XML documents are read sequentially tag-by-tag. As child elements are parsed into `ParsedArtifactRecord` instances, `elem.clear()` and `root.clear()` are invoked immediately. Multi-gigabyte XML trees are never assembled in RAM.

### 8.4 Pre-Flight Cryptographic Integrity Gate
* Before archive inspection or parser execution commences, the worker computes a fresh in-flight SHA-256 digest of the stored evidence binary.
* If the computed hash does not match the immutable ingestion baseline (`IntegrityStatus.MISMATCH`), parsing is immediately blocked.
* The evidence is marked as quarantined, an `INTEGRITY_MISMATCH` custody event is recorded, and an `UFDR_PROCESSING_FAILED` audit entry is created. Mismatched or tampered evidence is never parsed as authentic evidence.

### 8.5 Idempotent Reprocessing & Atomic Data Integrity
* Reprocessing an evidence package deletes existing raw artifacts previously linked to that evidence before inserting new records.
* Avoids phantom duplicate records upon retry.
* Artifact writes are performed in batched bulk inserts within managed database transactions.

## 9. Forensic Integrity Verification & Tamper-Evident Chain of Custody (Phase 4)

### 9.1 Streaming SHA-256 Storage Integrity Verification
* `IntegrityService` recalculates the cryptographic SHA-256 checksum on-demand by reading stored evidence files in 64KB blocks.
* This operates with $O(1)$ memory consumption, avoiding multi-gigabyte RAM loads.
* The calculated digest is compared against the immutable ingestion baseline recorded in the `evidence` table.

### 9.2 Cryptographic Mismatch & Tamper Defense
* **Prohibition of Hash Overwriting:** If a mismatch is detected (`stored_hash != calculated_hash`), the system strictly forbids overwriting or "fixing" the recorded hash.
* **Automatic Evidence Lockdown:** The evidence item transitions immediately to `IntegrityStatus.MISMATCH` and `EvidenceStatus.QUARANTINED`.
* **Tamper Event Logging:** A dedicated `INTEGRITY_MISMATCH` custody event and `INTEGRITY_MISMATCH_DETECTED` audit event are emitted, preserving both hashes for forensic scrutiny.

### 9.3 Append-Only Tamper-Evident Custody Hash Chain
* Every evidence lifecycle event is recorded in the append-only `evidence_custody_events` table.
* **Deterministic Canonicalization:** The event hash is generated by canonicalizing:
  $$\text{event\_hash} = \text{SHA-256}(\text{JSON}(\text{sequence}, \text{evidence\_id}, \text{case\_id}, \text{actor}, \text{type}, \text{UTC timestamp}, \text{prev\_hash}, \text{metadata}))$$
* **Parent Hash Linkage:** Each consecutive event embeds the SHA-256 hash of its predecessor (`previous_event_hash`), creating an unbroken tamper-evident audit chain.
* **Chain Verification:** The `/verify-custody-chain` endpoint recomputes hashes across all historical records; any payload alteration or sequence break is flagged immediately as `INVALID`.

### 9.4 Role Separation & Privilege Constraints
* `VIEWER` roles are strictly prohibited from triggering integrity checks or modifying case states (`403 Forbidden`).
* Viewers are permitted read-only access to view the verified chain of custody.

---

## 10. Large-Scale Processing & Queue Security Governance (Phase 6)

### 10.1 Processing Job IDOR Defense
* All job manipulation endpoints (`GET /processing-jobs/{id}`, `POST /cancel`, `POST /retry`) enforce strict case-membership checks.
* If a caller attempts to query or manipulate a job belonging to another case or a case they are not a member of, the API returns `404 Not Found`, preventing cross-case information leakage and unauthorized job disruption.

### 10.2 Queue Priority Starvation Defense
* Ingesting high volumes of evidence must not allow individual investigators to starve the worker pool by submitting jobs marked `HIGH`.
* The `ProcessingService` automatically throttles any priority submission from non-admin users (`INVESTIGATOR`, `ANALYST`) to `NORMAL` priority:
  ```python
  if current_user.role != UserRole.ADMIN and priority == JobPriority.HIGH:
      final_priority = JobPriority.NORMAL
  ```

### 10.3 Pre-Flight Storage Exhaustion Protection
* Large UFDR extractions can exhaust host filesystem capacity.
* Before archive extraction, `UFDRParserWorker` inspects available disk space using `shutil.disk_usage`.
* If available storage is below `MAX_TEMP_STORAGE_MB` (default: 5,000 MB / 5 GB), the job fails safely with `INSUFFICIENT_TEMP_STORAGE`, preventing system crash or disk lockups.

### 10.4 Worker Isolation & State Sanitation
* Worker processes do not share global in-memory mutable state containing evidence or tokens.
* Each job is assigned a unique worker ID (`worker-XXXXXX`) and writes exclusively to an ephemeral scratch directory `storage/scratch/jobs/<job-id>/`.
* Sensitive authentication tokens, passwords, and raw evidence byte payloads are never emitted in worker logs or metrics telemetry.

### 10.5 Original Evidence Immutability Verification
* Ingestion workers open canonical stored evidence in strict read-only mode (`rb`).
* Forensic test suites continuously assert that the original evidence SHA-256 hash before and after execution remains strictly identical.


