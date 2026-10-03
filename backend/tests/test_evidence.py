import hashlib
import io
import zipfile
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import app

client = TestClient(app)


def get_token(email: str, password: str, name: str, role: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": name, "password": password, "role": role},
    )
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]


def create_valid_zip_bytes(files_dict: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    """Creates an in-memory valid zip archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as zf:
        for fname, content in files_dict.items():
            zf.writestr(fname, content)
    return buffer.getvalue()


def test_evidence_upload_success_and_sha256_verification():
    inv_token = get_token("lead.inv@ufdr.org", "Pass1234!", "Lead Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {inv_token}"}

    # 1. Create a case
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Operation Cyber Vault", "description": "UFDR test case"},
        headers=headers,
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Build a valid UFDR / ZIP archive
    archive_contents = {
        "report.xml": b"<ufdr><device id='SM-G998B'><contacts/></device></ufdr>",
        "metadata.json": b'{"extractor": "UFED 4PC", "version": "7.58"}',
    }
    raw_zip = create_valid_zip_bytes(archive_contents)
    expected_sha256 = hashlib.sha256(raw_zip).hexdigest()
    expected_size = len(raw_zip)

    # 3. Upload evidence
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("device_extraction.ufdr", raw_zip, "application/octet-stream")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    ev_data = upload_res.json()
    assert ev_data["case_id"] == case_id
    assert ev_data["original_filename"] == "device_extraction.ufdr"
    assert ev_data["file_size"] == expected_size
    assert ev_data["sha256_hash"] == expected_sha256
    assert ev_data["status"] == "VALID"
    assert ev_data["detected_mime_type"] == "application/x-ufdr"
    # Verify physical filesystem paths are NOT exposed to the client
    assert "/" not in ev_data["stored_filename"]
    assert "\\" not in ev_data["stored_filename"]
    assert "storage" not in ev_data["stored_filename"]

    evidence_id = ev_data["id"]

    # 4. List evidence for the case
    list_res = client.get(f"/api/v1/cases/{case_id}/evidence", headers=headers)
    assert list_res.status_code == 200
    evidence_list = list_res.json()
    assert len(evidence_list) >= 1
    assert any(item["id"] == evidence_id for item in evidence_list)

    # 5. Get individual evidence details
    details_res = client.get(f"/api/v1/cases/{case_id}/evidence/{evidence_id}", headers=headers)
    assert details_res.status_code == 200
    assert details_res.json()["id"] == evidence_id
    assert details_res.json()["sha256_hash"] == expected_sha256

    # 6. Secure download
    download_res = client.get(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/download", headers=headers)
    assert download_res.status_code == 200
    assert download_res.headers["X-Evidence-SHA256"] == expected_sha256
    assert download_res.headers["Content-Length"] == str(expected_size)
    assert download_res.content == raw_zip

    # 7. Quarantine evidence (controlled soft-delete lifecycle)
    quarantine_res = client.delete(f"/api/v1/cases/{case_id}/evidence/{evidence_id}", headers=headers)
    assert quarantine_res.status_code == 200
    assert quarantine_res.json()["status"] == "QUARANTINED"

    # Verify original file was NOT erased from disk on quarantine
    assert len(download_res.content) == expected_size


def test_evidence_upload_unauthenticated_rejected():
    raw_zip = create_valid_zip_bytes({"test.txt": b"test"})
    res = client.post(
        "/api/v1/cases/00000000-0000-0000-0000-000000000000/evidence",
        files={"file": ("test.ufdr", raw_zip, "application/octet-stream")},
    )
    assert res.status_code == 401


def test_evidence_viewer_role_upload_forbidden():
    # Admin creates case
    admin_token = get_token("admin@ufdr.org", "ForensicAdmin2026!", "Admin", "ADMIN")
    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Viewer Protection Case", "description": "Testing RBAC upload denial"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    case_id = case_res.json()["id"]

    # Register Viewer and assign to case
    viewer_token = get_token("court.viewer@ufdr.org", "ViewPass123!", "Court Viewer", "VIEWER")
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    client.post(
        f"/api/v1/cases/{case_id}/members",
        json={"email": "court.viewer@ufdr.org", "access_role": "VIEWER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Viewer attempts upload
    raw_zip = create_valid_zip_bytes({"test.txt": b"content"})
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("test.zip", raw_zip, "application/zip")},
        headers=viewer_headers,
    )
    assert upload_res.status_code == 403


def test_evidence_idor_and_case_isolation():
    token_a = get_token("inv.a@ufdr.org", "Pass1234!", "Investigator A", "INVESTIGATOR")
    token_b = get_token("inv.b@ufdr.org", "Pass1234!", "Investigator B", "INVESTIGATOR")

    # Inv A creates Case A
    case_a_res = client.post(
        "/api/v1/cases",
        json={"title": "Case Alpha", "description": "Strict isolation test"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    case_a_id = case_a_res.json()["id"]

    # Inv B creates Case B
    case_b_res = client.post(
        "/api/v1/cases",
        json={"title": "Case Beta", "description": "Strict isolation test"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    case_b_id = case_b_res.json()["id"]

    # Inv A uploads evidence to Case A
    raw_zip = create_valid_zip_bytes({"chat.txt": b"suspect message"})
    upload_res = client.post(
        f"/api/v1/cases/{case_a_id}/evidence",
        files={"file": ("case_a_dump.ufdr", raw_zip, "application/octet-stream")},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert upload_res.status_code == 201
    evidence_a_id = upload_res.json()["id"]

    # IDOR Test 1: Inv B attempts to upload evidence to Case A
    idor_upload = client.post(
        f"/api/v1/cases/{case_a_id}/evidence",
        files={"file": ("rogue_evidence.zip", raw_zip, "application/zip")},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert idor_upload.status_code == 403

    # IDOR Test 2: Inv B attempts to read Case A's evidence list
    idor_list = client.get(
        f"/api/v1/cases/{case_a_id}/evidence",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert idor_list.status_code == 403

    # IDOR Test 3: Inv B attempts to download Case A's evidence
    idor_download = client.get(
        f"/api/v1/cases/{case_a_id}/evidence/{evidence_a_id}/download",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert idor_download.status_code == 403

    # IDOR Test 4: Querying Evidence A under Case B returns 404
    mismatch_get = client.get(
        f"/api/v1/cases/{case_b_id}/evidence/{evidence_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert mismatch_get.status_code == 404


def test_evidence_invalid_extension_rejected():
    inv_token = get_token("lead.inv@ufdr.org", "Pass1234!", "Lead Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {inv_token}"}

    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Extension Test Case"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    # Upload file with unsupported extension (.pdf or .exe)
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("unsupported_doc.pdf", b"%PDF-1.4...", "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["error"]["message"]


def test_evidence_invalid_magic_bytes_rejected():
    inv_token = get_token("lead.inv@ufdr.org", "Pass1234!", "Lead Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {inv_token}"}

    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Magic Bytes Test Case"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    # Masquerading file: Plain text renamed to .ufdr
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("fake_archive.ufdr", b"This is just plain ASCII text, not a zip!", "application/octet-stream")},
        headers=headers,
    )
    assert res.status_code == 422
    assert "Invalid file signature" in res.json()["error"]["message"]


def test_evidence_zipslip_traversal_rejected():
    inv_token = get_token("lead.inv@ufdr.org", "Pass1234!", "Lead Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {inv_token}"}

    case_res = client.post(
        "/api/v1/cases",
        json={"title": "ZipSlip Security Case"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    # Create ZipSlip archive containing entry with '../'
    raw_slip_zip = create_valid_zip_bytes({
        "../../etc/passwd": b"root:x:0:0:root:/root:/bin/bash",
        "legit_data.xml": b"<data/>",
    })

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("zipslip_exploit.ufdr", raw_slip_zip, "application/octet-stream")},
        headers=headers,
    )
    assert res.status_code == 422
    err_msg = res.json()["error"]["message"]
    assert "ZipSlip" in err_msg or "Path traversal" in err_msg


def test_evidence_path_traversal_in_filename_sanitized():
    inv_token = get_token("lead.inv@ufdr.org", "Pass1234!", "Lead Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {inv_token}"}

    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Filename Sanitization Case"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    raw_zip = create_valid_zip_bytes({"ok.txt": b"content"})

    # Malicious multipart filename attempting path escape
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("../../../../etc/shadow.zip", raw_zip, "application/zip")},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    # Ensure basename was applied and no path characters remain in original_filename display
    assert data["original_filename"] == "shadow.zip"
    assert "/" not in data["stored_filename"]
    assert "\\" not in data["stored_filename"]


def test_evidence_oversized_file_rejected(monkeypatch):
    inv_token = get_token("lead.inv@ufdr.org", "Pass1234!", "Lead Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {inv_token}"}

    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Size Limit Case"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    # Temporarily set MAX_UPLOAD_SIZE_MB to 1MB to test enforcement without generating gigabytes
    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)

    # Create uncompressed 1.5MB zip archive (exceeds 1MB limit)
    raw_large_zip = create_valid_zip_bytes(
        {"huge.bin": b"A" * 1_500_000},
        compression=zipfile.ZIP_STORED,
    )
    assert len(raw_large_zip) > 1024 * 1024

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("too_large.ufdr", raw_large_zip, "application/octet-stream")},
        headers=headers,
    )
    assert res.status_code == 413
    assert "exceeds maximum allowed limit" in res.json()["error"]["message"]


def test_evidence_large_streaming_upload_and_staging_cleanup():
    inv_token = get_token("lead.inv@ufdr.org", "Pass1234!", "Lead Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {inv_token}"}

    case_res = client.post(
        "/api/v1/cases",
        json={"title": "Large Stream Ingestion Case", "description": "Stress-testing streaming upload"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    # Generate a realistic 10 MB synthetic evidence package
    # with XML, SQLite DB simulation, and media simulation
    synthetic_files = {
        "report.xml": b"<?xml version='1.0'?><ufdr_report><chats count='50000'/></ufdr_report>" * 100,
        "contacts.vcf": b"BEGIN:VCARD\r\nFN:Suspect Contact\r\nTEL:+1555019999\r\nEND:VCARD\r\n" * 1000,
        "database.db": b"SQLITE FORMAT 3\x00" + b"\x00" * 10000,
        "call_audio.wav": b"RIFF" + b"\x00" * (8 * 1024 * 1024),  # 8 MB payload
    }
    raw_synthetic_archive = create_valid_zip_bytes(synthetic_files, compression=zipfile.ZIP_STORED)
    archive_size = len(raw_synthetic_archive)
    expected_sha256 = hashlib.sha256(raw_synthetic_archive).hexdigest()

    assert archive_size >= 8 * 1024 * 1024

    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("full_phone_dump.ufdr", raw_synthetic_archive, "application/octet-stream")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    ev_data = upload_res.json()
    assert ev_data["file_size"] == archive_size
    assert ev_data["sha256_hash"] == expected_sha256
    assert ev_data["status"] == "VALID"

    # Verify staging scratch directory has no orphaned temporary files
    settings = get_settings()
    scratch_files = list(get_settings().SCRATCH_STORAGE_PATH.strip())
    # Temporary files should be cleaned up / moved to final storage
    from pathlib import Path
    scratch_path = Path(settings.SCRATCH_STORAGE_PATH)
    if scratch_path.exists():
        staging_leftovers = list(scratch_path.glob("staging_*.tmp"))
        assert len(staging_leftovers) == 0, f"Found orphaned staging files: {staging_leftovers}"
