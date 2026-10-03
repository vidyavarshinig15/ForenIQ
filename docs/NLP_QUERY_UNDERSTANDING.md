# Phase 11 — NLP Query Understanding, Entity Extraction & Investigation Intent

## Overview & Architecture

The Phase 11 NLP subsystem provides an investigator-facing natural language query understanding pipeline. It translates unstructured investigator inquiries into structured forensic investigation plans (`InvestigationQuery`) and delegates retrieval to the Phase 9/10 Forensic Search Engine (`ForensicSearchService`).

```
                    Natural Language Query
                             ↓
                    Input Validation
                             ↓
                    Text Normalization (NFKC + Sanitization)
                             ↓
                    Temporal Expression Extraction
                             ↓
                    Forensic Entity Extraction (Hybrid)
                             ↓
                    Intent Classification
                             ↓
                    Query Constraint Construction
                             ↓
                    Structured Investigation Plan
                             ↓
                    Phase 9/10 Forensic Retrieval Engine
                             ↓
                    Ranked Evidence Results
```

---

## 1. Pipeline Components

### A. Query Normalizer (`QueryNormalizer`)
- Unicode NFKC normalization and control character stripping.
- Safety length cap enforcement (`MAX_INVESTIGATION_QUERY_LENGTH = 500`).
- Null-byte and malicious escape sequence sanitization.

### B. Temporal Parser (`TemporalParser`)
- Relative expressions: `"yesterday"`, `"today"`, `"last week"`, `"this month"`, `"last month"`.
- Date ranges: `"between September 1 and September 5"`, `"from 2026-09-01 to 2026-09-05"`.
- Time ranges: `"between 10 PM and midnight"`, `"from 10:00 to 12:00"`.
- Boundary expressions: `"after 8 PM"`, `"before September 10"`, `"since 14:00"`.
- **Explicit Precision Tracking**: Preserves exact granularity (`DAY`, `HOUR`, `MINUTE`, `MONTH`) without inventing unwarranted sub-second precision.

### C. Forensic Entity Extractor (`ForensicEntityExtractor`)
- **Deterministic Patterns**:
  - `PHONE_NUMBER`: International and local number formats.
  - `EMAIL`: RFC 5322 compliant regex.
  - `URL`: Standard Web and IP URLs.
  - `DEVICE`: 15-digit IMEIs, MAC addresses, serial identifiers.
  - `ACCOUNT`: Social handles (e.g. `@alice_crypto`).
  - `APPLICATION`: WhatsApp, Telegram, Signal, Chrome, Safari, Gmail, etc.
  - `ARTIFACT_TYPE`: Messages, Calls, Contacts, Location, Browser, Filesystem.
- **NLP NER (spaCy `en_core_web_sm`)**:
  - Extracts `PERSON`, `LOCATION`, `ORGANIZATION`.
- **Canonical Normalization**:
  - Reuses Phase 7 canonical normalizers (`normalize_phone_number`, `normalize_email`, `normalize_application_name`).
- **Span Conflict Resolution**:
  - Resolves overlapping token spans using pattern priority and longest span matching.

### D. Intent Classifier (`InvestigationIntentClassifier`)
Categorizes queries into 9 configurable forensic intent classes:
1. `PERSON_LOOKUP`: Targeted inquiries for individuals, contacts, emails, or phone numbers.
2. `EVENT_RETRIEVAL`: Queries seeking timeline incidents, suspect events, or activity logs.
3. `COMMUNICATION_ANALYSIS`: Multi-party message/call exchanges and conversations.
4. `TEMPORAL_INVESTIGATION`: Time-centric inquiries ("What happened between 10 PM and midnight?").
5. `DEVICE_LOOKUP`: Queries targeting specific hardware, serials, IMEIs, or MAC addresses.
6. `LOCATION_LOOKUP`: Geographic coordinates, locations, and travel histories.
7. `APPLICATION_ACTIVITY`: Application-specific queries (e.g. WhatsApp chats, Chrome history).
8. `GENERAL_EVIDENCE_SEARCH`: General semantic or keyword evidence search.
9. `UNKNOWN`: Unclassifiable queries falling back to general search.

---

## 2. API Endpoints

### `POST /api/v1/cases/{case_id}/investigation/query`
Executes complete NLP understanding, retrieval, and audit logging.

**Request:**
```json
{
  "query": "Find WhatsApp messages sent by Rahul yesterday",
  "retrieval_mode": "AUTO",
  "page_size": 50,
  "include_facets": true
}
```

**Response:**
```json
{
  "query_id": "8f37a54b-d7d1-4db8-b570-5b565a0c8b32",
  "case_id": "4d5d3286-16f8-4b64-bf8d-6cac2761468e",
  "raw_query": "Find WhatsApp messages sent by Rahul yesterday",
  "interpretation": {
    "intent": {
      "type": "APPLICATION_ACTIVITY",
      "confidence": 0.92,
      "explanation": "Application-specific activity query for WhatsApp."
    },
    "entities": [
      {
        "type": "APPLICATION",
        "text": "WhatsApp",
        "normalized_value": "WhatsApp",
        "start_pos": 5,
        "end_pos": 13,
        "extraction_method": "LEXICON",
        "confidence": 0.95
      },
      {
        "type": "PERSON",
        "text": "Rahul",
        "normalized_value": "Rahul",
        "start_pos": 31,
        "end_pos": 36,
        "extraction_method": "RULE",
        "confidence": 0.90
      }
    ],
    "temporal_constraints": [
      {
        "start_time": "2026-10-02T00:00:00+00:00",
        "end_time": "2026-10-02T23:59:59.999999+00:00",
        "raw_text": "yesterday",
        "timezone": "UTC",
        "precision": "DAY"
      }
    ],
    "artifact_types": ["MESSAGE"],
    "filters": {
      "artifact_type": "MESSAGE",
      "application": "WhatsApp",
      "start_time": "2026-10-02T00:00:00+00:00",
      "end_time": "2026-10-02T23:59:59.999999+00:00"
    },
    "search_text": "Rahul",
    "recommended_mode": "HYBRID"
  },
  "retrieval_plan": {
    "mode": "HYBRID",
    "filters": {
      "artifact_type": "MESSAGE",
      "application": "WhatsApp"
    },
    "search_text": "Rahul",
    "recommended_mode": "HYBRID",
    "explanation": "Hybrid retrieval (Lexical + Semantic) recommended for optimal forensic precision and recall."
  },
  "results": [],
  "pagination": {
    "next_cursor": null,
    "has_more": false,
    "page_size": 50
  },
  "duration_ms": 14
}
```

### `POST /api/v1/cases/{case_id}/investigation/parse`
Transparency/preview endpoint returning the parsed `InvestigationQuery` without executing search.

---

## 3. Forensic Neutrality & Safety Principles

1. **Parser Confidence vs Guilt**: Confidence scores (0.0 – 1.0) represent language model and pattern recognition certainty. They strictly DO NOT represent guilt, suspicion, or truthfulness.
2. **Immutable Provenance**: Every retrieved result references the canonical record ID, raw artifact ID, evidence ID, source file, and chain of custody event.
3. **Multi-Tenant Isolation**: Case-level access controls prevent unauthorized cross-case query construction (IDOR protection).
4. **Offline / Air-Gapped Operation**: spaCy and SentenceTransformer run 100% locally with zero external API dependencies.
