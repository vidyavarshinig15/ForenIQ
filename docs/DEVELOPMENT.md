# AI-Driven Intelligent UFDR Analysis System
## Developer Guide & Engineering Conventions

**Document Version:** 1.0.0  
**Classification:** Development & Engineering Standards  
**Status:** Foundation Phase  

---

## 1. Local Development Toolchain & Prerequisites

* **Operating System:** Linux (Ubuntu 22.04+ / Debian 12+) or macOS (Sonoma+)
* **Python Runtime:** Python 3.11+ (Python 3.13 supported)
* **Node Runtime:** Node.js v20+ / npm v10+
* **Primary Relational Store:** PostgreSQL 16+
* **Document Store:** MongoDB 7.0+
* **Message Broker & In-Memory Cache:** Redis 7.2+
* **Search / Vector Infrastructure:** OpenSearch 2.12+ (or Elasticsearch 8+) and FAISS / Qdrant

---

## 2. Project Directory Organization

```
ufdr/
├── backend/            # FastAPI application services, API routers, dependencies, config
├── workers/            # Background worker definitions, queue listeners, job orchestrators
├── parser/             # UFDR archive parser plugins, streaming decompressor, normalizers
├── analytics/          # Timeline aggregation, graph analysis (NetworkX), anomaly detectors
├── ai/                 # Grounded RAG orchestrator, LLM provider abstraction, embeddings
├── database/           # Relational schema (Alembic/PostgreSQL) and MongoDB ODM/connectors
├── frontend/           # React SPA application (TypeScript, forensic UI components)
├── tests/              # Comprehensive test suites
│   ├── unit/           # Unit tests (models, parsers, validators, utils)
│   ├── integration/    # Integration tests (DB persistence, worker queues, search)
│   └── security/       # Security tests (path traversal, XXE, auth, rate limiting)
├── docs/               # System specifications, threat models, API references
├── scripts/            # Development automation, synthetic dataset generators, migrations
└── infra/              # Docker Compose services, local development containers
```

---

## 3. Engineering Guidelines & Coding Standards

### 3.1 Python Conventions
* **Strict Type Annotations:** All production functions, methods, and API contracts must include Python 3.11+ type hints (`typing` / built-in generics).
* **Code Formatting & Linting:** Strict adherence to PEP 8 standards enforced via `ruff` and `black`.
* **Data Validation:** All external data representations, API bodies, and configuration parameters must be modeled using **Pydantic v2**.
* **Zero Hard-Coded Credentials:** All secrets, connection strings, and configuration toggles must be sourced via Pydantic `BaseSettings` reading environment variables.

### 3.2 Error Handling & Logging
* Never use bare `except:` clauses. Always catch specific domain exceptions.
* Use structured logging (`structlog` or standard library logging with JSON formatting).
* Never log raw passwords, authentication tokens, or private evidence contents.

---

## 4. Synthetic Forensic Datasets & Testing Strategy

### 4.1 Strict Policy on Real Evidence
* **Rule:** Never use real, private, or operational forensic evidence during development or automated testing.
* All testing must utilize **synthetic forensic datasets** generated specifically for testing purposes.

### 4.2 Synthetic Test Dataset Design
Test fixtures must simulate realistic UFDR XML/ZIP archives containing:
1. Known communication networks (e.g. 10 synthetic entities with known phone numbers).
2. Known chronological timelines (calls, messages, location coordinates with verified timestamps).
3. Injected anomalies (e.g., sudden burst of 500 messages at 03:00 AM, impossible geographic velocity).
4. Malicious test payloads (test ZIP slips, safe XXE payloads to verify parser defense rejection).

### 4.3 Testing Pyramid & Execution
```bash
# Execute unit test suite
pytest tests/unit

# Execute security validation tests
pytest tests/security

# Execute integration tests against test databases
pytest tests/integration
```

---

## 5. Git & Version Control Conventions

1. **Branch Naming:**
   * `feat/phase-<number>-<feature-description>`
   * `fix/<bug-description>`
   * `docs/<documentation-update>`
2. **Commit Messages:**
   Follow Conventional Commits:
   * `feat(parser): add streaming XML iterator for UFDR message nodes`
   * `fix(security): sanitize archive member path against path traversal`
   * `test(anomaly): add unit tests for Isolation Forest feature matrix`
3. **Commit Restrictions:**
   Never commit `.env`, binary extractions, or large synthetic archives to the repository.
