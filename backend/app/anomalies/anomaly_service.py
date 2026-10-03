from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
import uuid
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.anomalies.baseline_detector import StatisticalBaselineDetector
from backend.app.anomalies.feature_extractor import TemporalFeatureExtractor
from backend.app.anomalies.isolation_forest_detector import ForensicIsolationForestDetector
from backend.app.anomalies.job_manager import anomaly_job_manager
from backend.app.core.config import settings
from backend.app.core.errors import ForensicAppException
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import AnomalyAlgorithm, AuditAction, BaselineType, JobStatus
from backend.app.models.user import User
from backend.app.repositories.case_repo import CaseRepository
from backend.app.schemas.timeline_anomaly import (
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    AnomalyResult,
    TimelineFilterRequest,
)
from backend.app.timeline.timeline_service import timeline_service

logger = logging.getLogger(__name__)


class AnomalyService:
    """
    Forensic Anomaly Detection Orchestrator.
    Executes case-scoped behavioral and temporal anomaly analysis, calculates statistical deviations,
    and returns evidence-grounded anomaly reports with complete audit logging.
    """

    def __init__(self):
        self._cached_analyses: Dict[str, AnomalyDetectionResponse] = {}

    async def detect_anomalies(
        self,
        case_id: UUID,
        request: AnomalyDetectionRequest,
        current_user: User,
        session: AsyncSession,
    ) -> AnomalyDetectionResponse:
        """
        Execute statistical anomaly detection pipeline over case timeline data.
        """
        start_time_proc = time.perf_counter()

        # 1. Validate Case Access
        case_repo = CaseRepository(session)
        case = await case_repo.get_by_id(case_id)
        if not case:
            raise ForensicAppException(
                message=f"Case '{case_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # 2. Query Timeline Events
        timeline_filter = TimelineFilterRequest(
            start_time=request.time_range.get("start") if request.time_range else None,
            end_time=request.time_range.get("end") if request.time_range else None,
            entity_value=request.target_entity,
            device_id=request.target_device,
            applications=[request.target_application] if request.target_application else None,
            limit=10000,
        )
        timeline_resp = await timeline_service.get_timeline(
            case_id=case_id,
            filter_params=timeline_filter,
            current_user=current_user,
            session=session,
        )

        all_events = timeline_resp.events
        evidence_id_map: Dict[str, UUID] = {ev.event_id: ev.evidence_id for ev in all_events}

        # 3. Slice into Analysis Windows
        explicit_start = request.time_range.get("start") if request.time_range else None
        explicit_end = request.time_range.get("end") if request.time_range else None

        analysis_windows = TemporalFeatureExtractor.slice_into_windows(
            timeline_events=all_events,
            window_size=request.window_size,
            explicit_start=explicit_start,
            explicit_end=explicit_end,
        )

        # 4. Determine Baseline Windows
        if request.baseline_type == BaselineType.PREVIOUS_PERIOD and request.baseline_range:
            base_filter = TimelineFilterRequest(
                start_time=request.baseline_range.get("start"),
                end_time=request.baseline_range.get("end"),
                entity_value=request.target_entity,
                device_id=request.target_device,
                limit=10000,
            )
            base_resp = await timeline_service.get_timeline(
                case_id=case_id,
                filter_params=base_filter,
                current_user=current_user,
                session=session,
            )
            baseline_windows = TemporalFeatureExtractor.slice_into_windows(
                timeline_events=base_resp.events,
                window_size=request.window_size,
                explicit_start=request.baseline_range.get("start"),
                explicit_end=request.baseline_range.get("end"),
            )
        else:
            # Default: Case-wide baseline
            baseline_windows = analysis_windows

        # 5. Compute Baseline Statistical Profile
        baseline_profile = TemporalFeatureExtractor.compute_baseline_profile(baseline_windows)

        # 6. Execute Anomaly Detection Model
        if request.algorithm == AnomalyAlgorithm.ISOLATION_FOREST:
            detector = ForensicIsolationForestDetector(
                n_estimators=settings.ANOMALY_N_ESTIMATORS,
                contamination=request.contamination,
                random_state=settings.ANOMALY_RANDOM_SEED,
                score_threshold=request.score_threshold,
            )
            anomalies = detector.detect_anomalies(
                case_id=case_id,
                analysis_windows=analysis_windows,
                baseline_windows=baseline_windows,
                baseline_profile=baseline_profile,
                evidence_id_map=evidence_id_map,
            )
        else:
            z_detector = StatisticalBaselineDetector(z_threshold=2.5)
            anomalies = z_detector.detect_anomalies(
                case_id=case_id,
                analysis_windows=analysis_windows,
                baseline_profile=baseline_profile,
                evidence_id_map=evidence_id_map,
            )

        elapsed_ms = (time.perf_counter() - start_time_proc) * 1000.0
        analysis_id = f"analysis_{case_id}_{uuid.uuid4().hex[:8]}"

        response = AnomalyDetectionResponse(
            case_id=case_id,
            analysis_id=analysis_id,
            status="COMPLETED",
            window_size=request.window_size.value if hasattr(request.window_size, "value") else str(request.window_size),
            algorithm=request.algorithm.value if hasattr(request.algorithm, "value") else str(request.algorithm),
            total_windows_analyzed=len(analysis_windows),
            anomalies_detected=len(anomalies),
            anomalies=anomalies,
            baseline_summary=baseline_profile,
            model_metadata={
                "contamination": request.contamination,
                "score_threshold": request.score_threshold,
                "total_events_evaluated": len(all_events),
                "execution_time_ms": round(elapsed_ms, 2),
                "version": settings.ANOMALY_VERSION,
            },
        )

        self._cached_analyses[analysis_id] = response

        # 7. Record Audit Trail
        from backend.app.services.audit_service import AuditService
        audit_service = AuditService(session)
        await audit_service.record_event(
            action=AuditAction.ANOMALY_DETECTION_EXECUTED.value if hasattr(AuditAction.ANOMALY_DETECTION_EXECUTED, "value") else str(AuditAction.ANOMALY_DETECTION_EXECUTED),
            resource_type="anomaly_detection",
            status="SUCCESS",
            user_id=current_user.id,
            resource_id=analysis_id,
            case_id=case_id,
            details={
                "analysis_id": analysis_id,
                "algorithm": str(request.algorithm),
                "window_size": str(request.window_size),
                "total_windows": len(analysis_windows),
                "anomalies_found": len(anomalies),
                "execution_time_ms": round(elapsed_ms, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return response

    async def get_anomaly_details(
        self,
        case_id: UUID,
        anomaly_id: str,
        current_user: User,
        session: AsyncSession,
    ) -> Optional[AnomalyResult]:
        """Look up a specific detected anomaly across cached analyses for the case."""
        for resp in self._cached_analyses.values():
            if resp.case_id == case_id:
                for anom in resp.anomalies:
                    if anom.anomaly_id == anomaly_id:
                        return anom
        return None


anomaly_service = AnomalyService()
