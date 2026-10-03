# ForenIQ

**AI-Driven Intelligent UFDR Analysis System for Advanced Digital Forensic Investigations**

## Overview

ForenIQ is an AI-assisted digital forensic investigation platform designed to analyze Universal Forensic Data Extraction (UFDR) packages and mobile extractions. It enables forensic examiners and investigators to ingest, correlate, search, and review digital artifacts through evidence-grounded, verifiable analysis.

## Key Features

- **Secure Evidence Ingestion**: Streaming archive inspection with Zip-Slip traversal rejection and immutable storage.
- **Integrity & Chain of Custody**: Cryptographic SHA-256 baseline calculation and tamper-evident event ledger.
- **Multi-Modal Search**: Exact identifier matching, lexical full-text search, dense vector semantic search, and hybrid reciprocal rank fusion.
- **Natural-Language Investigation**: Multi-intent query understanding and named entity extraction.
- **Evidence-Grounded RAG Assistant**: Verifiable citation generation with strict hallucination safeguards.
- **Communication Graph Analysis**: Social Network Analysis (SNA), centrality metrics, and community detection.
- **Timeline & Anomaly Detection**: Chronological multi-source timeline and unsupervised temporal anomaly detection.
- **Evidence-Cited Forensic Reports**: Automated report builder with referential integrity validation and court-ready PDF, JSON, and CSV exports.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0 (AsyncIO), Pydantic v2
- **Database & Search**: PostgreSQL, SQLite, FAISS (Vector Index)
- **AI & Analytics**: Sentence-BERT (`all-MiniLM-L6-v2`), spaCy, NetworkX, Scikit-Learn (Isolation Forest)
- **Task Queue**: Redis Priority Queue / Asyncio Worker Pool
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, Vis-Network
- **Reporting**: ReportLab PDF Generation

## Getting Started

### 1. Environment Configuration
Copy the template configuration file:
```bash
cp .env.example .env
```
Update configuration parameters in `.env` as required for your deployment environment.

### 2. Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -c "import asyncio; from backend.app.core.database import init_db; asyncio.run(init_db())"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Access the web workstation at `http://localhost:5173`.

### 4. Running Tests & Evaluation
```bash
# Run backend test suite (200 tests)
pytest backend/tests/ -v

# Run end-to-end evaluation benchmark
python scripts/evaluate_phase16_end_to_end.py
```

## Security

ForenIQ is engineered as an investigative assistance system. Original evidence archives remain immutable and read-only. All case data, vector indices, and audit records enforce strict multi-tenant case isolation and Role-Based Access Control (RBAC).

## Disclaimer

ForenIQ provides analytical assistance and evidence correlation for authorized investigators. It does not make determinations of guilt, innocence, criminal intent, or legal conclusions. The human investigator remains responsible for evaluating and interpreting forensic evidence.
