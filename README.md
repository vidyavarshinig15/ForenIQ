# AI-Driven Intelligent UFDR Analysis System
### Advanced Digital Forensic Investigation Platform

[![Current Phase: Phase 2 Active](https://img.shields.io/badge/Current%20Phase-Phase%202%20Auth%20%26%20Cases-blue.svg)](#)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-green.svg)](#)
[![Frontend: React + TypeScript](https://img.shields.io/badge/Frontend-React%20%2B%20TS-cyan.svg)](#)
[![Security: Argon2id + JWT](https://img.shields.io/badge/Security-Argon2id%20%2B%20JWT-purple.svg)](#)
[![License: Proprietary / Forensic Use](https://img.shields.io/badge/License-Proprietary-red.svg)](#)

---

## 1. Project Overview & Purpose

The **AI-Driven Intelligent UFDR Analysis System** is an enterprise digital forensic investigation platform engineered to ingest, process, normalize, correlate, index, search, and analyze very large Universal Forensic Data Extraction (UFDR) archives and mobile extractions.

Engineered to support millions of evidence records, the platform provides investigative teams with advanced semantic discovery, communication network graphs, timeline analysis, statistical anomaly detection, and grounded AI assistance while guaranteeing strict chain of custody, cryptographic evidence integrity, and full explainability.

> [!IMPORTANT]
> **Ethical & Legal Safeguard:** The system is an investigative assistance platform. It **never** autonomously declares that a person is guilty, criminal, malicious, or responsible for an offense. All AI findings must remain traceable and directly linked to underlying evidence records.

---

## 2. Current Development Phase

**Active Phase:** `PHASE 2 — AUTHENTICATION, RBAC & CASE MANAGEMENT`

Phase 2 implements the core security, identity, and investigative boundary architecture:
1. **Cryptographic Authentication:** Password storage secured using **Argon2id** (`argon2-cffi`), JWT access token generation and validation, session revocation via `/auth/logout`, and brute-force protection with automated rate-limiting.
2. **User Identity & Normalized Accounts:** Strict case-insensitive email uniqueness, user role hierarchy (`ADMIN`, `INVESTIGATOR`, `ANALYST`, `VIEWER`), and initial administrator auto-bootstrap (`admin@ufdr.org`).
3. **Forensic Case Governance:** Full Case lifecycle management (`OPEN`, `IN_PROGRESS`, `CLOSED`, `ARCHIVED`), automated unique case numbering (`CASE-YYYY-XXXXXX`), and non-destructive soft archiving.
4. **Dual-Tier Authorization & IDOR Defense:** Enforces both system RBAC and explicit case membership (`CaseMember`). Unauthorized users cannot access or enumerate cases by ID.
5. **Tamper-Evident Audit Trail:** Append-only audit logger capturing all authentications, case operations, and authorization violations without leaking secrets.
6. **Relational Database Migrations:** SQLAlchemy 2.0 async engine with Alembic migration scripts.
7. **Examiner Workstation Frontend:** Interactive React interface with full `/login` screen, protected routes, Cases dashboard with search/filtering, and interactive Case Details page with member management.

---

## 3. High-Level Architecture

```
User (Examiner)
      │
      ▼
Perimeter Security & Auth Middleware [Phase 1-2]
 - Security Headers (nosniff, DENY, no-store)
 - Bearer JWT Token Verification
 - Brute-Force Rate Limiter
      │
      ▼
Dual-Tier Authorization Gate [Phase 2]
 ├── Tier 1: System RBAC (ADMIN, INVESTIGATOR, ANALYST, VIEWER)
 └── Tier 2: Case Scoping (CaseMember verification / IDOR Protection)
      │
      ▼
Application Layer [Phase 2]
 ├── AuthService (Argon2id Hashing, JWT Tokens, Logout)
 ├── CaseService (Case Numbering, Status Lifecycle, Membership)
 └── AuditService (Append-Only Event Trail)
      │
      ▼
Relational Database (SQLAlchemy + Alembic Migrations) [Phase 2]
 - users: Investigator identities & password hashes
 - cases: Organizational boundaries (CASE-YYYY-XXXXXX)
 - case_members: Explicit scoping grants
 - audit_logs: Tamper-evident forensic ledger
```

---

## 4. Local Development Setup

### 4.1 Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify backend:
```bash
curl http://localhost:8000/api/v1/health
# Response: {"status": "ok"}
```

API documentation: `http://localhost:8000/api/v1/docs`

### 4.2 Initial Development Credentials
A bootstrap administrator account is provisioned on initial launch:
* **Email:** `admin@ufdr.org`
* **Password:** `ForensicAdmin2026!`
* **Role:** `ADMIN`

### 4.3 Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Access the investigator workstation at `http://localhost:3000`.

---

## 5. Running Tests

```bash
# Run all backend tests (Phase 1 & Phase 2)
backend/.venv/bin/pytest backend/tests

# Run global foundation structure tests
backend/.venv/bin/pytest tests/unit

# Verify frontend production build
npm --prefix frontend run build
```

---

## 6. Current Limitations (Phase 2)

* **No Evidence Ingestion:** Parsing UFDR archives, streaming decompression, and raw file integrity hashing are scheduled for Phase 3.
* **No Document Store:** MongoDB raw artifact payload storage will be introduced in Phase 3.
* **No Background Worker Cluster:** Redis queues and worker tasks will be established in Phase 3.
* **No Search or Analytics Subsystems:** Vector search, timeline analytics, and communication graphs are scheduled for Phases 4–5.

---

## 7. Upcoming Roadmap

* **Phase 3:** Secure Evidence Ingestion, Streaming ZIP Decompression, Iterative XML Parser, and MongoDB Storage
* **Phase 4:** Search Subsystem (Inverted Index + Vector Embeddings) and Unified Timeline Analysis
* **Phase 5:** Communication Graph Analysis, Isolation Forest Anomaly Detection, and Investigator Workspace
* **Phase 6:** Evidence-Grounded RAG and Court-Ready Forensic Reporting
