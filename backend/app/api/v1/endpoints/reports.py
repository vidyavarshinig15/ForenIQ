import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_db
from backend.app.models.enums import AuditAction, ReportStatus, ReportType
from backend.app.models.user import User
from backend.app.reports.export_service import export_service
from backend.app.reports.job_manager import report_job_manager
from backend.app.reports.report_service import report_service
from backend.app.schemas.report import (
    ForensicReportDocument,
    ReportCreateRequest,
    ReportJobStatusResponse,
    ReportListSummary,
    ReportUpdateRequest,
)
from backend.app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ForensicReportDocument, status_code=status.HTTP_201_CREATED)
async def generate_forensic_report(
    case_id: UUID,
    request: ReportCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ForensicReportDocument:
    """
    Generate an evidence-grounded forensic investigation report document.
    """
    return await report_service.generate_report(
        case_id=case_id,
        request=request,
        current_user=current_user,
        session=session,
    )


@router.get("", response_model=List[ReportListSummary], status_code=status.HTTP_200_OK)
async def list_case_reports(
    case_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> List[ReportListSummary]:
    """
    List all generated reports and drafts for the specified case.
    """
    return await report_service.list_reports(
        case_id=case_id,
        current_user=current_user,
        session=session,
    )


@router.get("/{report_id}", response_model=ForensicReportDocument, status_code=status.HTTP_200_OK)
async def get_report_details(
    case_id: UUID,
    report_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ForensicReportDocument:
    """
    Retrieve full structured forensic report document.
    """
    return await report_service.get_report(
        case_id=case_id,
        report_id=report_id,
        current_user=current_user,
        session=session,
    )


@router.put("/{report_id}", response_model=ForensicReportDocument, status_code=status.HTTP_200_OK)
async def update_report_details(
    case_id: UUID,
    report_id: str,
    request: ReportUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ForensicReportDocument:
    """
    Update report title, analyst notes, or advance review status (increments report version).
    """
    return await report_service.update_report(
        case_id=case_id,
        report_id=report_id,
        request=request,
        current_user=current_user,
        session=session,
    )


@router.post("/{report_id}/approve", response_model=ForensicReportDocument, status_code=status.HTTP_200_OK)
async def approve_forensic_report(
    case_id: UUID,
    report_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ForensicReportDocument:
    """
    Approve report document for court export (sets status to APPROVED).
    """
    return await report_service.approve_report(
        case_id=case_id,
        report_id=report_id,
        current_user=current_user,
        session=session,
    )


@router.get("/{report_id}/export/json", status_code=status.HTTP_200_OK)
async def export_report_json(
    case_id: UUID,
    report_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Export report document as machine-readable JSON with SHA-256 cryptographic digest.
    """
    doc = await report_service.get_report(case_id, report_id, current_user, session)
    json_str, content_hash = export_service.export_as_json(doc)

    audit_service = AuditService(session)
    await audit_service.record_event(
        action=AuditAction.REPORT_EXPORTED.value if hasattr(AuditAction.REPORT_EXPORTED, "value") else str(AuditAction.REPORT_EXPORTED),
        resource_type="forensic_report",
        status="SUCCESS",
        user_id=current_user.id,
        resource_id=report_id,
        case_id=case_id,
        details={"format": "JSON", "sha256": content_hash},
    )

    return Response(
        content=json_str,
        media_type="application/json",
        headers={
            "X-Report-SHA256": content_hash,
            "Content-Disposition": f'attachment; filename="{report_id}.json"',
        },
    )


@router.get("/{report_id}/export/pdf", status_code=status.HTTP_200_OK)
async def export_report_pdf(
    case_id: UUID,
    report_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Export report document as court-ready PDF with embedded SHA-256 signature.
    """
    doc = await report_service.get_report(case_id, report_id, current_user, session)
    pdf_bytes, pdf_hash = export_service.export_as_pdf(doc)

    audit_service = AuditService(session)
    await audit_service.record_event(
        action=AuditAction.REPORT_EXPORTED.value if hasattr(AuditAction.REPORT_EXPORTED, "value") else str(AuditAction.REPORT_EXPORTED),
        resource_type="forensic_report",
        status="SUCCESS",
        user_id=current_user.id,
        resource_id=report_id,
        case_id=case_id,
        details={"format": "PDF", "sha256": pdf_hash, "file_size": len(pdf_bytes)},
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "X-Report-SHA256": pdf_hash,
            "Content-Disposition": f'attachment; filename="{report_id}.pdf"',
        },
    )


@router.get("/{report_id}/export/csv", status_code=status.HTTP_200_OK)
async def export_report_csv(
    case_id: UUID,
    report_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Export report timeline as CSV.
    """
    doc = await report_service.get_report(case_id, report_id, current_user, session)
    csv_str = export_service.export_timeline_as_csv(doc)

    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{report_id}_timeline.csv"',
        },
    )


@router.post("/jobs", response_model=ReportJobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_report_generation_job(
    case_id: UUID,
    request: ReportCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ReportJobStatusResponse:
    """
    Submit an asynchronous report generation job for large cases.
    """
    job = report_job_manager.create_job(case_id)
    report_job_manager.update_progress(job.job_id, "GENERATING", 0.3)
    try:
        doc = await report_service.generate_report(case_id, request, current_user, session)
        job = report_job_manager.update_progress(
            job.job_id,
            "COMPLETED",
            1.0,
            report_id=doc.report_id,
            report=doc,
        )
    except Exception as e:
        logger.exception("Report job %s failed", job.job_id)
        job = report_job_manager.update_progress(
            job.job_id,
            "FAILED",
            0.0,
            error_message=str(e),
        )
    return job


@router.get("/jobs/{job_id}", response_model=ReportJobStatusResponse, status_code=status.HTTP_200_OK)
async def get_report_job_status(
    case_id: UUID,
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> ReportJobStatusResponse:
    """
    Poll status of an asynchronous report generation job.
    """
    job = report_job_manager.get_job(job_id=job_id, case_id=case_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found for case '{case_id}'.",
        )
    return job
