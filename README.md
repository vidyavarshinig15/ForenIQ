# AI-Driven Intelligent UFDR Analysis System
### Advanced Digital Forensic Investigation Platform

[![Status: Foundation Phase](https://img.shields.io/badge/Status-Foundation%20Phase-blue.svg)](#)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-green.svg)](#)
[![License: Proprietary / Forensic Use](https://img.shields.io/badge/License-Proprietary-red.svg)](#)

---

## 1. Project Overview

The **AI-Driven Intelligent UFDR Analysis System** is an enterprise digital forensic investigation platform designed to ingest, process, normalize, correlate, index, search, and analyze very large Universal Forensic Data Extraction (UFDR) archives and mobile extractions.

Engineered to support millions of evidence records, the platform provides investigative teams with advanced semantic discovery, communication network graphs, timeline analysis, statistical anomaly detection, and grounded AI assistance while guaranteeing strict chain of custody, cryptographic evidence integrity, and full explainability.

> [!IMPORTANT]
> **Ethical & Legal Safeguard:** The system is an investigative assistance platform. It **never** autonomously declares that a person is guilty, criminal, malicious, or responsible for an offense. All AI findings must remain traceable and directly linked to underlying evidence records.

---

## 2. Core Development Principles

The engineering of this system strictly adheres to the ten foundational principles:

1. **Principle 1 — Evidence First:** The evidence database is the absolute source of truth.
2. **Principle 2 — Security First:** Never sacrifice security for convenience.
3. **Principle 3 — Scalable by Design:** Streaming and chunking architectures that scale to millions of records.
4. **Principle 4 — Modular:** Discrete boundaries separating API, workers, parsers, storage, and AI layers.
5. **Principle 5 — Traceable:** Every finding traces through: $\text{Evidence} \rightarrow \text{Artifact} \rightarrow \text{Record} \rightarrow \text{Analysis} \rightarrow \text{Finding} \rightarrow \text{Report}$.
6. **Principle 6 — Explainable:** Transparent citations and metrics explain why any analytical output or AI response was generated.
7. **Principle 7 — Reproducible:** Deterministic processing configurations yield identical results on identical evidence archives.
8. **Principle 8 — Failure Tolerant:** Single malformed XML nodes or damaged artifacts do not crash the case processing pipeline.
9. **Principle 9 — No Hallucinated Evidence:** AI models are constrained strictly to retrieved context; if evidence is absent, the system explicitly states it.
10. **Principle 10 — No Autonomous Accusations:** Human investigators evaluate facts; the system never outputs moral or criminal conclusions.

---

## 3. Architecture Overview

```
Evidence Upload (UFDR ZIP)
        │
        ▼
Validation & Cryptographic Hashing (SHA-256)
        │
        ▼
Background Processing Queue (Redis Broker)
        │
        ▼
Worker Cluster: Streaming Decompression & Iterative XML Parsing
        │
        ▼
Forensic Normalization to Canonical Evidence Model (CEM)
        │
        ├──────────────────────┬──────────────────────┐
        ▼                      ▼                      ▼
Relational Storage       Document Store         Search & Vector
(PostgreSQL)             (MongoDB)              (OpenSearch / FAISS)
- Cases & Members        - Raw XML Payloads     - Inverted Index
- Canonical Index        - Raw JSON States      - Semantic Embeddings
- Audit Trail Logs
        │
        ▼
Investigative Analysis Subsystems
- Timeline Engine (Chronological alignment)
- Communication Graph (Entity networks & centrality)
- Anomaly Detection (Isolation Forest statistical outliers)
- Grounded RAG (Provider-agnostic LLM with mandatory citations)
        │
        ▼
Investigator Workstation (React High-Density UI) & Court-Ready Forensic Reports
```

Comprehensive architecture details are available in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 4. Planned System Modules

* **`backend/`**: FastAPI REST API providing authentication, RBAC, case scoping, search brokerage, and audit log tracking.
* **`parser/`**: Pluggable extraction engines supporting UFDR, XML reports, and mobile database formats with strict ZipSlip and XXE safeguards.
* **`workers/`**: Asynchronous task workers executing chunked extraction, normalization, and indexing via Redis queues.
* **`database/`**: Polyglot storage abstraction managing PostgreSQL relational schemas and MongoDB document repositories.
* **`analytics/`**: Graph analysis (NetworkX), timeline aggregation, and statistical anomaly detection (Scikit-Learn Isolation Forest).
* **`ai/`**: Retrieval-Augmented Generation (RAG) pipeline with prompt injection defenses and strict citation enforcement.
* **`frontend/`**: High-density React workstation for forensic examiners (no toy dashboards; focused on tabular, timeline, and graph views).
* **`docs/`**: Forensic standards, data models, threat analysis, and development specifications.

---

## 5. Local Development Requirements

* **Operating System:** macOS Sonoma+ or Linux (Ubuntu 22.04+)
* **Python:** 3.11 or 3.12+ (Python 3.13 supported)
* **Node.js:** v20.0+ / npm v10.0+
* **PostgreSQL:** 16+ (Relational store)
* **MongoDB:** 7.0+ (Document store)
* **Redis:** 7.2+ (Task queue & caching broker)
* **Search / Vector:** OpenSearch 2.12+ / FAISS

---

## 6. Environment Configuration Overview

A template configuration is provided in `.env.example`:

```bash
# Copy the template to create your local environment file
cp .env.example .env
```

Key environment configurations include:
* `DATABASE_URL`: Connection string for PostgreSQL relational store.
* `MONGODB_URI`: Connection string for MongoDB raw artifact store.
* `REDIS_URL`: Connection string for Redis broker.
* `SECRET_KEY`: High-entropy 256-bit secret for signing JWT access tokens.
* `EVIDENCE_STORAGE_PATH`: Secure, non-executable volume for raw evidence archives.

---

## 7. Testing Strategy

Forensic software requires uncompromising test rigor:
* **Unit Tests:** Verify individual normalizers, parsing routines, and hash calculations.
* **Security Tests:** Rigorously test ZIP slip protection, XML entity expansion defense, and case-boundary access control.
* **Integration Tests:** Verify end-to-end database writes and queue-worker lifecycle.
* **Synthetic Datasets Only:** Automated tests execute exclusively against synthetically generated UFDR archives with known ground-truth networks, timestamps, and injected anomalies. Real private evidence is strictly prohibited in tests.

To run the test suite:
```bash
pytest
```

---

## 8. Documentation Index

Detailed specifications are maintained in the [`docs/`](docs/) directory:
* [Architecture Specification](docs/ARCHITECTURE.md)
* [Security & Threat Model](docs/SECURITY.md)
* [Canonical Data Model](docs/DATA_MODEL.md)
* [API Specifications](docs/API.md)
* [Developer Guide](docs/DEVELOPMENT.md)
* [Forensic Traceability & Ethics](docs/FORENSIC_TRACEABILITY.md)
