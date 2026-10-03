# Phase 10 — Embedding Generation Pipeline & Provenance

## 1. Embedding Model Specifications

- **Model Name**: `all-MiniLM-L6-v2` (Sentence-BERT architecture)
- **Model Version**: `2.0.0`
- **Embedding Dimension**: `384` (float32 vector)
- **Normalization**: Unit L2-normalized ($||v||_2 = 1.0$)
- **Language Support**: English (multilingual extension via `paraphrase-multilingual-MiniLM-L12-v2`)
- **License**: Apache 2.0 (permissive, suitable for commercial/forensic environments)
- **RAM / Memory Footprint**: ~120MB on disk, ~350MB RAM when loaded in process memory
- **Execution Target**: CPU-optimized (Apple Silicon / Intel / AMD) with CUDA auto-detection when NVIDIA GPU is present.

## 2. Textual Representation & Formatter
Forensic canonical records (`CanonicalEvidence`) are deterministically structured prior to vector embedding to focus solely on high-value retrieval signals:

```
Artifact Type: MESSAGE
Application: WhatsApp
Timestamp: 2026-09-30T14:30:00Z
Device: dev_pixel_9
Source File: whatsapp_messages.db
Content: Let's arrange a meeting tomorrow at 3 PM near the coffee shop downtown.
Entities: LOCATION: coffee shop downtown, DATE: tomorrow at 3 PM
Sender: +1555123456
Receiver: +1555987654
```

### Staleness Detection & Content Hashing
Every generated embedding retains a deterministic SHA-256 hash of the exact formatted text:
```
content_hash = SHA256(canonical_formatted_string)
```
When canonical evidence records undergo normalization updates or reprocessing, the embedding pipeline detects `current_content_hash != record.content_hash` and marks the embedding status as `STALE`, queueing automatic re-generation.

## 3. Embedding Database Schema (`evidence_embeddings`)

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID (PK) | Unique record embedding identifier |
| `canonical_evidence_id` | UUID (FK) | Reference to `canonical_evidence.id` (1:1 per model version) |
| `case_id` | UUID (FK) | Case isolation boundary |
| `model_name` | VARCHAR(100) | Configured embedding model (e.g. `all-MiniLM-L6-v2`) |
| `model_version` | VARCHAR(50) | Embedding model semantic version |
| `dimension` | INTEGER | Vector length (384) |
| `content_hash` | VARCHAR(64) | SHA-256 hash of formatted text |
| `status` | ENUM | `NOT_GENERATED`, `QUEUED`, `GENERATING`, `READY`, `STALE`, `FAILED`, `NOT_EMBEDDABLE` |
| `error_message` | TEXT | Diagnostics if embedding failed |
| `created_at` / `updated_at` | TIMESTAMPTZ | Creation and last updated timestamps |

## 4. Asynchronous Queue Processing
- Managed by Phase 6 `JobWorker` architecture under `JobType.EMBEDDING`.
- Streaming batch reads (default: 64 records/batch) with checkpointing.
- Graceful error isolation: unparseable or blank records marked `NOT_EMBEDDABLE` without terminating the batch.
