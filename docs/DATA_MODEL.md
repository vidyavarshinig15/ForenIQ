# AI-Driven Intelligent UFDR Analysis System
## Canonical Forensic Data Model & Storage Schema

**Document Version:** 1.0.0  
**Classification:** Core Data Architecture Specification  
**Status:** Foundation Phase  

---

## 1. Design Rationale & Normalization Strategy

Mobile extractions (UFDR archives) produce polymorphic, proprietary, and deeply nested structures. Directly tying the platform's analytical, search, and graph algorithms to specific vendor schemas creates brittle, unmaintainable code.

The platform employs a **Canonical Evidence Model (CEM)**:
1. **Extraction Invariance:** Whether an artifact originated from Cellebrite UFED, Oxygen, XRY, or manual extraction, it normalizes into a consistent internal representation.
2. **Dual-Layer Persistence:**
   * **Relational Layer (PostgreSQL):** Stores uniform indexing metadata, relational associations, timestamps, actors, and custody links.
   * **Document Layer (MongoDB):** Stores the complete, raw, uncompromised payload for forensic completeness and deep artifact inspection.
3. **Immutability & Provenance:** Every normalized record retains pointers to its physical source file, archive offset, and verification hash.

---

## 2. Canonical Evidence Model (CEM) Specification

Every normalized forensic artifact across the platform conforms to the following conceptual structure:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CANONICAL EVIDENCE RECORD                       │
├────────────────────────────────────────────────────────────────────────┤
│ Identification:                                                        │
│   id                         : UUID (Primary Key)                      │
│   case_id                    : UUID (Foreign Key -> Case)              │
│   evidence_source_id         : UUID (Foreign Key -> EvidenceSource)    │
│   device_id                  : UUID / String (Device Reference)        │
│                                                                        │
│ Classification:                                                        │
│   artifact_type              : ArtifactType (CALL, MESSAGE, LOCATION..│
│   application                : String (e.g., "WhatsApp", "SMS")        │
│   source_system              : String (e.g., "Cellebrite_UFED_v7")     │
│                                                                        │
│ Temporal Attributes:                                                   │
│   timestamp_utc              : Timestamp (ISO 8601 UTC)                │
│   timestamp_precision        : TimestampPrecision (SEC, MILLI, APPROX) │
│   duration_seconds           : Optional[Float] (For calls/media)       │
│                                                                        │
│ Entity & Communication References:                                     │
│   sender_id                  : Optional[String] (Phone/Email/Account)  │
│   receiver_ids               : List[String] (List of participants)     │
│   direction                  : DirectionType (INCOMING, OUTGOING, NA)  │
│                                                                        │
│ Content & Geospatial:                                                  │
│   content_text               : Optional[Text] (Message body, query)    │
│   latitude                   : Optional[Float]                         │
│   longitude                  : Optional[Float]                         │
│   altitude                   : Optional[Float]                         │
│                                                                        │
│ Forensic Provenance & Integrity:                                       │
│   source_file_path           : String (Relative path in UFDR archive)  │
│   original_record_id         : String (Vendor/XML record ID)           │
│   sha256_hash                : String (SHA-256 of extracted record)    │
│   raw_document_id            : String (MongoDB ObjectId reference)     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Supported Artifact Types

The normalizer pipeline supports a modular, plugin-based hierarchy of forensic artifact types:

| Artifact Category | Canonical Type Enum | Example Sources | Core Specialized Fields |
| :--- | :--- | :--- | :--- |
| **Communication** | `CALL_RECORD` | Native Phone, WhatsApp, Signal | `call_type` (Audio, Video), `duration_sec`, `call_status` (Missed, Answered) |
| **Messaging** | `MESSAGE` | SMS, MMS, WhatsApp, Telegram, iMessage | `thread_id`, `attachments`, `read_status`, `deleted_flag` |
| **Contacts** | `CONTACT` | Address Book, SIM card, Google Sync | `display_name`, `phone_numbers`, `emails`, `organization` |
| **Geospatial** | `LOCATION_RECORD` | GPS logs, cell tower fixes, photo EXIF | `latitude`, `longitude`, `accuracy_meters`, `location_type` |
| **Web Activity** | `BROWSER_HISTORY` | Chrome, Safari, Firefox | `url`, `page_title`, `visit_count`, `search_term` |
| **System & Files** | `FILESYSTEM_METADATA` | File listings, APKs, downloads | `file_name`, `file_size_bytes`, `md5`, `sha256`, `creation_time` |
| **Temporal Events** | `CALENDAR_EVENT` | Device Calendars | `event_title`, `start_time`, `end_time`, `attendees` |
| **Application State** | `APP_USAGE` | Device usage stats, installed packages | `package_name`, `last_time_used`, `total_time_foreground` |

---

## 4. Database Strategy & Relational Schema (PostgreSQL)

```sql
-- Core Cases Table
CREATE TABLE cases (
    id UUID PRIMARY KEY,
    case_number VARCHAR(128) UNIQUE NOT NULL,
    title VARCHAR(256) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL
);

-- Users & Case Membership Table (RBAC)
CREATE TABLE users (
    id UUID PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(256) UNIQUE NOT NULL,
    hashed_password VARCHAR(256) NOT NULL,
    role VARCHAR(32) NOT NULL, -- Administrator, Investigator, Analyst, Viewer
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE case_members (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    role_in_case VARCHAR(32) NOT NULL, -- Lead, Contributor, ReadOnly
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    UNIQUE(case_id, user_id)
);

-- Evidence Sources (UFDR Archives & Images)
CREATE TABLE evidence_sources (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE NOT NULL,
    uploaded_by UUID REFERENCES users(id) NOT NULL,
    filename VARCHAR(512) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    sha256_hash CHAR(64) NOT NULL,
    device_name VARCHAR(256),
    device_imei VARCHAR(64),
    acquisition_date TIMESTAMP WITH TIME ZONE,
    upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    processing_status VARCHAR(32) NOT NULL -- QUEUED, PROCESSING, COMPLETED, FAILED
);

-- Canonical Artifact Index Table
CREATE TABLE canonical_artifacts (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE NOT NULL,
    evidence_source_id UUID REFERENCES evidence_sources(id) ON DELETE CASCADE NOT NULL,
    artifact_type VARCHAR(64) NOT NULL,
    application VARCHAR(128),
    timestamp_utc TIMESTAMP WITH TIME ZONE,
    timestamp_precision VARCHAR(16) DEFAULT 'EXACT',
    sender_ref VARCHAR(256),
    primary_receiver_ref VARCHAR(256),
    content_preview VARCHAR(1024),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    sha256_hash CHAR(64) NOT NULL,
    raw_document_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for Fast Investigative Filtering
CREATE INDEX idx_artifacts_case_time ON canonical_artifacts(case_id, timestamp_utc);
CREATE INDEX idx_artifacts_type ON canonical_artifacts(case_id, artifact_type);
CREATE INDEX idx_artifacts_sender ON canonical_artifacts(case_id, sender_ref);
CREATE INDEX idx_artifacts_receiver ON canonical_artifacts(case_id, primary_receiver_ref);

-- Forensic Audit Log (Append-Only)
CREATE TABLE forensic_audit_logs (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action_type VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(128),
    client_ip VARCHAR(45) NOT NULL,
    status VARCHAR(32) NOT NULL,
    timestamp_utc TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    details_hash CHAR(64) NOT NULL
);
```

---

## 5. Document Storage Schema (MongoDB)

Document collections capture complete raw structures. For example, in the `raw_artifacts` collection:

```json
{
  "_id": "ObjectId('66fa810bc931f185c8e31a29')",
  "canonical_id": "8f8b1b5e-bdf3-4c91-a1e7-a0e4138e68ef",
  "case_id": "7a3b4c12-3456-789a-bcde-f0123456789a",
  "evidence_source_id": "3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f",
  "artifact_type": "MESSAGE",
  "application": "WhatsApp",
  "raw_xml_node": "<Message id='WA-8849'><From>+14155552671</From><To>+14155559812</To><Body>Archive key is 9981</Body><Timestamp>2024-05-18T14:22:10Z</Timestamp></Message>",
  "parsed_payload": {
    "from": "+14155552671",
    "to": ["+14155559812"],
    "message_text": "Archive key is 9981",
    "status": "READ",
    "media_attachments": []
  },
  "extraction_metadata": {
    "archive_entry": "data/data/com.whatsapp/databases/msgstore.db",
    "parsed_by_module": "whatsapp_sqlite_plugin_v1"
  }
}
```

---

## 6. Data Integrity & Non-Duplication Rules

1. **Structured vs Unstructured Boundary:** High-cardinality search, temporal alignment, and graph adjacency are derived strictly from PostgreSQL canonical records. Full raw XML fragments and unstructured app blobs reside exclusively in MongoDB.
2. **Stable Deterministic Identifiers:** Artifact IDs are deterministic UUIDv5 hashes derived from `case_id + evidence_source_id + source_file_path + original_record_id`. Reprocessing an identical extraction produces identical canonical IDs without duplicate record explosion.
