from fastapi import APIRouter

from backend.app.api.v1.endpoints import (
    anomalies,
    audit,
    auth,
    cases,
    evidence,
    graph,
    health,
    investigation,
    processing,
    rag,
    reports,
    search,
    timeline,
    users,
)

api_v1_router = APIRouter()

# Active Routers
api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(cases.router, prefix="/cases", tags=["Case Management"])
api_v1_router.include_router(evidence.router, prefix="/cases", tags=["Evidence Ingestion"])
api_v1_router.include_router(processing.router, prefix="/cases", tags=["Forensic Processing & Artifacts"])
api_v1_router.include_router(search.router, prefix="/cases", tags=["Forensic Search"])
api_v1_router.include_router(investigation.router, prefix="/cases", tags=["Investigation NLP & Intent"])
api_v1_router.include_router(rag.router, prefix="/cases", tags=["Evidence-Grounded RAG & Assistant"])
api_v1_router.include_router(graph.router, prefix="/cases", tags=["Communication Graph Analysis & SNA"])
api_v1_router.include_router(timeline.router, prefix="/cases/{case_id}/timeline", tags=["Timeline Analytics"])
api_v1_router.include_router(anomalies.router, prefix="/cases/{case_id}/anomalies", tags=["Anomaly Detection"])
api_v1_router.include_router(reports.router, prefix="/cases/{case_id}/reports", tags=["Forensic Report Generation & Export"])
api_v1_router.include_router(users.router, prefix="/users", tags=["User Management"])
api_v1_router.include_router(audit.router, prefix="/audit", tags=["Audit Trail"])

# ==============================================================================
# Planned Future Phase Route Inclusions:
# ==============================================================================
# Phase 4+:
# api_v1_router.include_router(search.router, prefix="/search", tags=["Search Subsystem"])
# api_v1_router.include_router(investigations.router, prefix="/investigations", tags=["Investigator Workspace"])
# api_v1_router.include_router(timeline.router, prefix="/timeline", tags=["Timeline Analytics"])
# api_v1_router.include_router(graph.router, prefix="/graph", tags=["Communication Graph"])
# api_v1_router.include_router(anomalies.router, prefix="/anomalies", tags=["Anomaly Detection"])
# api_v1_router.include_router(reports.router, prefix="/reports", tags=["Forensic Reports"])
# ==============================================================================
