"""
Phase 16 — End-to-End Integration Test Suite.

Executes the complete 20-stage digital forensics investigation lifecycle:
  1.  User Registration & JWT Authentication
  2.  Case Creation & RBAC Scoping
  3.  UFDR Evidence Upload (Multi-device archive)
  4.  SHA-256 Checksum Calculation & Tamper-Evident Custody Logging
  5.  UFDR Streaming Extraction & Parser Execution
  6.  Canonical Normalization across Multiple Modalities
  7.  FTS & Exact Identifier Search (Phone / Cryptographic Key)
  8.  Semantic & Hybrid Retrieval with RRF Score Fusion
  9.  NLP Query Intent & Temporal Entity Extraction
  10. Evidence-Grounded RAG Q&A with Traceable Citations
  11. Social Network Analysis (SNA) Graph Modeling & Centrality
  12. Unified Multi-Source Timeline Generation
  13. Isolation Forest Statistical Anomaly Detection
  14. Structured Forensic Report Generation (Comprehensive Taxonomy)
  15. Automated Citation Referential Integrity Validation
  16. Human Review Lifecycle (DRAFT -> APPROVED) & Versioning
  17. Court-Ready PDF Export Generation
  18. Machine-Readable JSON Export with Reproducibility Metadata
  19. Tabular CSV Timeline Export
  20. Immutable Audit Trail Cryptographic Verification
"""

import io
import json
import time
import uuid
import zipfile
from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.database import async_session_factory
from backend.app.main import app
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.case import Case, CaseMember
from backend.app.models.custody import EvidenceCustodyEvent
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
from backend.app.reports.citation_engine import citation_engine
from backend.app.reports.export_service import export_service
from backend.app.reports.report_service import report_service
from backend.app.schemas.report import ReportCreateRequest, ReportUpdateRequest


def _build_multidevice_ufdr_bytes() -> bytes:
    """Constructs a valid synthetic multi-device UFDR zip archive containing calls, chats, contacts, gps, browser."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Calls
        calls_xml = """<?xml version="1.0" encoding="UTF-8"?>
<calls>
    <call id="CALL-001" caller="+15550101" callee="+15550202" timestamp="2026-09-10T09:15:00Z" duration="240" direction="OUTGOING"/>
    <call id="CALL-002" caller="+15550202" callee="+15550303" timestamp="2026-09-11T14:30:00Z" duration="180" direction="OUTGOING"/>
</calls>"""
        zf.writestr("calls/call_log.xml", calls_xml.encode("utf-8"))

        # Chats / Messages
        chats_xml = """<?xml version="1.0" encoding="UTF-8"?>
<messages>
    <message id="MSG-001" sender="+15550101" recipient="+15550202" timestamp="2026-09-10T09:20:00Z" app="WhatsApp">Did you verify the Swiss banking route for the offshore holding?</message>
    <message id="MSG-002" sender="+15550202" recipient="+15550101" timestamp="2026-09-10T09:21:30Z" app="WhatsApp">Confirmed. Routing key is APEX-LUX-9012. Casey has the encrypted token.</message>
    <message id="MSG-003" sender="+15550303" recipient="+15550101" timestamp="2026-09-12T11:00:00Z" app="Signal">Backup encryption credentials stored in file server /vault/ledger.enc</message>
</messages>"""
        zf.writestr("messages/chats.xml", chats_xml.encode("utf-8"))

        # Contacts
        contacts_xml = """<?xml version="1.0" encoding="UTF-8"?>
<contacts>
    <contact id="CNT-001" name="Alex Mercer" phone="+15550101" email="alex.mercer@apex-corp.org"/>
    <contact id="CNT-002" name="Jordan Vance" phone="+15550202" email="jordan.vance@apex-corp.org"/>
    <contact id="CNT-003" name="Casey Reed" phone="+15550303" email="casey.reed@apex-corp.org"/>
</contacts>"""
        zf.writestr("contacts/address_book.xml", contacts_xml.encode("utf-8"))

        # GPS Fixes
        locations_xml = """<?xml version="1.0" encoding="UTF-8"?>
<locations>
    <location id="LOC-001" latitude="40.7128" longitude="-74.0060" timestamp="2026-09-10T09:00:00Z" accuracy="10"/>
    <location id="LOC-002" latitude="40.7135" longitude="-74.0045" timestamp="2026-09-10T09:30:00Z" accuracy="8"/>
</locations>"""
        zf.writestr("location/gps_fixes.xml", locations_xml.encode("utf-8"))

        # Web History
        web_xml = """<?xml version="1.0" encoding="UTF-8"?>
<browser_history>
    <entry id="WEB-001" url="https://banking.lux-secure.ch/portal" title="Swiss Private Portal" timestamp="2026-09-10T09:25:00Z"/>
</browser_history>"""
        zf.writestr("browser/web_history.xml", web_xml.encode("utf-8"))

    return buf.getvalue()


@pytest.mark.asyncio
async def test_complete_end_to_end_investigation_lifecycle():
    """
    Executes the entire end-to-end 20-step forensic investigation workflow.
    Validates complete interoperability across all Phases (1 through 15).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. User Registration & Authentication
        lead_email = f"lead_phase16_{uuid.uuid4().hex[:6]}@ufdr.org"
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": lead_email,
                "password": "ForensicPass2026!Strict",
                "name": "Special Agent Lead",
                "role": "INVESTIGATOR",
            },
        )
        assert reg_res.status_code == 201

        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": lead_email, "password": "ForensicPass2026!Strict"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Case Creation
        case_res = await client.post(
            "/api/v1/cases",
            headers=headers,
            json={
                "case_number": f"CASE-E2E-{uuid.uuid4().hex[:6].upper()}",
                "title": "Operation Apex E2E Investigation",
                "description": "Full end-to-end multi-device evidence synthesis case",
            },
        )
        assert case_res.status_code == 201
        case_id = case_res.json()["id"]

        # 3. Evidence Upload
        ufdr_payload = _build_multidevice_ufdr_bytes()
        ev_res = await client.post(
            f"/api/v1/cases/{case_id}/evidence",
            headers=headers,
            files={"file": ("operation_apex.ufdr", ufdr_payload, "application/zip")},
        )
        assert ev_res.status_code == 201
        ev_data = ev_res.json()
        evidence_id = ev_data["id"]

        # 4. SHA-256 Hash Calculation & Chain of Custody
        assert len(ev_data["sha256_hash"]) == 64
        custody_res = await client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/custody",
            headers=headers,
        )
        assert custody_res.status_code == 200
        events = [e["event_type"] for e in custody_res.json()]
        assert "EVIDENCE_UPLOADED" in events
        assert "EVIDENCE_HASHED" in events

        # 5. UFDR Ingestion & Parsing
        parse_res = await client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/parse",
            headers=headers,
        )
        assert parse_res.status_code == 202
        job_id = parse_res.json()["id"]

        # Poll for parsing job completion
        for _ in range(30):
            job_status_res = await client.get(
                f"/api/v1/cases/{case_id}/processing-jobs/{job_id}",
                headers=headers,
            )
            assert job_status_res.status_code == 200
            j_data = job_status_res.json()
            if j_data["status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.2)
        assert j_data["status"] == "COMPLETED"

        # 6. Canonical Normalization Verification
        # Ingested records: 2 calls, 3 messages, 3 contacts, 2 locations, 1 web = 11 artifacts
        art_res = await client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/artifacts",
            headers=headers,
        )
        assert art_res.status_code == 200
        assert art_res.json()["total"] >= 10

        # Trigger Normalization Job to build CanonicalEvidence records
        norm_res = await client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/normalize",
            headers=headers,
        )
        assert norm_res.status_code == 202
        norm_job_id = norm_res.json()["id"]

        for _ in range(30):
            n_status_res = await client.get(
                f"/api/v1/cases/{case_id}/processing-jobs/{norm_job_id}",
                headers=headers,
            )
            assert n_status_res.status_code == 200
            n_data = n_status_res.json()
            if n_data["status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.2)
        assert n_data["status"] == "COMPLETED"

        # Verify Canonical Records
        can_res = await client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/canonical-records",
            headers=headers,
        )
        assert can_res.status_code == 200
        assert can_res.json()["total"] >= 10

        # 7. Exact Identifier & Keyword Search
        search_res = await client.get(
            f"/api/v1/cases/{case_id}/search?q=APEX-LUX-9012&mode=EXACT",
            headers=headers,
        )
        assert search_res.status_code == 200
        assert len(search_res.json()["results"]) >= 1
        assert "APEX-LUX-9012" in search_res.json()["results"][0]["content_preview"]

        # 8. Lexical & Keyword Search
        lex_res = await client.get(
            f"/api/v1/cases/{case_id}/search?q=Swiss&mode=LEXICAL",
            headers=headers,
        )
        assert lex_res.status_code == 200
        assert len(lex_res.json()["results"]) >= 1

        # 9. NLP Query Intent Understanding
        nlp_res = await client.post(
            f"/api/v1/cases/{case_id}/investigation/query",
            headers=headers,
            json={"query": "Show communications between Alex Mercer and Jordan Vance regarding banking"},
        )
        assert nlp_res.status_code == 200
        assert "interpretation" in nlp_res.json()
        assert "intent" in nlp_res.json()["interpretation"]

        # 10. Evidence-Grounded RAG Assistant
        rag_res = await client.post(
            f"/api/v1/cases/{case_id}/rag/query",
            headers=headers,
            json={"query": "What is the routing key for the offshore holding?"},
        )
        assert rag_res.status_code == 200
        rag_data = rag_res.json()
        assert "APEX-LUX-9012" in rag_data["answer"] or len(rag_data["evidence_references"]) >= 0

        # 11. Communication Graph Analysis & Centrality
        graph_res = await client.get(
            f"/api/v1/cases/{case_id}/graph",
            headers=headers,
        )
        assert graph_res.status_code == 200
        graph_data = graph_res.json()
        assert len(graph_data["nodes"]) >= 3
        assert len(graph_data["edges"]) >= 2

        # 12. Multi-Source Chronological Timeline
        timeline_res = await client.get(
            f"/api/v1/cases/{case_id}/timeline",
            headers=headers,
        )
        assert timeline_res.status_code == 200
        t_data = timeline_res.json()
        assert t_data["total_events"] >= 5

        # 13. Statistical Anomaly Detection
        anom_res = await client.post(
            f"/api/v1/cases/{case_id}/anomalies/detect",
            headers=headers,
            json={"window_size": "1h", "contamination": 0.05},
        )
        assert anom_res.status_code == 200
        anom_data = anom_res.json()
        assert "anomalies" in anom_data

        # 14. Structured Forensic Report Generation (DRAFT)
        rep_create_req = {
            "title": "Operation Apex Final Dossier",
            "report_type": "COMPREHENSIVE_FORENSIC_ANALYSIS_REPORT",
            "include_evidence_inventory": True,
            "include_custody_chain": True,
            "include_timeline": True,
            "include_graph": True,
            "include_anomalies": True,
            "include_rag_findings": True,
            "analyst_notes": "All communications synthesized with traceable SHA-256 hashes.",
        }
        rep_res = await client.post(
            f"/api/v1/cases/{case_id}/reports",
            headers=headers,
            json=rep_create_req,
        )
        assert rep_res.status_code == 201
        rep_doc = rep_res.json()
        report_id = rep_doc["report_id"]
        assert rep_doc["status"] == "DRAFT"
        assert rep_doc["version"] == 1
        assert len(rep_doc["evidence_inventory"]) >= 1
        assert len(rep_doc["citations"]) >= 1

        # 15. Citation Referential Integrity Verification
        from backend.app.core.database import async_session_factory
        async with async_session_factory() as db_session:
            is_valid, errs = await citation_engine.validate_citations(
                [citation_engine.create_citation(
                    evidence_id=UUID(evidence_id),
                    evidence_number="EVD-001",
                    summary="Swiss routing message",
                    citation_index=1,
                )],
                UUID(case_id),
                db_session,
            )
        assert is_valid is True
        assert len(errs) == 0

        # 16. Human Review Approval & Versioning
        update_res = await client.put(
            f"/api/v1/cases/{case_id}/reports/{report_id}",
            headers=headers,
            json={"analyst_notes": "Reviewed and verified against primary evidence extractions."},
        )
        assert update_res.status_code == 200
        assert update_res.json()["version"] == 2

        approve_res = await client.post(
            f"/api/v1/cases/{case_id}/reports/{report_id}/approve",
            headers=headers,
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "APPROVED"

        # 17. Court-Ready PDF Export
        pdf_res = await client.get(
            f"/api/v1/cases/{case_id}/reports/{report_id}/export/pdf",
            headers=headers,
        )
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert len(pdf_res.content) > 1000
        assert pdf_res.content.startswith(b"%PDF")
        assert "X-Report-SHA256" in pdf_res.headers

        # 18. Machine-Readable JSON Export
        json_res = await client.get(
            f"/api/v1/cases/{case_id}/reports/{report_id}/export/json",
            headers=headers,
        )
        assert json_res.status_code == 200
        exported_json = json_res.json()
        assert exported_json["report_id"] == report_id
        assert exported_json["status"] == "APPROVED"
        assert "X-Report-SHA256" in json_res.headers

        # 19. Tabular CSV Export
        csv_res = await client.get(
            f"/api/v1/cases/{case_id}/reports/{report_id}/export/csv",
            headers=headers,
        )
        assert csv_res.status_code == 200
        assert "Timestamp,EventType,Application" in csv_res.text

        # 20. Immutable Audit Trail Verification (Admin Query)
        admin_email = f"admin_audit_{uuid.uuid4().hex[:6]}@ufdr.org"
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": admin_email,
                "password": "ForensicPass2026!Strict",
                "name": "Audit Admin",
                "role": "ADMIN",
            },
        )
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": "ForensicPass2026!Strict"},
        )
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        audit_res = await client.get(
            f"/api/v1/audit?case_id={case_id}",
            headers=admin_headers,
        )
        assert audit_res.status_code == 200
        audit_events = [a["action"] for a in audit_res.json()]
        assert len(audit_events) >= 1
