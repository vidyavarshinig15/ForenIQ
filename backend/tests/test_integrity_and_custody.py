import asyncio
import hashlib
import io
import json
import zipfile
import pytest
from uuid import UUID
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.database import async_session_factory
from backend.app.main import app
from backend.app.models.custody import EvidenceCustodyEvent
from backend.app.models.enums import CaseAccessRole, CustodyEventType, EvidenceStatus, IntegrityStatus
from backend.app.models.evidence import Evidence
from backend.app.services.storage.local import LocalStorageService

client = TestClient(app)


def get_token(email: str, password: str, name: str, role: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": name, "password": password, "role": role},
    )
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]


def create_minimal_test_zip(filename: str = "report.xml", content: bytes = b"<ufdr>data</ufdr>") -> bytes:
    """Helper creating a minimal valid ZIP archive in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename, content)
    return buf.getvalue()


def test_known_sha256_verification():
    """
    Test 1: Verify independent calculation matches in-flight server SHA-256
    and initial custody events are created in sequence.
    """
    token = get_token("integ_inv@test.org", "Password123!", "Officer Integrity", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {token}"}

    # Create case
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Integrity Baseline Case", "description": "SHA-256 test"},
        headers=headers,
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # Prepare known test file
    test_content = create_minimal_test_zip("manifest.xml", b"<forensics>verified_content</forensics>")
    expected_sha256 = hashlib.sha256(test_content).hexdigest()

    # Upload
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("evidence_known.ufdr", io.BytesIO(test_content), "application/octet-stream")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    ev_data = upload_res.json()
    evidence_id = ev_data["id"]
    assert ev_data["sha256_hash"] == expected_sha256
    assert ev_data["integrity_status"] == IntegrityStatus.VALID.value

    # Verify initial chain of custody events: UPLOADED (1), HASHED (2), VALIDATED (3)
    custody_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/custody",
        headers=headers,
    )
    assert custody_res.status_code == 200
    events = custody_res.json()
    assert len(events) >= 3
    assert events[0]["sequence_number"] == 1
    assert events[0]["event_type"] == CustodyEventType.EVIDENCE_UPLOADED.value
    assert events[1]["sequence_number"] == 2
    assert events[1]["event_type"] == CustodyEventType.EVIDENCE_HASHED.value
    assert events[1]["metadata"]["sha256"] == expected_sha256
    assert events[2]["sequence_number"] == 3
    assert events[2]["event_type"] == CustodyEventType.EVIDENCE_VALIDATED.value

    # Verify custody chain cryptographic validity
    verify_chain_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify-custody-chain",
        headers=headers,
    )
    assert verify_chain_res.status_code == 200
    chain_info = verify_chain_res.json()
    assert chain_info["status"] == "VALID"
    assert chain_info["events_checked"] >= 3


def test_modified_file_mismatch_detection():
    """
    Test 2: Tampering simulation. When a stored file is altered on disk:
    - Integrity check returns MISMATCH.
    - Stored baseline hash is NOT overwritten.
    - Evidence status transitions to QUARANTINED.
    - Custody event INTEGRITY_MISMATCH is recorded.
    """
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ufdr.org", "password": "ForensicAdmin2026!"},
    )
    token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create case
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Tamper Simulation Case", "description": "Modifying stored file"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    # Upload evidence
    original_zip = create_minimal_test_zip("device.xml", b"ORIGINAL_DEVICE_DATA")
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("tamper_test.ufdr", io.BytesIO(original_zip), "application/octet-stream")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    ev_data = upload_res.json()
    evidence_id = ev_data["id"]
    baseline_hash = ev_data["sha256_hash"]

    # Get evidence entity to locate file on disk
    async def get_storage_path():
        async with async_session_factory() as session:
            query = select(Evidence).where(Evidence.id == UUID(evidence_id))
            res = await session.execute(query)
            return res.scalars().first().storage_path_or_key


    storage_path = asyncio.run(get_storage_path())
    storage = LocalStorageService()
    physical_path = storage.get_absolute_path_for_validation(storage_path)

    # SIMULATE DISK TAMPERING: alter bytes on disk directly
    with open(physical_path, "wb") as f:
        f.write(b"CORRUPTED_TAMPERED_CONTENT_IN_STORAGE")

    # Execute On-Demand Integrity Verification
    verify_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify-integrity",
        headers=headers,
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.json()

    assert verify_data["match"] is False
    assert verify_data["integrity_status"] == IntegrityStatus.MISMATCH.value
    assert verify_data["stored_hash"] == baseline_hash
    assert verify_data["calculated_hash"] != baseline_hash

    # Re-fetch from DB: verify baseline hash preserved and status is QUARANTINED
    details_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}",
        headers=headers,
    )
    details = details_res.json()
    assert details["sha256_hash"] == baseline_hash  # CRITICAL: Baseline preserved
    assert details["integrity_status"] == IntegrityStatus.MISMATCH.value
    assert details["status"] == EvidenceStatus.QUARANTINED.value

    # Verify custody history contains INTEGRITY_MISMATCH
    custody_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/custody",
        headers=headers,
    )
    events = custody_res.json()
    mismatch_events = [e for e in events if e["event_type"] == CustodyEventType.INTEGRITY_MISMATCH.value]
    assert len(mismatch_events) == 1
    assert mismatch_events[0]["metadata"]["stored_hash"] == baseline_hash


def test_missing_file_detection():
    """
    Test 3: Missing storage file handling.
    - Integrity check marks MISSING.
    - Database record is preserved for investigation.
    """
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ufdr.org", "password": "ForensicAdmin2026!"},
    )
    headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Missing File Case", "description": "File disappears"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    test_zip = create_minimal_test_zip("notes.xml", b"SOME_DATA")
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("missing_test.zip", io.BytesIO(test_zip), "application/zip")},
        headers=headers,
    )
    evidence_id = upload_res.json()["id"]

    # Delete the stored file from disk
    async def get_storage_path():
        async with async_session_factory() as session:
            query = select(Evidence).where(Evidence.id == UUID(evidence_id))
            res = await session.execute(query)
            return res.scalars().first().storage_path_or_key

    storage_path = asyncio.run(get_storage_path())
    storage = LocalStorageService()
    physical_path = storage.get_absolute_path_for_validation(storage_path)
    physical_path.unlink()

    # Trigger integrity verification
    verify_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify-integrity",
        headers=headers,
    )
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["integrity_status"] == IntegrityStatus.MISSING.value
    assert v_data["match"] is False

    # Verify DB metadata remains intact
    check_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}",
        headers=headers,
    )
    assert check_res.status_code == 200
    assert check_res.json()["integrity_status"] == IntegrityStatus.MISSING.value


def test_tampered_custody_chain_detection():
    """
    Test 4: Tampering with an append-only custody event causes chain verification to fail (INVALID).
    """
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ufdr.org", "password": "ForensicAdmin2026!"},
    )
    headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Custody Chain Tamper Case"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    test_zip = create_minimal_test_zip("c.xml", b"DATA")
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("chain_test.zip", io.BytesIO(test_zip), "application/zip")},
        headers=headers,
    )
    evidence_id = upload_res.json()["id"]

    # Chain initially VALID
    chain_res1 = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify-custody-chain",
        headers=headers,
    )
    assert chain_res1.json()["status"] == "VALID"

    # Tamper with an event directly in the database (e.g. modify sequence 2 metadata)
    async def tamper_event():
        async with async_session_factory() as session:
            query = select(EvidenceCustodyEvent).where(
                EvidenceCustodyEvent.evidence_id == UUID(evidence_id),
                EvidenceCustodyEvent.sequence_number == 2,
            )
            event_res = await session.execute(query)
            event = event_res.scalars().first()
            event.metadata_json = json.dumps({"tampered": True, "fake_field": "injected"})
            await session.commit()


    asyncio.run(tamper_event())

    # Chain verification should now FAIL
    chain_res2 = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify-custody-chain",
        headers=headers,
    )
    tamper_report = chain_res2.json()
    assert tamper_report["status"] == "INVALID"
    assert "Tampered event content detected" in tamper_report["details"]


def test_role_authorization_and_viewer_restrictions():
    """
    Test 5:
    - Viewer cannot trigger integrity verification (403 Forbidden).
    - Viewer CAN view custody history (read-only audit viewing).
    """
    lead_token = get_token("lead_officer@test.org", "Password123!", "Lead Officer", "INVESTIGATOR")
    lead_headers = {"Authorization": f"Bearer {lead_token}"}

    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Role Test Case"},
        headers=lead_headers,
    )
    case_id = case_res.json()["id"]

    # Upload evidence as Lead
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("role_test.zip", io.BytesIO(create_minimal_test_zip()), "application/zip")},
        headers=lead_headers,
    )
    evidence_id = upload_res.json()["id"]

    # Create VIEWER user and add to case
    viewer_token = get_token("viewer_user@test.org", "Password123!", "Auditor Viewer", "VIEWER")
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # Add viewer to case
    client.post(
        f"/api/v1/cases/{case_id}/members",
        json={"email": "viewer_user@test.org", "access_role": CaseAccessRole.VIEWER.value},
        headers=lead_headers,
    )

    # Viewer attempts to trigger integrity verification -> FORBIDDEN (403)
    verify_attempt = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify-integrity",
        headers=viewer_headers,
    )
    assert verify_attempt.status_code == 403

    # Viewer CAN view custody history (read-only audit viewing)
    custody_view = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/custody",
        headers=viewer_headers,
    )
    assert custody_view.status_code == 200


def test_idor_custody_and_integrity_isolation():
    """
    Test 6: Cross-case IDOR defense:
    Investigator of Case A cannot verify or view custody for Evidence of Case B.
    """
    token_a = get_token("inv_a@test.org", "Password123!", "Inv A", "INVESTIGATOR")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    case_a_res = client.post("/api/v1/cases", json={"title": "Case A"}, headers=headers_a)
    case_a_id = case_a_res.json()["id"]

    # Investigator 2 (Case B)
    token_b = get_token("inv_b@test.org", "Password123!", "Inv B", "INVESTIGATOR")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    case_b_res = client.post("/api/v1/cases", json={"title": "Case B"}, headers=headers_b)
    case_b_id = case_b_res.json()["id"]

    # Upload evidence to Case B
    upload_b = client.post(
        f"/api/v1/cases/{case_b_id}/evidence",
        files={"file": ("secret_b.zip", io.BytesIO(create_minimal_test_zip()), "application/zip")},
        headers=headers_b,
    )
    evidence_b_id = upload_b.json()["id"]

    # Inv A attempts to verify Evidence B in Case B -> 404/403 (IDOR defense)
    verify_idor = client.post(
        f"/api/v1/cases/{case_b_id}/evidence/{evidence_b_id}/verify-integrity",
        headers=headers_a,
    )
    assert verify_idor.status_code in (403, 404)

    # Inv A attempts to access Evidence B through Case A's path -> 404
    cross_path_verify = client.post(
        f"/api/v1/cases/{case_a_id}/evidence/{evidence_b_id}/verify-integrity",
        headers=headers_a,
    )
    assert cross_path_verify.status_code == 404

    # Inv A attempts to view custody of Evidence B -> 404/403
    custody_idor = client.get(
        f"/api/v1/cases/{case_b_id}/evidence/{evidence_b_id}/custody",
        headers=headers_a,
    )
    assert custody_idor.status_code in (403, 404)
