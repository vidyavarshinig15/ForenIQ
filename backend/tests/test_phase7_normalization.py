import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import async_session_factory
from backend.app.main import app
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import (
    ArtifactType,
    CaseAccessRole,
    DataQualityStatus,
    JobPriority,
    JobStatus,
    JobType,
    TimestampPrecision,
    TimestampStatus,
    UserRole,
)
from backend.app.models.evidence import Evidence
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.raw_artifact import RawArtifact
from backend.app.models.user import User
from backend.app.models.case import Case
from backend.app.normalizers.timestamps import normalize_timestamp
from backend.app.normalizers.entities import (
    normalize_phone_number,
    normalize_email,
    normalize_application_name,
)
from backend.app.normalizers.calls import CallNormalizer
from backend.app.normalizers.messages import MessageNormalizer
from backend.app.normalizers.contacts import ContactNormalizer
from backend.app.normalizers.location import LocationNormalizer
from backend.app.normalizers.browser import BrowserNormalizer
from backend.app.normalizers.applications import ApplicationNormalizer
from backend.app.normalizers.filesystem import FilesystemNormalizer
from backend.app.normalizers.pipeline import NormalizationPipeline
from backend.app.repositories.canonical_evidence_repo import CanonicalEvidenceRepository
from backend.app.services.normalization_worker import EvidenceNormalizationWorker


# ==============================================================================
# 1. UNIT TESTS: TIMESTAMP NORMALIZATION & PRECISION
# ==============================================================================

def test_timestamp_normalization_iso8601():
    """Verify ISO-8601 parsing across microseconds, seconds, and UTC offsets."""
    # Microsecond precision
    res1 = normalize_timestamp("2026-09-30T14:22:15.123456Z")
    assert res1.status == TimestampStatus.VALID
    assert res1.precision == TimestampPrecision.MILLISECOND
    assert res1.normalized_utc.year == 2026 and res1.normalized_utc.month == 9 and res1.normalized_utc.day == 30
    assert res1.normalized_utc.hour == 14 and res1.normalized_utc.minute == 22 and res1.normalized_utc.second == 15
    assert res1.original_timezone == "UTC"

    # Second precision with offset +05:30
    res2 = normalize_timestamp("2026-10-01T10:00:00+05:30")
    assert res2.status == TimestampStatus.VALID
    assert res2.precision == TimestampPrecision.SECOND
    # Converted to UTC (10:00 - 5:30 = 04:30)
    assert res2.normalized_utc.hour == 4 and res2.normalized_utc.minute == 30
    assert res2.original_timezone == "+05:30"


def test_timestamp_normalization_epochs():
    """Verify Unix epoch parsing in seconds, milliseconds, and microseconds."""
    # Seconds (1700000000 -> 2023-11-14 22:13:20 UTC)
    res_sec = normalize_timestamp("1700000000")
    assert res_sec.status == TimestampStatus.VALID
    assert res_sec.precision == TimestampPrecision.SECOND
    assert res_sec.normalized_utc.year == 2023

    # Milliseconds (1700000000123)
    res_ms = normalize_timestamp(1700000000123)
    assert res_ms.status == TimestampStatus.VALID
    assert res_ms.precision == TimestampPrecision.MILLISECOND
    assert res_ms.normalized_utc.microsecond == 123000


def test_timestamp_normalization_partial_dates():
    """Verify partial dates preserve DAY, MONTH, YEAR precision without fake times."""
    # DAY precision: 2026-09-30
    res_day = normalize_timestamp("2026-09-30")
    assert res_day.status == TimestampStatus.VALID
    assert res_day.precision == TimestampPrecision.DAY
    assert res_day.normalized_utc.year == 2026 and res_day.normalized_utc.month == 9 and res_day.normalized_utc.day == 30

    # MONTH precision: 2026-09
    res_mo = normalize_timestamp("2026-09")
    assert res_mo.status == TimestampStatus.VALID
    assert res_mo.precision == TimestampPrecision.MONTH
    assert res_mo.normalized_utc.year == 2026 and res_mo.normalized_utc.month == 9 and res_mo.normalized_utc.day == 1

    # YEAR precision: 2026
    res_yr = normalize_timestamp("2026")
    assert res_yr.status == TimestampStatus.VALID
    assert res_yr.precision == TimestampPrecision.YEAR
    assert res_yr.normalized_utc.year == 2026 and res_yr.normalized_utc.month == 1 and res_yr.normalized_utc.day == 1


def test_timestamp_invalid_and_missing_handling():
    """Verify unparseable timestamps return None and INVALID status without inventing data."""
    res_inv = normalize_timestamp("Not-A-Timestamp-404")
    assert res_inv.normalized_utc is None
    assert res_inv.status == TimestampStatus.INVALID
    assert res_inv.precision == TimestampPrecision.UNKNOWN

    res_none = normalize_timestamp(None)
    assert res_none.normalized_utc is None
    assert res_none.status == TimestampStatus.UNKNOWN
    assert res_none.precision == TimestampPrecision.UNKNOWN


# ==============================================================================
# 2. UNIT TESTS: ENTITY EXTRACTION & NORMALIZATION
# ==============================================================================

def test_phone_number_normalization():
    """Verify phone formatting normalizes to E.164 while preserving validity."""
    norm1, orig1 = normalize_phone_number("+91 98765 43210")
    assert norm1 == "+919876543210"
    assert orig1 == "+91 98765 43210"

    norm2, _ = normalize_phone_number("+1 (555) 123-4567")
    assert norm2 == "+15551234567"

    norm3, _ = normalize_phone_number("09876543210")
    assert norm3 == "09876543210"

    norm_empty, _ = normalize_phone_number("")
    assert norm_empty is None

    norm_none, _ = normalize_phone_number(None)
    assert norm_none is None


def test_email_normalization():
    """Verify safe email whitespace trimming and lowercasing."""
    norm1, orig1 = normalize_email("  Suspect.ONE@Investigation.Org  ")
    assert norm1 == "suspect.one@investigation.org"
    assert orig1 == "Suspect.ONE@Investigation.Org"

    norm_inv, _ = normalize_email("invalid-email-no-at")
    assert norm_inv is None

    norm_none, _ = normalize_email(None)
    assert norm_none is None


def test_application_name_normalization():
    """Verify package name mapping to canonical applications."""
    norm1, orig1 = normalize_application_name("com.whatsapp")
    assert norm1 == "WhatsApp"
    assert orig1 == "com.whatsapp"

    norm2, _ = normalize_application_name("com.android.chrome")
    assert norm2 == "Chrome"

    norm3, _ = normalize_application_name("org.telegram.messenger")
    assert norm3 == "Telegram"

    norm4, orig4 = normalize_application_name("CustomInternalApp")
    assert norm4 == "CustomInternalApp"

    norm_none, _ = normalize_application_name(None)
    assert norm_none is None


# ==============================================================================
# 3. UNIT TESTS: MODULAR NORMALIZERS
# ==============================================================================

def test_call_normalizer():
    """Test CallNormalizer standardizes calls, direction, duration, entities."""
    norm = CallNormalizer()
    raw = RawArtifact(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        evidence_id=uuid.uuid4(),
        artifact_type=ArtifactType.CALL,
        source_file="calls.xml",
        source_path="/data/calls.xml",
        record_identifier="call_101",
        raw_data={
            "caller": "+1-555-0199",
            "receiver": "+1-555-0200",
            "direction": "INCOMING",
            "duration": "142",
            "timestamp": "2026-09-30T12:00:00Z",
            "application": "Phone",
        },
    )
    assert norm.can_normalize(raw)
    res = norm.normalize(raw)
    assert res.data_quality_status == DataQualityStatus.VALID
    assert res.event_timestamp is not None
    assert res.timestamp_precision == TimestampPrecision.SECOND
    assert res.metadata["duration_seconds"] == 142
    assert res.metadata["direction"] == "INCOMING"
    entity_types = [e["entity_type"] for e in res.entities]
    assert "PHONE_NUMBER" in entity_types


def test_message_normalizer_verbatim_preservation():
    """Test MessageNormalizer preserves verbatim content without summarization."""
    norm = MessageNormalizer()
    content_raw = "Forensic test message: Meet at coordinates 37.7749, -122.4194 at 22:00! Do NOT delete."
    raw = RawArtifact(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        evidence_id=uuid.uuid4(),
        artifact_type=ArtifactType.MESSAGE,
        source_file="messages.xml",
        source_path="/data/messages.xml",
        record_identifier="msg_505",
        raw_data={
            "sender": "+15551112222",
            "receiver": "+15553334444",
            "body": content_raw,
            "timestamp": "2026-09-30T18:30:00Z",
            "app": "WhatsApp",
            "direction": "OUTGOING",
        },
    )
    res = norm.normalize(raw)
    assert res.content == content_raw  # Verbatim preservation guaranteed
    assert res.data_quality_status == DataQualityStatus.VALID
    assert len(res.entities) >= 2


def test_contact_normalizer():
    """Test ContactNormalizer standardizes name, phones, emails, and accounts."""
    norm = ContactNormalizer()
    raw = RawArtifact(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        evidence_id=uuid.uuid4(),
        artifact_type=ArtifactType.CONTACT,
        source_file="contacts.xml",
        source_path="/data/contacts.xml",
        record_identifier="contact_001",
        raw_data={
            "name": "Target Subject A",
            "phone_numbers": ["+1 555-1234", "+1 555-5678"],
            "emails": ["subjectA@example.com"],
            "account": "whatsapp_user_123",
        },
    )
    res = norm.normalize(raw)
    assert res.data_quality_status == DataQualityStatus.VALID
    assert res.metadata["name"] == "Target Subject A"
    assert len(res.metadata["phone_numbers"]) == 2
    assert len(res.entities) >= 3


def test_location_normalizer_strict_coordinate_validation():
    """Test LocationNormalizer accepts valid coordinates and strictly rejects out-of-bounds."""
    norm = LocationNormalizer()

    # Valid coordinates (San Francisco)
    valid_raw = RawArtifact(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        evidence_id=uuid.uuid4(),
        artifact_type=ArtifactType.LOCATION,
        source_file="gps.xml",
        source_path="/data/gps.xml",
        record_identifier="gps_001",
        raw_data={
            "latitude": 37.7749,
            "longitude": -122.4194,
            "accuracy": 4.5,
            "timestamp": "2026-09-30T10:15:00Z",
            "provider": "GPS",
        },
    )
    valid_res = norm.normalize(valid_raw)
    assert valid_res.data_quality_status == DataQualityStatus.VALID
    assert valid_res.metadata["latitude"] == 37.7749
    assert valid_res.metadata["longitude"] == -122.4194
    assert len(valid_res.validation_warnings) == 0

    # Corrupted / Out-of-bounds coordinates (lat 195.0 > 90, lon -250.0 < -180)
    invalid_raw = RawArtifact(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        evidence_id=uuid.uuid4(),
        artifact_type=ArtifactType.LOCATION,
        source_file="gps.xml",
        source_path="/data/gps.xml",
        record_identifier="gps_corrupted",
        raw_data={
            "latitude": 195.0,
            "longitude": -250.0,
            "timestamp": "2026-09-30T10:15:00Z",
        },
    )
    invalid_res = norm.normalize(invalid_raw)
    # Does NOT silently fix or clamp; flags INVALID status and records warnings
    assert invalid_res.data_quality_status == DataQualityStatus.INVALID
    warning_codes = [w["code"] for w in invalid_res.validation_warnings]
    assert "INVALID_LATITUDE_RANGE" in warning_codes


def test_browser_normalizer():
    """Test BrowserNormalizer maps URL, title, browser name."""
    norm = BrowserNormalizer()
    raw = RawArtifact(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        evidence_id=uuid.uuid4(),
        artifact_type=ArtifactType.BROWSER,
        source_file="history.xml",
        source_path="/data/history.xml",
        record_identifier="hist_99",
        raw_data={
            "url": "https://secure-forensics.org/dockets/case_1234",
            "title": "Docket Case 1234 Overview",
            "timestamp": "2026-09-30T11:00:00Z",
            "browser": "com.android.chrome",
        },
    )
    res = norm.normalize(raw)
    assert res.data_quality_status == DataQualityStatus.VALID
    assert res.application == "Chrome"
    assert "Docket Case 1234 Overview" in res.content
    assert res.metadata["url"] == "https://secure-forensics.org/dockets/case_1234"
    assert any(e["entity_type"] == "URL" for e in res.entities)


def test_filesystem_normalizer():
    """Test FilesystemNormalizer standardizes path, hashes, sizes, and timestamps."""
    norm = FilesystemNormalizer()
    raw = RawArtifact(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        evidence_id=uuid.uuid4(),
        artifact_type=ArtifactType.FILESYSTEM,
        source_file="files.xml",
        source_path="/data/files.xml",
        record_identifier="file_404",
        raw_data={
            "path": "/storage/emulated/0/DCIM/Camera/IMG_20260930_001.jpg",
            "filename": "IMG_20260930_001.jpg",
            "size_bytes": 4194304,
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "modified_at": "2026-09-30T15:20:00Z",
        },
    )
    res = norm.normalize(raw)
    assert res.data_quality_status == DataQualityStatus.VALID
    assert res.metadata["size_bytes"] == 4194304
    assert res.metadata["sha256"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# ==============================================================================
# 4. DETERMINISTIC IDENTIFIERS & FINGERPRINTING
# ==============================================================================

def test_deterministic_identity_and_fingerprint():
    """Verify stable UUIDv5 identity key generation is deterministic across executions."""
    pipeline = NormalizationPipeline()
    ev_id = uuid.uuid4()
    raw = RawArtifact(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        evidence_id=ev_id,
        artifact_type=ArtifactType.MESSAGE,
        source_file="messages.xml",
        source_path="/data/messages.xml",
        record_identifier="msg_stable_123",
        raw_data={"body": "Stable identity test", "timestamp": "2026-09-30T10:00:00Z"},
    )

    # First normalization
    rec1 = pipeline.normalize(raw)
    # Second normalization with different RawArtifact ID but identical source provenance
    raw2 = RawArtifact(
        id=uuid.uuid4(),  # Different DB ID
        case_id=raw.case_id,
        evidence_id=ev_id,
        artifact_type=ArtifactType.MESSAGE,
        source_file="messages.xml",
        source_path="/data/messages.xml",
        record_identifier="msg_stable_123",  # Same provenance
        raw_data={"body": "Stable identity test", "timestamp": "2026-09-30T10:00:00Z"},
    )
    rec2 = pipeline.normalize(raw2)

    assert rec1.id == rec2.id  # Deterministic UUIDv5 matches exactly
    assert rec1.canonical_fingerprint == rec2.canonical_fingerprint
    assert len(rec1.canonical_fingerprint) == 64  # SHA-256 hex


# ==============================================================================
# 5. INTEGRATION TEST: END-TO-END NORMALIZATION, IDEMPOTENCY & TRACEABILITY
# ==============================================================================

@pytest.mark.asyncio
async def test_end_to_end_normalization_pipeline_and_idempotency():
    """
    Comprehensive integration test:
    1. Seed Case, Evidence, and diverse RawArtifacts (Call, Msg, Contact, Location, Browser).
    2. Run EvidenceNormalizationWorker.
    3. Verify CanonicalEvidence created with valid timestamps, precision, entities, metadata.
    4. Verify Bidirectional Traceability: CanonicalEvidence -> RawArtifact -> Evidence.
    5. Re-run EvidenceNormalizationWorker (Idempotency test) and verify 0 duplicates created.
    """
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with async_session_factory() as session:
        user = User(
            id=user_id,
            email=f"p7_user_{uuid.uuid4().hex[:6]}@ufdr.org",
            name="Phase 7 Investigator",
            password_hash="hashed_pass_placeholder",
            role=UserRole.INVESTIGATOR,
        )
        session.add(user)

        case = Case(
            id=case_id,
            title="Phase 7 Test Case",
            case_number=f"UFDR-P7-{uuid.uuid4().hex[:6]}",
            status="ACTIVE",
            created_by=user_id,
        )
        session.add(case)

        evidence = Evidence(
            id=evidence_id,
            case_id=case_id,
            original_filename="ForensicEvidence_P7.ufdr",
            stored_filename=f"p7_test_{uuid.uuid4().hex}.ufdr",
            storage_path_or_key=f"/tmp/p7_test_{uuid.uuid4().hex}.ufdr",
            file_size=1024 * 50,
            mime_type="application/zip",
            file_extension="ufdr",
            status="PROCESSED",
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            integrity_status="VALID",
            uploaded_by=user_id,
        )
        session.add(evidence)

        # Seed UFDR Parse Job that extracted these raw artifacts
        parse_job_id = uuid.uuid4()
        parse_job = ProcessingJob(
            id=parse_job_id,
            case_id=case_id,
            evidence_id=evidence_id,
            job_type=JobType.UFDR_PARSE,
            priority=JobPriority.NORMAL,
            status=JobStatus.COMPLETED,
            created_by=user_id,
        )
        session.add(parse_job)

        # 2. Seed diverse RawArtifacts
        raw_artifacts = [
            RawArtifact(
                id=uuid.uuid4(),
                case_id=case_id,
                evidence_id=evidence_id,
                processing_job_id=parse_job_id,
                artifact_type=ArtifactType.CALL,
                artifact_fingerprint=hashlib.sha256(b"call_p7_01").hexdigest(),
                source_file="calls.xml",
                source_path="/calls/call_1",
                record_identifier="call_p7_01",
                raw_data={"caller": "+1-555-8888", "receiver": "+1-555-9999", "duration": "45", "timestamp": "2026-09-30T10:00:00Z"},
            ),
            RawArtifact(
                id=uuid.uuid4(),
                case_id=case_id,
                evidence_id=evidence_id,
                processing_job_id=parse_job_id,
                artifact_type=ArtifactType.MESSAGE,
                artifact_fingerprint=hashlib.sha256(b"msg_p7_01").hexdigest(),
                source_file="messages.xml",
                source_path="/messages/msg_1",
                record_identifier="msg_p7_01",
                raw_data={"sender": "+1-555-8888", "receiver": "+1-555-9999", "content": "Classified meeting at 14:00", "timestamp": "2026-09-30T11:00:00Z", "app": "Signal"},
            ),
            RawArtifact(
                id=uuid.uuid4(),
                case_id=case_id,
                evidence_id=evidence_id,
                processing_job_id=parse_job_id,
                artifact_type=ArtifactType.LOCATION,
                artifact_fingerprint=hashlib.sha256(b"loc_p7_01").hexdigest(),
                source_file="gps.xml",
                source_path="/gps/fix_1",
                record_identifier="loc_p7_01",
                raw_data={"latitude": 38.8977, "longitude": -77.0365, "accuracy": 3.0, "timestamp": "2026-09-30T12:00:00Z"},
            ),
            RawArtifact(
                id=uuid.uuid4(),
                case_id=case_id,
                evidence_id=evidence_id,
                processing_job_id=parse_job_id,
                artifact_type=ArtifactType.CONTACT,
                artifact_fingerprint=hashlib.sha256(b"con_p7_01").hexdigest(),
                source_file="contacts.xml",
                source_path="/contacts/contact_1",
                record_identifier="con_p7_01",
                raw_data={"name": "Informant Beta", "phone_numbers": ["+1-555-7777"], "emails": ["beta@secure.org"]},
            ),
            RawArtifact(
                id=uuid.uuid4(),
                case_id=case_id,
                evidence_id=evidence_id,
                processing_job_id=parse_job_id,
                artifact_type=ArtifactType.LOCATION,
                artifact_fingerprint=hashlib.sha256(b"loc_p7_invalid").hexdigest(),
                source_file="gps.xml",
                source_path="/gps/fix_bad",
                record_identifier="loc_p7_invalid",
                raw_data={"latitude": 999.0, "longitude": -999.0, "timestamp": "2026-09-30T12:30:00Z"},  # Out of range
            ),
        ]
        for ra in raw_artifacts:
            session.add(ra)

        # Seed Normalization Job
        job = ProcessingJob(
            id=uuid.uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            job_type=JobType.NORMALIZATION,
            priority=JobPriority.NORMAL,
            status=JobStatus.QUEUED,
            created_by=user_id,
        )
        session.add(job)
        await session.commit()

        # 3. Execute Normalization Worker
        worker = EvidenceNormalizationWorker(batch_size=2)
        success = await worker.execute(job.id, None)
        assert success is True

        # 4. Verify Canonical Records persisted
        repo = CanonicalEvidenceRepository(session)
        count = await repo.count_for_evidence(case_id, evidence_id)
        assert count == 5

        # Check invalid coordinate record was flagged DataQualityStatus.INVALID
        records, total = await repo.list_for_evidence(case_id, evidence_id, page=1, page_size=10)
        assert total == 5

        invalid_rec = next(r for r in records if r.record_identifier == "loc_p7_invalid")
        assert invalid_rec.data_quality_status == DataQualityStatus.INVALID
        assert len(invalid_rec.validation_warnings) > 0

        valid_rec = next(r for r in records if r.record_identifier == "msg_p7_01")
        assert valid_rec.data_quality_status == DataQualityStatus.VALID
        assert valid_rec.content == "Classified meeting at 14:00"
        assert valid_rec.timestamp_precision == TimestampPrecision.SECOND
        assert valid_rec.timestamp_status == TimestampStatus.VALID

        # 5. Verify Bidirectional Traceability:
        # Canonical -> RawArtifact -> Evidence
        originating_raw = await repo.get_originating_raw_artifact(case_id, valid_rec.id)
        assert originating_raw is not None
        assert originating_raw.id == valid_rec.raw_artifact_id
        assert originating_raw.evidence_id == evidence_id
        assert originating_raw.case_id == case_id
        assert originating_raw.record_identifier == "msg_p7_01"

        # 6. IDEMPOTENCY TEST: Run normalization again on same raw artifacts
        job2 = ProcessingJob(
            id=uuid.uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            job_type=JobType.NORMALIZATION,
            priority=JobPriority.NORMAL,
            status=JobStatus.QUEUED,
            created_by=user_id,
        )
        session.add(job2)
        await session.commit()

        success2 = await worker.execute(job2.id, None)
        assert success2 is True

        # Total must STILL be exactly 5 (0 duplicates created)
        count_after_rerun = await repo.count_for_evidence(case_id, evidence_id)
        assert count_after_rerun == 5


# ==============================================================================
# 6. API ENDPOINT TESTS: NORMALIZATION TRIGGER, LISTING & SECURITY
# ==============================================================================

def get_auth_token(cl: TestClient, email: str, password: str, name: str, role: str) -> str:
    cl.post(
        "/api/v1/auth/register",
        json={"email": email, "name": name, "password": password, "role": role},
    )
    res = cl.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]


def test_api_canonical_records_authorization_and_idor():
    """Verify RBAC and IDOR security on canonical evidence endpoints."""
    client = TestClient(app)
    token_inv = get_auth_token(client, f"inv_{uuid.uuid4().hex[:6]}@ufdr.org", "Pass123!Safe", "Inv P7", "INVESTIGATOR")
    token_view = get_auth_token(client, f"view_{uuid.uuid4().hex[:6]}@ufdr.org", "Pass123!Safe", "View P7", "VIEWER")

    headers_inv = {"Authorization": f"Bearer {token_inv}"}
    headers_view = {"Authorization": f"Bearer {token_view}"}

    # Investigator creates Case
    case_res = client.post(
        "/api/v1/cases",
        headers=headers_inv,
        json={"title": "P7 IDOR Case"},
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    ev_id = uuid.uuid4()

    # 1. Unauthenticated request rejected
    res_unauth = client.get(f"/api/v1/cases/{case_id}/evidence/{ev_id}/canonical-records")
    assert res_unauth.status_code == 401

    # 2. Viewer role cannot trigger normalization (403 Forbidden)
    res_view_norm = client.post(
        f"/api/v1/cases/{case_id}/evidence/{ev_id}/normalize",
        headers=headers_view,
        json={"priority": "NORMAL"},
    )
    assert res_view_norm.status_code == 403

    # 3. IDOR: Querying non-existent case returns 404
    fake_case = uuid.uuid4()
    res_idor = client.get(
        f"/api/v1/cases/{fake_case}/evidence/{ev_id}/canonical-records",
        headers=headers_inv,
    )
    assert res_idor.status_code == 404
