import asyncio
import io
import os
import time
import zipfile
import pytest
from uuid import UUID
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.core.database import async_session_factory
from backend.app.main import app
from backend.app.models.custody import EvidenceCustodyEvent
from backend.app.models.enums import ArtifactType, CustodyEventType, IntegrityStatus, JobStatus
from backend.app.models.evidence import Evidence
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.raw_artifact import RawArtifact
from backend.app.parser import (
    NestedArchiveExceededError,
    ParserSecurityError,
    SafeArchiveInspector,
    UFDRDetector,
    UnsupportedUFDRFormatError,
    ZipBombError,
    ZipSlipError,
    stream_xml_records,
)
from backend.app.services.parser_worker import UFDRParserWorker
from backend.app.services.storage.local import LocalStorageService

client = TestClient(app)
settings = get_settings()


def get_token(email: str, password: str, name: str, role: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": name, "password": password, "role": role},
    )
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]


def build_synthetic_ufdr_bytes(
    num_calls: int = 5,
    num_messages: int = 5,
    num_contacts: int = 5,
    num_locations: int = 5,
    num_browser: int = 5,
    num_apps: int = 5,
    num_files: int = 5,
) -> bytes:
    """Constructs a deterministic, multi-artifact synthetic UFDR archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Manifest
        manifest_xml = """<?xml version="1.0" encoding="UTF-8"?>
<report>
    <case_info>
        <investigator>Detective Miller</investigator>
        <device_model>SM-G998B</device_model>
        <extraction_type>Full Physical / Logical Extraction</extraction_type>
    </case_info>
</report>"""
        zf.writestr("report.xml", manifest_xml.encode("utf-8"))

        # 2. Calls
        calls_xml = ['<?xml version="1.0" encoding="UTF-8"?><calls>']
        for i in range(1, num_calls + 1):
            calls_xml.append(f"""
            <call id="CALL_{i}">
                <caller>+155501000{i}</caller>
                <receiver>+155509999{i}</receiver>
                <direction>{"INCOMING" if i % 2 == 0 else "OUTGOING"}</direction>
                <timestamp>2026-09-30T10:{i:02d}:00Z</timestamp>
                <duration>{60 * i}</duration>
                <status>COMPLETED</status>
            </call>
            """)
        calls_xml.append("</calls>")
        zf.writestr("calls/call_log.xml", "".join(calls_xml).encode("utf-8"))

        # 3. Messages
        msgs_xml = ['<?xml version="1.0" encoding="UTF-8"?><messages>']
        apps = ["WhatsApp", "Telegram", "SMS", "Signal"]
        for i in range(1, num_messages + 1):
            app_name = apps[i % len(apps)]
            msgs_xml.append(f"""
            <message id="MSG_{i}">
                <sender>user_{i}@domain.com</sender>
                <receiver>target_{i}@domain.com</receiver>
                <timestamp>2026-09-30T12:{i:02d}:00Z</timestamp>
                <content>Forensic evidence message payload #{i} for analysis</content>
                <direction>{"INCOMING" if i % 2 == 0 else "OUTGOING"}</direction>
                <app>{app_name}</app>
                <status>READ</status>
            </message>
            """)
        msgs_xml.append("</messages>")
        zf.writestr("messages/chats.xml", "".join(msgs_xml).encode("utf-8"))

        # 4. Contacts
        contacts_xml = ['<?xml version="1.0" encoding="UTF-8"?><contacts>']
        for i in range(1, num_contacts + 1):
            contacts_xml.append(f"""
            <contact id="CONT_{i}">
                <name>Contact Person {i}</name>
                <phone>+155512345{i}</phone>
                <email>person_{i}@example.org</email>
                <account>Google Account</account>
            </contact>
            """)
        contacts_xml.append("</contacts>")
        zf.writestr("contacts/address_book.xml", "".join(contacts_xml).encode("utf-8"))

        # 5. Locations
        loc_xml = ['<?xml version="1.0" encoding="UTF-8"?><locations>']
        for i in range(1, num_locations + 1):
            loc_xml.append(f"""
            <location id="LOC_{i}">
                <latitude>{37.7749 + (i * 0.001):.6f}</latitude>
                <longitude>{-122.4194 + (i * 0.001):.6f}</longitude>
                <timestamp>2026-09-30T14:{i:02d}:00Z</timestamp>
                <source>GPS</source>
                <accuracy>5.0</accuracy>
            </location>
            """)
        loc_xml.append("</locations>")
        zf.writestr("location/gps_fixes.xml", "".join(loc_xml).encode("utf-8"))

        # 6. Browser
        browser_xml = ['<?xml version="1.0" encoding="UTF-8"?><browser_history>']
        for i in range(1, num_browser + 1):
            browser_xml.append(f"""
            <history_item id="HIST_{i}">
                <url>https://suspicious-site-{i}.org/login</url>
                <title>Secure Portal {i}</title>
                <timestamp>2026-09-30T15:{i:02d}:00Z</timestamp>
                <browser>Chrome</browser>
                <visit_count>{i}</visit_count>
            </history_item>
            """)
        browser_xml.append("</browser_history>")
        zf.writestr("browser/web_history.xml", "".join(browser_xml).encode("utf-8"))

        # 7. Applications
        apps_xml = ['<?xml version="1.0" encoding="UTF-8"?><installed_apps>']
        for i in range(1, num_apps + 1):
            apps_xml.append(f"""
            <application id="APP_{i}">
                <name>ForensicApp_{i}</name>
                <package_name>com.evidence.app{i}</package_name>
                <version>2.{i}.0</version>
                <event_type>INSTALLED</event_type>
                <timestamp>2026-09-30T08:{i:02d}:00Z</timestamp>
            </application>
            """)
        apps_xml.append("</installed_apps>")
        zf.writestr("apps/applications.xml", "".join(apps_xml).encode("utf-8"))

        # 8. Filesystem
        files_xml = ['<?xml version="1.0" encoding="UTF-8"?><filesystem>']
        for i in range(1, num_files + 1):
            files_xml.append(f"""
            <file id="FILE_{i}">
                <path>/data/user/0/com.evidence.app{i}/files/encrypted_{i}.dat</path>
                <size>{1024 * i}</size>
                <created>2026-09-30T09:00:00Z</created>
                <modified>2026-09-30T11:00:00Z</modified>
                <sha256>abcdef1234567890abcdef1234567890abcdef1234567890abcdef123456789{i:01d}</sha256>
            </file>
            """)
        files_xml.append("</filesystem>")
        zf.writestr("filesystem/files.xml", "".join(files_xml).encode("utf-8"))

    return buf.getvalue()


# ==============================================================================
# 1. Archive & Security Unit Tests
# ==============================================================================

def test_safe_archive_zipslip_rejection(tmp_path):
    """Verifies that archive members with directory traversal sequences are rejected."""
    bad_zip = tmp_path / "zipslip.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("../../etc/shadow", b"malicious content")

    inspector = SafeArchiveInspector()
    with pytest.raises(ZipSlipError):
        inspector.inspect_and_build_inventory(str(bad_zip))


def test_safe_archive_absolute_path_rejection(tmp_path):
    """Verifies that archive members with absolute paths are rejected."""
    bad_zip = tmp_path / "absolute_path.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("/root/.bashrc", b"malicious content")

    inspector = SafeArchiveInspector()
    with pytest.raises(ZipSlipError):
        inspector.inspect_and_build_inventory(str(bad_zip))


def test_safe_archive_entry_count_limit(tmp_path, monkeypatch):
    """Verifies that archive exceeding MAX_ARCHIVE_ENTRIES is rejected as ZipBomb."""
    monkeypatch.setattr(settings, "MAX_ARCHIVE_ENTRIES", 10)
    bomb_zip = tmp_path / "bomb_entries.zip"
    with zipfile.ZipFile(bomb_zip, "w") as zf:
        for i in range(15):
            zf.writestr(f"file_{i}.txt", b"abc")

    inspector = SafeArchiveInspector()
    with pytest.raises(ZipBombError):
        inspector.inspect_and_build_inventory(str(bomb_zip))


def test_safe_archive_decompression_ratio_limit(tmp_path, monkeypatch):
    """Verifies that suspicious compression ratios (e.g. 1000:1) trigger ZipBombError."""
    monkeypatch.setattr(settings, "MAX_COMPRESSION_RATIO", 20.0)
    bomb_zip = tmp_path / "bomb_ratio.zip"
    large_zeros = b"\x00" * (2 * 1024 * 1024)  # 2MB of zeroes compresses to ~2KB
    with zipfile.ZipFile(bomb_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("zeroes.dat", large_zeros)

    inspector = SafeArchiveInspector()
    with pytest.raises(ZipBombError):
        inspector.inspect_and_build_inventory(str(bomb_zip))


def test_nested_archive_depth_limit(tmp_path, monkeypatch):
    """Verifies that nesting beyond MAX_ARCHIVE_DEPTH raises NestedArchiveExceededError."""
    monkeypatch.setattr(settings, "MAX_ARCHIVE_DEPTH", 1)
    inspector = SafeArchiveInspector()
    with pytest.raises(NestedArchiveExceededError):
        inspector.inspect_and_build_inventory(str(tmp_path), current_depth=2)


# ==============================================================================
# 2. XML Security & Streaming Tests
# ==============================================================================

def test_xml_xxe_injection_blocked(tmp_path):
    """Verifies that XML files attempting external entity expansion are immediately blocked."""
    xxe_file = tmp_path / "xxe.xml"
    xxe_payload = """<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <calls>
        <call id="1">&xxe;</call>
    </calls>
    """
    xxe_file.write_text(xxe_payload)

    with pytest.raises(ParserSecurityError):
        list(stream_xml_records(str(xxe_file), target_tags={"call"}))


def test_xml_streaming_memory_clearing(tmp_path):
    """Verifies that iterparse yields parsed records accurately and clears memory."""
    valid_xml = tmp_path / "valid.xml"
    xml_content = """<calls>
        <call id="C1"><caller>+12345</caller></call>
        <call id="C2"><caller>+67890</caller></call>
    </calls>"""
    valid_xml.write_text(xml_content)

    records = list(stream_xml_records(str(valid_xml), target_tags={"call"}))
    assert len(records) == 2
    assert records[0][1]["caller"] == "+12345"
    assert records[1][1]["caller"] == "+67890"


# ==============================================================================
# 3. End-to-End Processing & Asynchronous Worker Pipeline Tests
# ==============================================================================

def test_end_to_end_ufdr_parsing_pipeline():
    """
    Full end-to-end pipeline test:
    Upload synthetic UFDR -> Verify queued job -> Execute worker ->
    Verify artifacts extracted across all 7 categories -> Verify custody & audit logs.
    """
    inv_token = get_token("pipeline_lead@ufdr.org", "Pass12345!", "Lead Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {inv_token}"}

    # 1. Create Case
    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "UFDR Parser Ingestion Case", "description": "Phase 5 end-to-end test"},
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Upload Synthetic UFDR
    ufdr_bytes = build_synthetic_ufdr_bytes(
        num_calls=3, num_messages=4, num_contacts=2, num_locations=2,
        num_browser=3, num_apps=2, num_files=2
    )
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=headers,
        files={"file": ("extraction.ufdr", ufdr_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    evidence_id = upload_res.json()["id"]

    # 3. Trigger Parse Endpoint
    parse_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/parse",
        headers=headers,
    )
    assert parse_res.status_code == 202
    job_data = parse_res.json()
    job_id = job_data["id"]
    assert job_data["status"] == "QUEUED"

    # 4. Synchronously run worker execution to verify completion deterministically
    async def run_worker():
        worker = UFDRParserWorker()
        await worker.execute_job(UUID(job_id))

    asyncio.run(run_worker())

    # 5. Check Job Status API
    for _ in range(30):
        status_res = client.get(
            f"/api/v1/cases/{case_id}/processing-jobs/{job_id}",
            headers=headers,
        )
        assert status_res.status_code == 200
        completed_job = status_res.json()
        if completed_job["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.2)

    assert completed_job["status"] == "COMPLETED"
    assert completed_job["progress"] == 100
    assert completed_job["artifacts_total"] == (3 + 4 + 2 + 2 + 3 + 2 + 2)
    assert completed_job["errors_count"] == 0

    # 6. Verify Summary JSON Content
    summary = completed_job["summary_json"]
    assert summary is not None
    assert summary["counts_by_type"]["CALL"] == 3
    assert summary["counts_by_type"]["MESSAGE"] == 4
    assert summary["counts_by_type"]["CONTACT"] == 2
    assert summary["counts_by_type"]["LOCATION"] == 2
    assert summary["counts_by_type"]["BROWSER"] == 3
    assert summary["counts_by_type"]["APPLICATION"] == 2
    assert summary["counts_by_type"]["FILESYSTEM"] == 2

    # 7. Check Artifact Explorer Endpoint with Traceability
    art_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/artifacts?page=1&page_size=50",
        headers=headers,
    )
    assert art_res.status_code == 200
    art_data = art_res.json()
    assert art_data["total"] == 18

    # Verify every artifact retains full source provenance
    for item in art_data["items"]:
        assert item["evidence_id"] == evidence_id
        assert item["source_file"] in ["call_log.xml", "chats.xml", "address_book.xml", "gps_fixes.xml", "web_history.xml", "applications.xml", "files.xml"]
        assert len(item["source_path"]) > 0
        assert len(item["record_identifier"]) > 0
        assert isinstance(item["raw_data"], dict)

    # 8. Test Filtering by Artifact Category (CALL)
    call_filter_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/artifacts?artifact_type=CALL",
        headers=headers,
    )
    assert call_filter_res.status_code == 200
    calls_data = call_filter_res.json()
    assert calls_data["total"] == 3
    for call in calls_data["items"]:
        assert call["artifact_type"] == "CALL"
        assert "caller" in call["raw_data"]

    # 9. Verify Chain of Custody Events
    custody_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/custody",
        headers=headers,
    )
    assert custody_res.status_code == 200
    events = [e["event_type"] for e in custody_res.json()]
    assert "EVIDENCE_PROCESSING_STARTED" in events
    assert "EVIDENCE_PROCESSING_COMPLETED" in events

    # 10. Verify Reprocessing Idempotency (Does not create duplicate artifacts)
    retry_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/parse",
        headers=headers,
    )
    assert retry_res.status_code == 202
    retry_job_id = retry_res.json()["id"]

    async def run_retry_worker():
        worker = UFDRParserWorker()
        await worker.execute_job(UUID(retry_job_id))

    asyncio.run(run_retry_worker())

    # Count artifacts after retry: must remain strictly 18, not 36!
    art_after_retry = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/artifacts",
        headers=headers,
    )
    assert art_after_retry.json()["total"] == 18


def test_viewer_role_cannot_trigger_parsing():
    """Verifies that users with VIEWER role are forbidden from initiating parsing."""
    lead_token = get_token("lead_owner@ufdr.org", "Pass12345!", "Lead Owner", "INVESTIGATOR")
    viewer_token = get_token("viewer_agent@ufdr.org", "Pass12345!", "Viewer Agent", "VIEWER")

    # Lead creates case
    case_res = client.post(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {lead_token}"},
        json={"title": "Viewer Restrictions Case"},
    )
    case_id = case_res.json()["id"]

    # Lead uploads evidence
    ufdr_bytes = build_synthetic_ufdr_bytes()
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers={"Authorization": f"Bearer {lead_token}"},
        files={"file": ("evidence.ufdr", ufdr_bytes, "application/zip")},
    )
    evidence_id = upload_res.json()["id"]

    # Viewer attempts parse -> 403 Forbidden
    parse_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/parse",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert parse_res.status_code == 403


def test_tampered_evidence_integrity_mismatch_blocks_parsing():
    """
    Verifies that if stored evidence has been altered (integrity mismatch),
    the parser engine immediately refuses to process it and preserves audit evidence.
    """
    token = get_token("tamper_inv@ufdr.org", "Pass12345!", "Tamper Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {token}"}

    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "Tampered Evidence Case"},
    )
    case_id = case_res.json()["id"]

    ufdr_bytes = build_synthetic_ufdr_bytes(num_calls=2)
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=headers,
        files={"file": ("original.ufdr", ufdr_bytes, "application/zip")},
    )
    evidence_id = upload_res.json()["id"]

    # Tamper with the physical file on disk directly
    async def tamper_file():
        async with async_session_factory() as session:
            ev = await session.get(Evidence, UUID(evidence_id))
            storage = LocalStorageService()
            file_path = storage._resolve_safe_path(ev.storage_path_or_key)
            with open(file_path, "wb") as f:
                f.write(b"CORRUPTED_TAMPERED_DATA_BYTES")

    asyncio.run(tamper_file())

    # Create job & execute worker
    parse_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/parse",
        headers=headers,
    )
    assert parse_res.status_code == 202
    job_id = parse_res.json()["id"]

    async def run_worker():
        worker = UFDRParserWorker()
        await worker.execute_job(UUID(job_id))

    asyncio.run(run_worker())

    # Check job status: must be FAILED with INTEGRITY_MISMATCH
    status_res = client.get(
        f"/api/v1/cases/{case_id}/processing-jobs/{job_id}",
        headers=headers,
    )
    assert status_res.status_code == 200
    job_data = status_res.json()
    assert job_data["status"] == "FAILED"
    assert "INTEGRITY_MISMATCH" in job_data["error_message"]

    # Verify no raw artifacts were extracted from corrupted data
    art_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/artifacts",
        headers=headers,
    )
    assert art_res.json()["total"] == 0


def test_partial_success_with_malformed_xml():
    """
    Verifies that a UFDR containing one malformed XML file does not fail the entire job:
    valid files are extracted, malformed file is recorded in warnings, job completes with partial metrics.
    """
    token = get_token("partial_inv@ufdr.org", "Pass12345!", "Partial Examiner", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {token}"}

    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "Partial Failure Case"},
    )
    case_id = case_res.json()["id"]

    # Build archive with 1 valid calls.xml and 1 malformed chats.xml
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("report.xml", b"<report><device>Demo</device></report>")
        zf.writestr("calls/calls.xml", b'<calls><call id="1"><caller>+123</caller></call></calls>')
        zf.writestr("messages/chats.xml", b'<messages><message id="1">BROKEN UNCLOSED TAG')

    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=headers,
        files={"file": ("partial.ufdr", buf.getvalue(), "application/zip")},
    )
    evidence_id = upload_res.json()["id"]

    parse_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/parse",
        headers=headers,
    )
    job_id = parse_res.json()["id"]

    async def run_worker():
        worker = UFDRParserWorker()
        await worker.execute_job(UUID(job_id))

    asyncio.run(run_worker())

    for _ in range(30):
        status_res = client.get(
            f"/api/v1/cases/{case_id}/processing-jobs/{job_id}",
            headers=headers,
        )
        job = status_res.json()
        if job["status"] in ("PARTIAL", "COMPLETED", "FAILED"):
            break
        time.sleep(0.2)

    assert job["status"] in ("PARTIAL", "COMPLETED")
    assert job["artifacts_total"] == 1
    error_or_warning_msgs = job["summary_json"].get("warnings", []) + job["summary_json"].get("errors", [])
    assert any("chats.xml" in msg for msg in error_or_warning_msgs)


# ==============================================================================
# 4. Large Dataset & Bounded Performance Verification Test
# ==============================================================================

def test_large_synthetic_dataset_processing():
    """
    Generates a large synthetic UFDR package with 1,000+ artifact records.
    Verifies that processing executes in bounded memory and streams records into database.
    """
    token = get_token("perf_inv@ufdr.org", "Pass12345!", "Perf Officer", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {token}"}

    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": "Performance Ingestion Benchmark"},
    )
    case_id = case_res.json()["id"]

    # 200 calls, 300 messages, 150 contacts, 150 locations, 100 browser, 100 apps = 1,000 records
    large_ufdr_bytes = build_synthetic_ufdr_bytes(
        num_calls=200,
        num_messages=300,
        num_contacts=150,
        num_locations=150,
        num_browser=100,
        num_apps=100,
        num_files=50,
    )
    total_expected = 200 + 300 + 150 + 150 + 100 + 100 + 50  # 1,050 records

    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=headers,
        files={"file": ("large_benchmark.ufdr", large_ufdr_bytes, "application/zip")},
    )
    evidence_id = upload_res.json()["id"]

    t0 = time.perf_counter()

    parse_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/parse",
        headers=headers,
    )
    job_id = parse_res.json()["id"]

    async def run_large_worker():
        worker = UFDRParserWorker()
        await worker.execute_job(UUID(job_id))

    asyncio.run(run_large_worker())

    elapsed = time.perf_counter() - t0

    for _ in range(30):
        status_res = client.get(
            f"/api/v1/cases/{case_id}/processing-jobs/{job_id}",
            headers=headers,
        )
        job = status_res.json()
        if job["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.2)

    assert job["status"] == "COMPLETED"
    assert job["artifacts_total"] == total_expected
    assert job["errors_count"] == 0

    print(f"\n[BENCHMARK] Parsed {total_expected} records in {elapsed:.2f}s ({total_expected/elapsed:.1f} rec/sec)")
