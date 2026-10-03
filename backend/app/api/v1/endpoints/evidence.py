from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_client_ip, get_current_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.custody import (
    CustodyChainVerificationResult,
    EvidenceCustodyEventResponse,
    IntegrityVerificationResult,
)
from backend.app.schemas.evidence import EvidenceResponse
from backend.app.services.custody_service import CustodyService
from backend.app.services.evidence_service import EvidenceService
from backend.app.services.integrity_service import IntegrityService

router = APIRouter()



@router.post(
    "/{case_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Forensic Evidence",
    description=(
        "Streams and stores an incoming UFDR/ZIP forensic evidence archive. "
        "Calculates SHA-256 hash in-flight, validates archive integrity, defends against "
        "ZipSlip and ZipBomb vulnerabilities, and persists immutable evidence metadata."
    ),
)
async def upload_evidence(
    case_id: UUID,
    request: Request,
    file: UploadFile = File(..., description="Forensic archive (.ufdr or .zip)"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EvidenceResponse:
    client_ip = get_client_ip(request)
    evidence_service = EvidenceService(session)
    return await evidence_service.upload_evidence(
        current_user=current_user,
        case_id=case_id,
        file=file,
        client_ip=client_ip,
    )


@router.get(
    "/{case_id}/evidence",
    response_model=List[EvidenceResponse],
    status_code=status.HTTP_200_OK,
    summary="List Case Evidence",
    description="Lists all forensic evidence archives associated strictly with the authorized case.",
)
async def list_case_evidence(
    case_id: UUID,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> List[EvidenceResponse]:
    client_ip = get_client_ip(request)
    evidence_service = EvidenceService(session)
    return await evidence_service.list_evidence(
        current_user=current_user,
        case_id=case_id,
        skip=skip,
        limit=limit,
        client_ip=client_ip,
    )


@router.get(
    "/{case_id}/evidence/{evidence_id}",
    response_model=EvidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Evidence Details",
    description="Retrieves forensic metadata for a specific evidence item with IDOR protection.",
)
async def get_evidence_details(
    case_id: UUID,
    evidence_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EvidenceResponse:
    client_ip = get_client_ip(request)
    evidence_service = EvidenceService(session)
    return await evidence_service.get_evidence(
        current_user=current_user,
        case_id=case_id,
        evidence_id=evidence_id,
        client_ip=client_ip,
    )


@router.delete(
    "/{case_id}/evidence/{evidence_id}",
    response_model=EvidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Quarantine Evidence",
    description=(
        "Performs a controlled status transition to QUARANTINED. "
        "Original evidence files are preserved immutably for forensic integrity."
    ),
)
async def quarantine_evidence(
    case_id: UUID,
    evidence_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EvidenceResponse:
    client_ip = get_client_ip(request)
    evidence_service = EvidenceService(session)
    return await evidence_service.quarantine_evidence(
        current_user=current_user,
        case_id=case_id,
        evidence_id=evidence_id,
        client_ip=client_ip,
    )


@router.get(
    "/{case_id}/evidence/{evidence_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download Evidence Archive",
    description="Streams the original forensic evidence archive to authorized investigators with verification headers.",
)
async def download_evidence(
    case_id: UUID,
    evidence_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    client_ip = get_client_ip(request)
    evidence_service = EvidenceService(session)
    stream, evidence = await evidence_service.get_download_stream(
        current_user=current_user,
        case_id=case_id,
        evidence_id=evidence_id,
        client_ip=client_ip,
    )

    headers = {
        "Content-Disposition": f'attachment; filename="{evidence.original_filename}"',
        "X-Evidence-SHA256": evidence.sha256_hash or "",
        "Content-Length": str(evidence.file_size),
    }

    return StreamingResponse(
        stream,
        media_type=evidence.detected_mime_type or evidence.mime_type or "application/octet-stream",
        headers=headers,
    )


@router.post(
    "/{case_id}/evidence/{evidence_id}/verify-integrity",
    response_model=IntegrityVerificationResult,
    status_code=status.HTTP_200_OK,
    summary="Verify Evidence Cryptographic Integrity",
    description=(
        "Streams the stored physical evidence archive, recalculates its SHA-256 digest in-flight, "
        "and compares against recorded baseline. If mismatched or missing, marks status and emits tamper events."
    ),
)
async def verify_evidence_integrity(
    case_id: UUID,
    evidence_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> IntegrityVerificationResult:
    client_ip = get_client_ip(request)
    integrity_service = IntegrityService(session)
    return await integrity_service.verify_evidence_integrity(
        case_id=case_id,
        evidence_id=evidence_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get(
    "/{case_id}/evidence/{evidence_id}/custody",
    response_model=List[EvidenceCustodyEventResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Evidence Chain of Custody",
    description="Retrieves the append-only, chronologically ordered chain of custody for the specified evidence.",
)
async def get_evidence_custody_history(
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> List[EvidenceCustodyEventResponse]:
    # Enforce case authorization check
    evidence_service = EvidenceService(session)
    await evidence_service._verify_case_and_membership(case_id, current_user, required_upload=False)

    custody_service = CustodyService(session)
    return await custody_service.list_events(case_id=case_id, evidence_id=evidence_id)


@router.get(
    "/{case_id}/evidence/{evidence_id}/verify-custody-chain",
    response_model=CustodyChainVerificationResult,
    status_code=status.HTTP_200_OK,
    summary="Verify Custody Hash Chain",
    description="Recalculates cryptographic hashes across sequential custody events and verifies previous-event linkage.",
)
async def verify_custody_chain(
    case_id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CustodyChainVerificationResult:
    # Enforce case authorization check
    evidence_service = EvidenceService(session)
    await evidence_service._verify_case_and_membership(case_id, current_user, required_upload=False)

    custody_service = CustodyService(session)
    return await custody_service.verify_custody_chain(
        case_id=case_id,
        evidence_id=evidence_id,
        current_user_id=current_user.id,
    )

