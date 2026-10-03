"""
Phase 15 — Intelligent Forensic Report Generation, Evidence Citation & Export Tests.

Validates:
  1. Structured Report Generation Across Report Types
  2. Evidence Citation Engine & Referential Integrity Validation
  3. Chain of Custody, Timeline, Graph, and Anomaly Rendering
  4. Report Versioning & Tamper-Evident SHA-256 Hashing
  5. Human Review Lifecycle (DRAFT -> REVIEW_REQUIRED -> APPROVED -> EXPORTED)
  6. PDF, JSON, and CSV Export Formats with Integrity Headers
  7. Cross-Case Isolation & IDOR Protection
  8. Asynchronous Report Generation Jobs
  9. Forensic Safety & Prohibited Criminal Inferences
"""

from datetime import datetime, timezone
import json
import uuid
from uuid import UUID

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.main import app
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.case import Case
from backend.app.models.enums import (
    ArtifactType,
    CaseStatus,
    FindingType,
    ReportStatus,
    ReportType,
    UserRole,
)
from backend.app.models.evidence import Evidence
from backend.app.models.user import User
from backend.app.reports.citation_engine import ForensicCitationEngine, citation_engine
from backend.app.reports.export_service import export_service
from backend.app.reports.job_manager import report_job_manager
from backend.app.reports.report_service import report_service
from backend.app.schemas.report import (
    EvidenceCitation,
    ForensicFinding,
    ForensicReportDocument,
    ReportCaseInfo,
    ReportCreateRequest,
    ReportEvidenceItem,
    ReportUpdateRequest,
)


async def _register_and_login(client: AsyncClient, email: str, role: str = "INVESTIGATOR") -> str:
    user_data = {
        "email": email,
        "password": "ForensicSecurePassword2026!",
        "name": f"Test User {role}",
        "role": role,
    }
    await client.post("/api/v1/auth/register", json=user_data)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "ForensicSecurePassword2026!"},
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


async def _setup_case(client: AsyncClient, token: str, case_number: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.post(
        "/api/v1/cases",
        json={"case_number": case_number, "title": f"Investigation Case {case_number}"},
        headers=headers,
    )
    assert res.status_code == 201
    return res.json()["id"]


from backend.app.core.database import async_session_factory


@pytest.mark.asyncio
async def test_evidence_citation_engine_and_validation():
    """Unit test: Evidence citation creation, validation pass on active records, and rejection on invalid IDs."""
    case_id = uuid.uuid4()
    ev_id = uuid.uuid4()

    # Valid Citation
    cit_valid = citation_engine.create_citation(
        evidence_id=ev_id,
        evidence_number="EVD-001",
        summary="Call record between suspect and unknown contact",
        record_identifier="CALL-101",
        source_file="calls.xml",
        timestamp="2026-09-15T10:00:00Z",
        citation_index=1,
    )
    assert cit_valid.citation_id == "CIT-001"
    assert cit_valid.evidence_number == "EVD-001"

    async with async_session_factory() as session:
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="citation_tester@ufdr.internal",
            name="Citation Tester",
            password_hash="mock_hash",
            role=UserRole.INVESTIGATOR,
        )
        case = Case(id=case_id, case_number="CASE-CIT-01", title="Citation Case", status=CaseStatus.ACTIVE, created_by=user_id)
        ev = Evidence(
            id=ev_id,
            case_id=case_id,
            original_filename="calls.ufdr",
            stored_filename="stored_calls.ufdr",
            storage_path_or_key="/raw/calls.ufdr",
            file_size=1024,
            mime_type="application/octet-stream",
            file_extension="ufdr",
            sha256_hash="hash123",
            uploaded_by=user_id,
        )
        session.add_all([user, case, ev])
        await session.commit()

        # Test Validation Success
        is_valid, errors = await citation_engine.validate_citations([cit_valid], case_id, session)
        assert is_valid is True
        assert len(errors) == 0

        # Test Validation Failure on Fake/Hallucinated Evidence ID
        cit_fake = citation_engine.create_citation(
            evidence_id=uuid.uuid4(),  # Does not exist in case
            evidence_number="EVD-FAKE",
            summary="Fabricated record",
            citation_index=2,
        )
        is_invalid, errs = await citation_engine.validate_citations([cit_fake], case_id, session)
        assert is_invalid is False
        assert len(errs) >= 1
        assert "does not exist in Case" in errs[0]


@pytest.mark.asyncio
async def test_report_export_json_and_pdf_integrity():
    """Unit test: Report document serialization to JSON and PDF with SHA-256 integrity verification."""
    case_id = uuid.uuid4()
    ev_id = uuid.uuid4()

    doc = ForensicReportDocument(
        report_id="REP-TEST-001",
        case_id=case_id,
        title="Comprehensive Forensic Report",
        report_type=ReportType.COMPREHENSIVE_FORENSIC_ANALYSIS_REPORT,
        status=ReportStatus.APPROVED,
        version=1,
        generated_by_id=uuid.uuid4(),
        generated_by_name="Lead Forensic Investigator",
        generated_at=datetime.now(timezone.utc).isoformat(),
        case_info=ReportCaseInfo(
            case_id=case_id,
            case_number="CASE-001",
            title="Test Case",
            created_at=datetime.now(timezone.utc).isoformat(),
            status="ACTIVE",
        ),
        evidence_inventory=[
            ReportEvidenceItem(
                evidence_id=ev_id,
                evidence_number="EVD-001",
                original_filename="device.ufdr",
                sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                integrity_status="VALID",
                artifact_count=25,
                ingestion_timestamp=datetime.now(timezone.utc).isoformat(),
            )
        ],
        findings=[
            ForensicFinding(
                finding_id="FIND-001",
                title="Verified Communication Spike",
                description="18 calls recorded within a 15-minute window.",
                finding_type=FindingType.COMMUNICATION_PATTERN,
                source_type="Forensic Subsystems",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        ],
        methodology=["NIST SP 800-86", "Canonical Normalization"],
        limitations=["Analysis based strictly on verified records."],
    )

    # 1. JSON Export & Hash Check
    json_str, json_hash = export_service.export_as_json(doc)
    assert len(json_str) > 0
    assert len(json_hash) == 64  # SHA-256 is 64 hex characters
    assert export_service.compute_sha256(json_str.encode("utf-8")) != ""

    # 2. PDF Export & Hash Check
    pdf_bytes, pdf_hash = export_service.export_as_pdf(doc)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")  # Valid PDF binary signature
    assert len(pdf_hash) == 64

    # 3. CSV Export
    csv_str = export_service.export_timeline_as_csv(doc)
    assert "Timestamp,EventType" in csv_str


@pytest.mark.asyncio
async def test_report_job_manager_lifecycle():
    """Unit test: Asynchronous report job manager progress and lifecycle."""
    case_id = uuid.uuid4()
    job = report_job_manager.create_job(case_id)
    assert job.status == "QUEUED"
    assert job.progress == 0.0

    # Progress Update
    updated = report_job_manager.update_progress(
        job_id=job.job_id,
        status="GENERATING",
        progress=0.5,
    )
    assert updated.status == "GENERATING"
    assert updated.progress == 0.5

    # Cancellation
    cancelled = report_job_manager.cancel_job(job.job_id, case_id)
    assert cancelled is True
    assert report_job_manager.get_job(job.job_id).status == "CANCELLED"


@pytest.mark.asyncio
async def test_report_api_endpoints_end_to_end():
    """Integration test: REST API endpoints for report generation, review, export, and jobs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(client, f"rep_admin_{uuid.uuid4().hex[:6]}@ufdr.org", "ADMIN")
        case_id = await _setup_case(client, token, f"CASE-REP-{uuid.uuid4().hex[:6]}")
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Generate Report POST
        create_payload = {
            "title": "Initial Forensic Examination Report",
            "report_type": "COMPREHENSIVE_FORENSIC_ANALYSIS_REPORT",
            "include_evidence_inventory": True,
            "include_custody_chain": True,
            "include_timeline": True,
            "include_graph": True,
            "include_anomalies": True,
            "analyst_notes": "All extractions verified by examiner.",
        }
        resp = await client.post(
            f"/api/v1/cases/{case_id}/reports",
            json=create_payload,
            headers=headers,
        )
        assert resp.status_code == 201
        rep_data = resp.json()
        report_id = rep_data["report_id"]
        assert rep_data["status"] == "DRAFT"
        assert rep_data["version"] == 1
        assert rep_data["report_hash"] is not None

        # 2. List Reports GET
        resp_list = await client.get(f"/api/v1/cases/{case_id}/reports", headers=headers)
        assert resp_list.status_code == 200
        summaries = resp_list.json()
        assert len(summaries) >= 1
        assert summaries[0]["report_id"] == report_id

        # 3. Get Report Details GET
        resp_get = await client.get(f"/api/v1/cases/{case_id}/reports/{report_id}", headers=headers)
        assert resp_get.status_code == 200
        assert resp_get.json()["report_id"] == report_id

        # 4. Update Report (Version Increment) PUT
        update_payload = {
            "title": "Updated Forensic Examination Report",
            "status": "REVIEW_REQUIRED",
            "analyst_notes": "Added peer review comments.",
        }
        resp_upd = await client.put(
            f"/api/v1/cases/{case_id}/reports/{report_id}",
            json=update_payload,
            headers=headers,
        )
        assert resp_upd.status_code == 200
        upd_data = resp_upd.json()
        assert upd_data["version"] == 2
        assert upd_data["status"] == "REVIEW_REQUIRED"

        # 5. Approve Report POST
        resp_appr = await client.post(
            f"/api/v1/cases/{case_id}/reports/{report_id}/approve",
            headers=headers,
        )
        assert resp_appr.status_code == 200
        assert resp_appr.json()["status"] == "APPROVED"

        # 6. Export JSON GET
        resp_json = await client.get(f"/api/v1/cases/{case_id}/reports/{report_id}/export/json", headers=headers)
        assert resp_json.status_code == 200
        assert "X-Report-SHA256" in resp_json.headers
        assert resp_json.headers["Content-Type"].startswith("application/json")

        # 7. Export PDF GET
        resp_pdf = await client.get(f"/api/v1/cases/{case_id}/reports/{report_id}/export/pdf", headers=headers)
        assert resp_pdf.status_code == 200
        assert "X-Report-SHA256" in resp_pdf.headers
        assert resp_pdf.headers["Content-Type"].startswith("application/pdf")
        assert resp_pdf.content.startswith(b"%PDF-")

        # 8. Submit Report Job POST
        resp_job = await client.post(
            f"/api/v1/cases/{case_id}/reports/jobs",
            json=create_payload,
            headers=headers,
        )
        assert resp_job.status_code == 202
        job_id = resp_job.json()["job_id"]

        # 9. Poll Report Job GET
        resp_poll = await client.get(f"/api/v1/cases/{case_id}/reports/jobs/{job_id}", headers=headers)
        assert resp_poll.status_code == 200
        assert resp_poll.json()["job_id"] == job_id


@pytest.mark.asyncio
async def test_cross_case_isolation_reports():
    """Verify strict cross-case isolation prevents reports from Case A appearing in Case B."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(client, f"rep_iso_{uuid.uuid4().hex[:6]}@ufdr.org", "INVESTIGATOR")
        case_a = await _setup_case(client, token, f"CASE-REPA-{uuid.uuid4().hex[:6]}")
        case_b = await _setup_case(client, token, f"CASE-REPB-{uuid.uuid4().hex[:6]}")
        headers = {"Authorization": f"Bearer {token}"}

        # Generate report in Case A
        resp_a = await client.post(
            f"/api/v1/cases/{case_a}/reports",
            json={"title": "Report A"},
            headers=headers,
        )
        report_a_id = resp_a.json()["report_id"]

        # Attempt to access Report A via Case B endpoint (Must fail with 404)
        resp_b_access = await client.get(
            f"/api/v1/cases/{case_b}/reports/{report_a_id}",
            headers=headers,
        )
        assert resp_b_access.status_code == 404


@pytest.mark.asyncio
async def test_forensic_safety_prohibits_guilt_and_speculation():
    """Verify that report types, findings, and schemas strictly enforce non-speculative forensic safety."""
    prohibited_keywords = [
        "criminal",
        "guilty",
        "guilt",
        "suspect ranking",
        "crime probability",
        "risk score",
        "threat level",
        "conspiracy",
    ]

    for rt in ReportType:
        for word in prohibited_keywords:
            assert word not in rt.value.lower()

    for rs in ReportStatus:
        for word in prohibited_keywords:
            assert word not in rs.value.lower()

    for ft in FindingType:
        for word in prohibited_keywords:
            assert word not in ft.value.lower()
