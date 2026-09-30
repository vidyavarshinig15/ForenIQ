from fastapi import APIRouter

from backend.app.api.v1.endpoints import audit, auth, cases, health, users

api_v1_router = APIRouter()

# Phase 1 & 2 Active Routers
api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(cases.router, prefix="/cases", tags=["Case Management"])
api_v1_router.include_router(users.router, prefix="/users", tags=["User Management"])
api_v1_router.include_router(audit.router, prefix="/audit", tags=["Audit Trail"])

# ==============================================================================
# Planned Future Phase Route Inclusions:
# ==============================================================================
# Phase 3+:
# api_v1_router.include_router(evidence.router, prefix="/evidence", tags=["Evidence Management"])
# api_v1_router.include_router(search.router, prefix="/search", tags=["Search Subsystem"])
# api_v1_router.include_router(investigations.router, prefix="/investigations", tags=["Investigator Workspace"])
# api_v1_router.include_router(timeline.router, prefix="/timeline", tags=["Timeline Analytics"])
# api_v1_router.include_router(graph.router, prefix="/graph", tags=["Communication Graph"])
# api_v1_router.include_router(anomalies.router, prefix="/anomalies", tags=["Anomaly Detection"])
# api_v1_router.include_router(reports.router, prefix="/reports", tags=["Forensic Reports"])
# ==============================================================================
