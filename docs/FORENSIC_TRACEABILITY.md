# AI-Driven Intelligent UFDR Analysis System
## Forensic Traceability & Evidence Integrity Framework

**Document Version:** 1.0.0  
**Classification:** Digital Forensic Legal & Procedural Standard  
**Status:** Foundation Phase  

---

## 1. The Core Forensic Lineage Model

In legal proceedings, evidence analyzed by digital systems must withstand rigorous cross-examination regarding authenticity, integrity, and provenance. 

The platform guarantees an unbroken chain of traceability across six discrete operational stages:

$$\text{Evidence} \longrightarrow \text{Artifact} \longrightarrow \text{Record} \longrightarrow \text{Analysis} \longrightarrow \text{Finding} \longrightarrow \text{Report}$$

```
┌─────────────────────────┐
│     EVIDENCE FILE       │  UFDR archive file, physical hash (SHA-256), acquisition metadata,
│   (Acquisition Stage)   │  investigator custody record.
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│    FORENSIC ARTIFACT    │  Specific component within extraction (e.g. databases/msgstore.db,
│   (Extraction Stage)    │  report.xml section, raw file system offset).
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│    CANONICAL RECORD     │  Normalized record in database (unique UUIDv5, normalized UTC
│  (Normalization Stage)  │  timestamp, participating entities, raw document payload link).
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│   ANALYTICAL OUTPUT     │  Graph edge, timeline entry, or statistical anomaly referencing
│    (Analytics Stage)    │  the canonical record ID.
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  INVESTIGATIVE FINDING  │  Investigator observation, hypothesis, or validated note linked
│    (Workspace Stage)    │  directly to supporting canonical records.
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│     FORENSIC REPORT     │  Formal court-ready report citing verified findings and underlying
│    (Reporting Stage)    │  evidence provenance without ungrounded assertions.
└─────────────────────────┘
```

---

## 2. Cryptographic Integrity & Chain of Custody Framework (Phase 4)

### 2.1 The Three Forensic Tracking Layers
The platform maintains strict conceptual and technical separation across three auditing and verification layers:

1. **Evidence Storage Integrity:**
   * *Question Answered:* "Has the stored physical evidence archive on disk changed since it was ingested?"
   * *Mechanism:* Cryptographic SHA-256 hash comparison between the baseline ingestion record and an on-demand re-read of stored blocks.
   * *Status Outcomes:* `VALID`, `MISMATCH`, `MISSING`, `UNKNOWN`, `ERROR`.

2. **Tamper-Evident Chain of Custody:**
   * *Question Answered:* "What sequence of authorized lifecycle events occurred for this evidence item?"
   * *Mechanism:* Append-only records in `evidence_custody_events` linked sequentially via cryptographic parent hashes ($\text{previous\_event\_hash}$).
   * *Events:* `EVIDENCE_UPLOADED`, `EVIDENCE_HASHED`, `EVIDENCE_VALIDATED`, `EVIDENCE_ACCESSED`, `EVIDENCE_DOWNLOADED`, `INTEGRITY_VERIFIED`, `INTEGRITY_MISMATCH`, `EVIDENCE_QUARANTINED`.

3. **System Application Audit Trail:**
   * *Question Answered:* "What system-level API operations were performed by which user/IP?"
   * *Mechanism:* Security ledger in `audit_logs` tracking logins, access control modifications, permissions, and broad endpoint invocations.

### 2.2 In-Flight SHA-256 Ingestion Baseline
* Upon upload, the platform calculates a cryptographic **SHA-256 digest** in-flight while streaming chunked data from the client request directly into isolated storage staging.
* Zero multi-gigabyte RAM buffering is permitted.
* This digest is immediately committed to the `evidence` table as the immutable baseline identifier alongside:
  * Uploading officer ID (`uploaded_by`)
  * Upload timestamp UTC (`uploaded_at`)
  * File size in bytes (`file_size`)
  * Original user filename (`original_filename`)
  * Client IP and user agent

### 2.3 On-Demand Storage Integrity Verification
* Authorized examiners can invoke on-demand integrity checks (`POST /cases/{case_id}/evidence/{evidence_id}/verify-integrity`).
* The system streams the file in 64KB blocks directly from isolated storage, incrementally re-hashes the byte sequence, and compares the result to the recorded baseline.
* **Integrity Mismatch Policy:** If a discrepancy is found:
  * The baseline recorded hash is preserved immutably (never overwritten or modified).
  * `evidence.integrity_status` is updated to `MISMATCH`.
  * `evidence.status` is transitioned to `QUARANTINED`.
  * Dedicated `INTEGRITY_MISMATCH` custody and audit events are generated with the discrepancy details.

### 2.4 Tamper-Evident Custody Hash Chain Linkage
* Every custody event contains:
  $$\text{event\_hash} = \text{SHA-256}(\text{CanonicalJSON}(\text{seq}, \text{evidence\_id}, \text{case\_id}, \text{actor\_id}, \text{type}, \text{timestamp}, \text{prev\_hash}, \text{metadata}))$$
* Any unauthorized modification of an event's metadata, sequence, timestamp, or parent linkage invalidates the hash chain downstream, detectable via the `/verify-custody-chain` audit check.

### 2.5 Important Forensic Limitation
The platform is an investigative software tool, not a legal certification agency. Cryptographic verification establishes whether stored digital bytes match recorded baseline hashes; it does not independently verify external hardware seizure warrants, field acquisition protocols, or physical courier custody.

### 2.6 Artifact Provenance & Raw Source Traceability (Phase 5 Implemented)
Phase 5 establishes strict forensic lineage for every parsed raw artifact before downstream normalization or AI reasoning:
* **The Forensic Lineage Quadruple:** Every record in `raw_artifacts` immutably captures:
  $$\text{Provenance} = (\text{case\_id}, \text{evidence\_id}, \text{source\_file}, \text{source\_path}, \text{record\_identifier})$$
  * `evidence_id`: Foreign key linking to the parent evidence package and its cryptographically verified SHA-256 baseline.
  * `source_file`: The exact file within the archive that contained the record (e.g. `report.xml`, `contacts.xml`, `chats.xml`).
  * `source_path`: Normalized path of the structured member relative to the extraction root (e.g. `messages/whatsapp.xml`).
  * `record_identifier`: The extraction-tool specific record ID (e.g. `CALL_101`, `MSG_203`, `LOC_01`).
* **Preservation of Raw Structure (`raw_data`):** The exact extracted dictionary structure is stored verbatim in PostgreSQL JSONB (`raw_data`). The engine does not prematurely flatten, drop unrecognized keys, or lossy-compress evidence fields during ingestion.
* **Non-Destructive Processing & Original Evidence Immutability:** Processing operates read-only on the original evidence binary in temporary sandbox storage. Original files are never modified, altered, or overwritten.
* **Custody Events for Processing:** Initiation and conclusion of parsing emit tamper-evident custody events:
  * `EVIDENCE_PROCESSING_STARTED`: Captures job ID, job type, and processing actor.
  * `EVIDENCE_PROCESSING_COMPLETED`: Captures parsed artifact counts, warnings, execution duration, and parser summary.

### 2.4 Deterministic Artifact Identity & Idempotent Duplicate Prevention (Phase 6)
To satisfy court-mandated evidentiary reproducibility, repeating an extraction process must generate identical records without duplication:
* **Deterministic Composite Fingerprint:**
  $$\text{Identity Key} = \text{evidence\_id} \mathbin{\Vert} \text{source\_file} \mathbin{\Vert} \text{source\_path} \mathbin{\Vert} \text{record\_identifier} \mathbin{\Vert} \text{artifact\_type}$$
  $$\text{artifact\_fingerprint} = \text{SHA-256}(\text{Identity Key})$$
  $$\text{id} = \text{UUIDv5}(\text{evidence\_id}, \text{Identity Key})$$
* **Database Constraint:** Unique index `uq_raw_artifact_identity` on `(evidence_id, artifact_fingerprint)`.
* **Idempotent Ingestion Guarantee:** Batch inserts execute `ON CONFLICT (evidence_id, artifact_fingerprint) DO NOTHING`. If a job is retried or executed across multiple worker nodes, duplicate records are completely prevented at the database kernel level.
### 2.5 Canonical Evidence Traceability & Bidirectional Lineage (Phase 7)
In Phase 7, the forensic chain of custody extends into normalized data structures without breaking lineage:
* **The Full Forensic Provenance Chain:**
  $$\text{Original Evidence Archive} \xrightarrow{\text{SHA-256}} \text{Raw Artifact} \xrightarrow{\text{Lineage UUID}} \text{Canonical Record} \xrightarrow{\text{Citation}} \text{Investigator Finding}$$
* **Verbatim Preservation of Original Timestamps:** Even when timestamps are parsed into ISO-8601 UTC, the system preserves `original_timestamp` and `original_timezone` verbatim. Timestamps are never fabricated; partial dates retain explicit precision (`YEAR`, `MONTH`, `DAY`) and missing dates are flagged `TimestampStatus.MISSING`.
* **Verbatim Content Preservation:** Textual messages, call notes, and user entries are preserved verbatim without truncation or editorial alteration.
* **Strict Quality Auditing:** If coordinates or values violate physical constraints (e.g. latitude $> 90^\circ$), the record is retained with `DataQualityStatus.INVALID` and detailed `ValidationWarning` structures—it is never silently discarded or clamped.
* **Bidirectional Audit Trail API:** Every canonical record includes its source `raw_artifact_id`. The endpoint `GET /cases/{case_id}/canonical-records/{record_id}/raw` allows defense counsel and forensic auditors to inspect the exact un-normalized XML fragment extracted from the device dump.

---

## 3. Grounded AI & Non-Hallucination Mandate

### 3.1 The Evidence Database is the Absolute Source of Truth
* Large Language Models (LLMs) are used strictly as **contextual reasoning and summarization engines**, never as knowledge sources for forensic facts.
* All AI answers must be synthesized exclusively from retrieved canonical evidence records passed into the inference context.

### 3.2 Citation Requirement
* Every factual claim made in an AI response must include an explicit citation back to the canonical artifact ID:
  > *"User +14155552671 sent message 'Package arrived' at 2024-05-18 14:22:10 UTC [Record: `8f8b1b5e-bdf3-4c91-a1e7-a0e4138e68ef`]."*
* If the underlying evidence records do not provide an answer, the AI engine is programmatically constrained to state:
  > *"The available forensic evidence in this case is insufficient to answer this inquiry."*

### 3.3 Prohibition of Fact Fabrication
Under no circumstance shall the system invent or infer beyond verified records:
* Fictional participants or aliases
* Fabricated timestamps or durations
* Synthesized message text or conversation threads
* Inferred physical locations without GPS/cell tower evidence

---

## 4. The Non-Autonomous Accusation Principle

```
               ┌────────────────────────────────────────────────────────┐
               │              CRITICAL ETHICAL & LEGAL RULE             │
               │                                                        │
               │  The system is an INVESTIGATIVE ASSISTANCE PLATFORM.   │
               │                                                        │
               │  It must NEVER autonomously declare that any person,   │
               │  phone number, or entity is GUILTY, CRIMINAL,          │
               │  MALICIOUS, or RESPONSIBLE for an offense.             │
               └────────────────────────────────────────────────────────┘
```

1. **Analytical Neutrality:** Analytical outputs (anomaly detection, graph centrality, communication bursts) must be characterized using objective, descriptive statistical terminology:
   * **Allowed:** *"Entity +14155550000 exhibited a statistical anomaly in message frequency on 2024-06-12 (Isolation Forest score: -0.32, z-score: 4.1)."*
   * **Prohibited:** *"Entity +14155550000 engaged in suspicious/criminal communication on 2024-06-12."*
2. **Human in the Loop:** All investigative findings, tags, and report conclusions are authored or formally ratified by licensed human investigators.
