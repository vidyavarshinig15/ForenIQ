# Phase 10 — Semantic Search & Hybrid Retrieval

## 1. Overview
Phase 10 introduces the natural-language and vector similarity retrieval foundation for the AI-Driven Intelligent UFDR Analysis System. It builds on Phase 9's structured filtering and lexical search engine, combining dense semantic representations with lexical token matching into a unified, evidence-grounded hybrid ranker.

```
                         Investigator Query
                                 │
                                 ▼
                         Search API Router
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
        Lexical Retrieval                Semantic Retrieval
    (Full-text & Token Index)            (Sentence-BERT & FAISS)
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
                       Hybrid Ranker (RRF & Linear)
                                 │
                                 ▼
                       Ranked Evidence Cards
                                 │
                                 ▼
                     Forensic Source Citations
```

## 2. Core Principles
1. **Evidence Grounding**: Retrieval results always return actual canonical evidence records (`CanonicalEvidence`), retaining provenance links (`evidence_id`, `raw_artifact_id`, `source_file`, `record_identifier`).
2. **No Speculative Conclusions**: Semantic similarity scores represent distance in dense vector space (0.0 to 1.0) and are **never** presented as probabilities of guilt, innocence, or malicious intent.
3. **Strict Case Isolation**: Vector searches and index partitions are scoped strictly per case (`case_id`), preventing cross-case vector leakage.
4. **Air-Gapped / Local Execution**: All embeddings are computed locally using SentenceTransformer on CPU/GPU without transmitting evidentiary data to external third-party cloud APIs.

## 3. Search Modes

| Search Mode | Engine / Logic | Primary Use Case |
| :--- | :--- | :--- |
| **`EXACT`** | Exact field matches (`record_identifier`, `application`, `device_id`) | Looking up specific identifiers, numbers, or hashes |
| **`LEXICAL`** | PostgreSQL ILIKE / BM25 keyword matching across text and metadata | Specific known keywords, error strings, file paths |
| **`SEMANTIC`** | Dense vector similarity via Sentence-BERT (`all-MiniLM-L6-v2`) and FAISS | Natural-language conceptual queries (e.g. "discussing travel plans") |
| **`HYBRID`** | Weighted fusion of Lexical + Dense Semantic + Exact Match Boost | Default investigator search combining keyword accuracy with conceptual discovery |

## 4. REST API Endpoints

### Search Evidence
```http
GET /api/v1/cases/{case_id}/search?q={query}&mode={mode}&artifact_type={type}&page_size=50
```

#### Query Parameters
- `q`: Search query string (up to 500 characters).
- `mode`: `EXACT`, `LEXICAL`, `SEMANTIC`, `HYBRID` (Default: `LEXICAL`).
- `artifact_type`: Filter by artifact type (`MESSAGE`, `CALL`, `CONTACT`, etc.).
- `application`: Filter by application name (e.g. `WhatsApp`, `Signal`).
- `device_id`: Filter by physical or logical device ID.
- `start_date` / `end_date`: ISO 8601 timestamp range filter.
- `cursor`: Base64 cursor for high-performance zero-offset pagination.

#### Sample Response
```json
{
  "results": [
    {
      "id": "c0000000-0000-0000-0000-000000000001",
      "artifact_type": "MESSAGE",
      "event_timestamp": "2026-09-30T14:30:00Z",
      "timestamp_precision": "SECOND",
      "application": "WhatsApp",
      "device_id": "dev_pixel_9",
      "content_preview": "Let's arrange a meeting tomorrow at 3 PM near the coffee shop downtown.",
      "matched_entities": [
        {"type": "LOCATION", "value": "coffee shop downtown"},
        {"type": "DATE", "value": "tomorrow at 3 PM"}
      ],
      "data_quality_status": "VALID",
      "match_type": "HYBRID_MATCH",
      "similarity_score": 0.8842,
      "retrieval_explanation": "Matched via Hybrid: Lexical relevance (1.00) + Semantic similarity (0.77)",
      "source": {
        "evidence_id": "e0000000-0000-0000-0000-000000000001",
        "raw_artifact_id": "a0000000-0000-0000-0000-000000000001",
        "source_file": "whatsapp_messages.db",
        "source_path": "/raw/whatsapp_messages.db",
        "record_identifier": "msg_wa_101"
      }
    }
  ],
  "facets": {
    "by_artifact_type": { "MESSAGE": 2, "BROWSER": 1 },
    "total_matched": 3
  },
  "pagination": {
    "next_cursor": null,
    "has_more": false,
    "page_size": 50
  },
  "search_mode": "HYBRID",
  "duration_ms": 12
}
```

### Embedding Index Management
- `GET /api/v1/cases/{case_id}/embeddings/stats`: Vector index counts, model provenance, and coverage percentage.
- `POST /api/v1/cases/{case_id}/embeddings/generate`: Enqueue background worker to generate embeddings for unembedded canonical records.
- `POST /api/v1/cases/{case_id}/embeddings/rebuild`: Enqueue full atomic rebuild of the case's vector index.
