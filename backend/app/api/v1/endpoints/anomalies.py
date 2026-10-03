import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.anomalies.anomaly_service import anomaly_service
from backend.app.anomalies.job_manager import anomaly_job_manager
from backend.app.api.deps import get_current_user, get_db
from backend.app.models.enums import JobStatus
from backend.app.models.user import User
from backend.app.schemas.timeline_anomaly import (
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    AnomalyJobStatusResponse,
    AnomalyResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/detect", response_model=AnomalyDetectionResponse, status_code=status.HTTP_200_OK)
async def detect_timeline_anomalies(
    case_id: UUID,
    request: AnomalyDetectionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AnomalyDetectionResponse:
    """
    Execute statistical anomaly detection (Isolation Forest / Z-score) across case timeline.
    Outputs evidence-grounded anomaly scores with full context and baseline comparisons.
    """
    return await anomaly_service.detect_anomalies(
        case_id=case_id,
        request=request,
        current_user=current_user,
        session=session,
    )


@router.get("/{anomaly_id}", response_model=AnomalyResult, status_code=status.HTTP_200_OK)
async def get_anomaly_details(
    case_id: UUID,
    anomaly_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AnomalyResult:
    """
    Retrieve full factual breakdown and supporting canonical evidence IDs for a specific anomaly.
    """
    anomaly = await anomaly_service.get_anomaly_details(
        case_id=case_id,
        anomaly_id=anomaly_id,
        current_user=current_user,
        session=session,
    )
    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly '{anomaly_id}' not found in case '{case_id}'.",
        )
    return anomaly


@router.post("/jobs", response_model=AnomalyJobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_anomaly_analysis_job(
    case_id: UUID,
    request: AnomalyDetectionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AnomalyJobStatusResponse:
    """
    Submit an asynchronous anomaly analysis job for large forensic cases.
    """
    job = anomaly_job_manager.create_job(case_id)
    # Execute synchronous computation in handler and update job for fast turnaround
    anomaly_job_manager.update_progress(job.job_id, JobStatus.RUNNING, 0.2)
    try:
        resp = await anomaly_service.detect_anomalies(
            case_id=case_id,
            request=request,
            current_user=current_user,
            session=session,
        )
        job = anomaly_job_manager.update_progress(
            job.job_id,
            JobStatus.COMPLETED,
            1.0,
            total_windows=resp.total_windows_analyzed,
            anomalies_found=resp.anomalies_detected,
            result=resp,
        )
    except Exception as e:
        logger.exception("Anomaly job %s failed", job.job_id)
        job = anomaly_job_manager.update_progress(
            job.job_id,
            JobStatus.FAILED,
            0.0,
            error_message=str(e),
        )
    return job


@router.get("/jobs/{job_id}", response_model=AnomalyJobStatusResponse, status_code=status.HTTP_200_OK)
async def get_anomaly_job_status(
    case_id: UUID,
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> AnomalyJobStatusResponse:
    """
    Poll status of an asynchronous anomaly detection job.
    """
    job = anomaly_job_manager.get_job(job_id=job_id, case_id=case_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found for case '{case_id}'.",
        )
    return job
