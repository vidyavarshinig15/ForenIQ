# Backend Service - AI-Driven Intelligent UFDR Analysis System

This directory contains the FastAPI core backend service for the forensic investigation platform.

## Architecture & Directory Layout

```
backend/
├── app/
│   ├── main.py              # Application entrypoint, middleware, lifespan
│   ├── core/                # Configuration, logging, errors, security headers
│   ├── api/v1/              # Versioned API routes (health, auth, cases, etc.)
│   ├── models/              # Foundational domain entities
│   ├── schemas/             # Pydantic validation schemas
│   ├── services/            # Business logic and coordination layer
│   ├── repositories/        # Data access contracts and implementations
│   └── utils/               # Shared utilities
├── tests/                   # Backend test suite (pytest)
├── requirements.txt         # Production and development dependencies
└── README.md
```

## Local Development Setup

### 1. Create and Activate Virtual Environment
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Development Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Run Test Suite
```bash
pytest
```

## Active Endpoints in Phase 1
* `GET /api/v1/health` - Operational health check endpoint (`{"status": "ok"}`)
* `GET /api/v1/docs` - OpenAPI documentation (in development mode)
