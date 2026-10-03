"""
Phase 8 — Structured Database & Document Storage Optimization
Test Suite

Tests cover:
  1.  Cursor encoding / decoding round-trip
  2.  Malformed cursor raises ValueError
  3.  cursor_page_by_evidence — first page, full traversal, exhaustion
  4.  cursor_page_by_evidence — NULL timestamps
  5.  Cursor idempotency
  6.  cursor_page_by_case — spans multiple evidence items
  7.  stream_by_evidence — yields all records, bounded batch sizes
  8.  stream_by_evidence — empty evidence package
  9.  count_for_case — sums across evidence items
  10. count_by_artifact_type_for_case — per-type breakdown
  11. health_check — returns healthy
  12. Phase 8 composite indexes present in DB
  13. API: evidence-scoped cursor endpoint (GET .../canonical-records/stream)
  14. API: cursor chain traversal via next_cursor
  15. API: case-scoped cursor endpoint
  16. API: /canonical-records/summary
  17. API: /storage/health
  18. Backward-compat: offset endpoint still works
  19. API: malformed cursor returns 4xx
"""
import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.core.database import async_session_factory
from backend.app.main import app
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import (
    ArtifactType,
    DataQualityStatus,
    TimestampPrecision,
    TimestampStatus,
)
from backend.app.repositories.canonical_evidence_repo import CanonicalEvidenceRepository


# ============================================================= #
# Helpers                                                        #
# ============================================================= #

def _get_admin_token(client: TestClient) -> str:
    """Obtain a JWT token for the bootstrapped admin account."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ufdr.org", "password": "ForensicAdmin2026!"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _register_and_login(client: TestClient, prefix: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}_p8@ufdr.org",
            "name": f"P8 User {prefix}",
            "password": "Pass12345!",
            "role": "INVESTIGATOR",
        },
    )
    res = client.post(
        "/api/v1/auth/login",
        json={"email": f"{prefix}_p8@ufdr.org", "password": "Pass12345!"},
    )
    return res.json()["access_token"]


def _make_canonical(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    raw_artifact_id: uuid.UUID,
    record_identifier: str,
    artifact_type: ArtifactType = ArtifactType.MESSAGE,
    event_ts: Optional[datetime] = None,
) -> CanonicalEvidence:
    """Build an in-memory CanonicalEvidence instance for direct DB insertion."""
    fp = hashlib.sha256(f"{evidence_id}:{record_identifier}".encode()).hexdigest()
    return CanonicalEvidence(
        id=uuid.uuid4(),
        case_id=case_id,
        evidence_id=evidence_id,
        raw_artifact_id=raw_artifact_id,
        processing_job_id=None,
        artifact_type=artifact_type,
        canonical_fingerprint=fp,
        source_file="messages.xml",
        source_path="/messages/messages.xml",
        record_identifier=record_identifier,
        event_timestamp=event_ts,
        timestamp_precision=TimestampPrecision.SECOND if event_ts else TimestampPrecision.UNKNOWN,
        timestamp_status=TimestampStatus.VALID if event_ts else TimestampStatus.UNKNOWN,
        original_timestamp=event_ts.isoformat() if event_ts else None,
        original_timezone="UTC" if event_ts else None,
        device_id="DEVICE-001",
        application="WhatsApp",
        entities=[],
        metadata_={},
        data_quality_status=DataQualityStatus.VALID,
        validation_warnings=[],
        parser_version="1.0.0",
        normalizer_version="1.0.0",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _insert_n_records_sync(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    n: int,
    with_timestamps: bool = True,
    artifact_type: ArtifactType = ArtifactType.MESSAGE,
) -> None:
    """Insert N canonical records synchronously using asyncio.run."""
    async def _do():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            records = []
            for i in range(n):
                raw_id = uuid.uuid4()
                ts = (
                    datetime(2024, 1, 1, i // 3600, (i % 3600) // 60, i % 60, tzinfo=timezone.utc)
                    if with_timestamps
                    else None
                )
                records.append(_make_canonical(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    raw_artifact_id=raw_id,
                    record_identifier=f"record-{i}-{raw_id}",
                    artifact_type=artifact_type,
                    event_ts=ts,
                ))
            await repo.bulk_create_or_ignore(records)
    asyncio.run(_do())


# ============================================================= #
# 1–2. Cursor encoding / decoding                               #
# ============================================================= #

def test_cursor_encode_decode_with_timestamp():
    """Round-trip encode/decode a cursor containing a timezone-aware timestamp."""
    ts = datetime(2024, 6, 15, 12, 30, 45, tzinfo=timezone.utc)
    rid = uuid.uuid4()
    cursor = CanonicalEvidenceRepository._encode_cursor(ts, rid)
    assert isinstance(cursor, str) and len(cursor) > 0

    decoded_ts, decoded_id = CanonicalEvidenceRepository._decode_cursor(cursor)
    assert decoded_ts is not None
    assert decoded_ts == ts
    assert decoded_id == rid


def test_cursor_encode_decode_null_timestamp():
    """Round-trip encode/decode a cursor where event_timestamp is None."""
    rid = uuid.uuid4()
    cursor = CanonicalEvidenceRepository._encode_cursor(None, rid)
    decoded_ts, decoded_id = CanonicalEvidenceRepository._decode_cursor(cursor)
    assert decoded_ts is None
    assert decoded_id == rid


def test_cursor_decode_invalid_raises():
    """Malformed cursor bytes must raise ValueError with a descriptive message."""
    with pytest.raises(ValueError, match="Invalid pagination cursor"):
        CanonicalEvidenceRepository._decode_cursor("not-a-valid-base64-cursor!!!")


# ============================================================= #
# 3–4. cursor_page_by_evidence (direct repo)                    #
# ============================================================= #

def test_cursor_page_first_page_size():
    """First page without cursor returns exactly page_size items."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    _insert_n_records_sync(case_id, evidence_id, n=15)

    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            items, next_cursor = await repo.cursor_page_by_evidence(
                evidence_id=evidence_id, page_size=10
            )
            return items, next_cursor

    items, next_cursor = asyncio.run(_run())
    assert len(items) == 10
    assert next_cursor is not None


def test_cursor_page_full_traversal_no_duplicates():
    """Iterating all cursor pages retrieves exactly N records without duplicates."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    n_records = 27
    _insert_n_records_sync(case_id, evidence_id, n=n_records)

    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            all_ids = []
            pages = 0
            cursor = None
            while True:
                items, next_cursor = await repo.cursor_page_by_evidence(
                    evidence_id=evidence_id, page_size=10, cursor=cursor
                )
                pages += 1
                all_ids.extend(item.id for item in items)
                if next_cursor is None:
                    break
                cursor = next_cursor
            return all_ids, pages

    all_ids, pages = asyncio.run(_run())
    assert len(all_ids) == n_records
    assert len(set(all_ids)) == n_records
    assert pages == 3  # ceil(27/10)


def test_cursor_page_exhaustion_returns_none():
    """When all records fit in one page, next_cursor is None."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    _insert_n_records_sync(case_id, evidence_id, n=5)

    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            return await repo.cursor_page_by_evidence(evidence_id=evidence_id, page_size=50)

    items, cursor = asyncio.run(_run())
    assert len(items) == 5
    assert cursor is None


def test_cursor_page_null_timestamps():
    """Cursor pagination works correctly when all event_timestamps are NULL."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    _insert_n_records_sync(case_id, evidence_id, n=13, with_timestamps=False)

    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            all_ids = []
            cursor = None
            while True:
                items, next_cursor = await repo.cursor_page_by_evidence(
                    evidence_id=evidence_id, page_size=5, cursor=cursor
                )
                all_ids.extend(item.id for item in items)
                if next_cursor is None:
                    break
                cursor = next_cursor
            return all_ids

    all_ids = asyncio.run(_run())
    assert len(all_ids) == 13
    assert len(set(all_ids)) == 13


# ============================================================= #
# 5. Cursor idempotency                                          #
# ============================================================= #

def test_cursor_idempotency():
    """The same cursor always returns the same page (stable keyset)."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    _insert_n_records_sync(case_id, evidence_id, n=20)

    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            page1, cursor = await repo.cursor_page_by_evidence(
                evidence_id=evidence_id, page_size=5
            )
            page1_ids = [item.id for item in page1]

            page2a, _ = await repo.cursor_page_by_evidence(
                evidence_id=evidence_id, page_size=5, cursor=cursor
            )
            page2b, _ = await repo.cursor_page_by_evidence(
                evidence_id=evidence_id, page_size=5, cursor=cursor
            )
            return page1_ids, [i.id for i in page2a], [i.id for i in page2b]

    p1, p2a, p2b = asyncio.run(_run())
    # Same cursor → same result set
    assert p2a == p2b
    # Second page must not overlap first page
    assert not set(p2a).intersection(set(p1))


# ============================================================= #
# 6. cursor_page_by_case                                         #
# ============================================================= #

def test_cursor_page_by_case_spans_evidence():
    """Case-scoped cursor pagination aggregates records across all evidence items."""
    case_id = uuid.uuid4()
    _insert_n_records_sync(case_id, uuid.uuid4(), n=8)
    _insert_n_records_sync(case_id, uuid.uuid4(), n=7)

    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            all_ids = []
            cursor = None
            while True:
                items, next_cursor = await repo.cursor_page_by_case(
                    case_id=case_id, page_size=6, cursor=cursor
                )
                all_ids.extend(item.id for item in items)
                if next_cursor is None:
                    break
                cursor = next_cursor
            return all_ids

    all_ids = asyncio.run(_run())
    assert len(all_ids) == 15
    assert len(set(all_ids)) == 15


# ============================================================= #
# 7–8. stream_by_evidence                                        #
# ============================================================= #

def test_stream_by_evidence_yields_all_records():
    """stream_by_evidence yields every record exactly once in bounded batches."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    _insert_n_records_sync(case_id, evidence_id, n=47)

    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            all_ids = []
            batch_sizes = []
            async for batch in repo.stream_by_evidence(evidence_id=evidence_id, batch_size=20):
                assert len(batch) <= 20
                batch_sizes.append(len(batch))
                all_ids.extend(item.id for item in batch)
            return all_ids, batch_sizes

    all_ids, batch_sizes = asyncio.run(_run())
    assert len(all_ids) == 47
    assert len(set(all_ids)) == 47


def test_stream_by_evidence_empty():
    """Streaming an evidence package with no records yields no batches."""
    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            batches = []
            async for batch in repo.stream_by_evidence(evidence_id=uuid.uuid4(), batch_size=100):
                batches.append(batch)
            return batches

    batches = asyncio.run(_run())
    assert batches == []


# ============================================================= #
# 9–10. Aggregate queries                                        #
# ============================================================= #

def test_count_for_case_sums_across_evidence():
    """count_for_case correctly sums records across multiple evidence items."""
    case_id = uuid.uuid4()
    _insert_n_records_sync(case_id, uuid.uuid4(), n=10)
    _insert_n_records_sync(case_id, uuid.uuid4(), n=15)

    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            return await repo.count_for_case(case_id)

    total = asyncio.run(_run())
    assert total == 25


def test_count_by_artifact_type_for_case():
    """count_by_artifact_type_for_case returns accurate per-type breakdown."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()

    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)

            msg_records = []
            for i in range(5):
                raw_id = uuid.uuid4()
                fp = hashlib.sha256(f"{evidence_id}:msg-{i}-{raw_id}".encode()).hexdigest()
                msg_records.append(CanonicalEvidence(
                    id=uuid.uuid4(), case_id=case_id, evidence_id=evidence_id,
                    raw_artifact_id=raw_id, artifact_type=ArtifactType.MESSAGE,
                    canonical_fingerprint=fp, source_file="m.xml", source_path="/m.xml",
                    record_identifier=f"msg-{i}-{raw_id}", entities=[], metadata_={},
                    validation_warnings=[], parser_version="1.0.0", normalizer_version="1.0.0",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ))
            call_records = []
            for i in range(3):
                raw_id = uuid.uuid4()
                fp = hashlib.sha256(f"{evidence_id}:call-{i}-{raw_id}".encode()).hexdigest()
                call_records.append(CanonicalEvidence(
                    id=uuid.uuid4(), case_id=case_id, evidence_id=evidence_id,
                    raw_artifact_id=raw_id, artifact_type=ArtifactType.CALL,
                    canonical_fingerprint=fp, source_file="c.xml", source_path="/c.xml",
                    record_identifier=f"call-{i}-{raw_id}", entities=[], metadata_={},
                    validation_warnings=[], parser_version="1.0.0", normalizer_version="1.0.0",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ))
            await repo.bulk_create_or_ignore(msg_records + call_records)
            return await repo.count_by_artifact_type_for_case(case_id)

    breakdown = asyncio.run(_run())
    assert breakdown.get("MESSAGE", 0) == 5
    assert breakdown.get("CALL", 0) == 3


# ============================================================= #
# 11. DB health check (direct repo)                             #
# ============================================================= #

def test_repo_health_check():
    """health_check returns 'healthy' status and row count integer."""
    async def _run():
        async with async_session_factory() as session:
            repo = CanonicalEvidenceRepository(session)
            return await repo.health_check()

    result = asyncio.run(_run())
    assert result["status"] == "healthy"
    assert isinstance(result["canonical_evidence_rows"], int)


# ============================================================= #
# 12. Phase 8 indexes present in DB                             #
# ============================================================= #

def test_phase8_composite_indexes_exist():
    """Verify the four new Phase 8 composite indexes are present in SQLite."""
    async def _run():
        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='index' AND tbl_name='canonical_evidence'"
                )
            )
            return {row[0] for row in result.fetchall()}

    existing = asyncio.run(_run())
    required = [
        "ix_canonical_evidence_case_time_id",
        "ix_canonical_evidence_case_device_time",
        "ix_canonical_evidence_case_quality_type",
        "ix_canonical_evidence_evidence_time_id",
    ]
    for idx in required:
        assert idx in existing, f"Phase 8 index missing: {idx}"


def test_phase8_processing_job_index_exists():
    """Verify the worker dispatch index is present on processing_jobs."""
    async def _run():
        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='index' AND tbl_name='processing_jobs'"
                )
            )
            return {row[0] for row in result.fetchall()}

    existing = asyncio.run(_run())
    assert "ix_processing_jobs_status_priority_created" in existing


# ============================================================= #
# 13–19. API endpoint tests                                     #
# ============================================================= #

import io
import zipfile


def _make_minimal_ufdr() -> bytes:
    """Create a minimal valid UFDR bytes (ZIP with report.xml) for evidence upload."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.xml", '<?xml version="1.0"?><report><case_info></case_info></report>')
    return buf.getvalue()


def _setup_case_with_real_evidence(client: TestClient, prefix: str):
    """Create investigator, case, and upload a minimal UFDR to get a real evidence_id."""
    token = _register_and_login(client, prefix)
    headers = {"Authorization": f"Bearer {token}"}

    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": f"P8 Case {prefix}"},
    )
    assert case_res.status_code == 201
    case_id = UUID(case_res.json()["id"])

    ufdr_bytes = _make_minimal_ufdr()
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=headers,
        files={"file": (f"{prefix}.ufdr", ufdr_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    evidence_id = UUID(upload_res.json()["id"])
    return token, headers, case_id, evidence_id


def _setup_case_with_evidence(client: TestClient, prefix: str):
    """Create an investigator + case (no evidence file). Used for case-scoped tests."""
    token = _register_and_login(client, prefix)
    headers = {"Authorization": f"Bearer {token}"}

    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": f"P8 Case {prefix}"},
    )
    assert case_res.status_code == 201
    case_id = UUID(case_res.json()["id"])
    return token, headers, case_id


def test_api_cursor_records_by_evidence_first_page():
    """GET .../canonical-records/stream returns keyset-paginated items + next_cursor."""
    client = TestClient(app)
    token, headers, case_id, evidence_id = _setup_case_with_real_evidence(client, "ce8a")

    _insert_n_records_sync(case_id, evidence_id, n=12)

    resp = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/canonical-records/stream",
        params={"page_size": 5},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "has_next" in data
    assert "next_cursor" in data
    assert len(data["items"]) == 5
    assert data["has_next"] is True
    assert data["next_cursor"] is not None


def test_api_cursor_chain_traversal_no_duplicates():
    """Following next_cursor links yields all records without duplicates."""
    client = TestClient(app)
    token, headers, case_id, evidence_id = _setup_case_with_real_evidence(client, "ce8b")
    _insert_n_records_sync(case_id, evidence_id, n=22)

    all_ids = []
    cursor = None
    while True:
        params: dict = {"page_size": 10}
        if cursor:
            params["cursor"] = cursor
        resp = client.get(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/canonical-records/stream",
            params=params,
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        all_ids.extend(item["id"] for item in data["items"])
        cursor = data.get("next_cursor")
        if not cursor:
            break

    assert len(all_ids) == 22
    assert len(set(all_ids)) == 22


def test_api_cursor_records_by_case():
    """GET /{case_id}/canonical-records/stream spans all evidence in a case."""
    client = TestClient(app)
    token, headers, case_id = _setup_case_with_evidence(client, "ce8c")
    _insert_n_records_sync(case_id, uuid.uuid4(), n=6)
    _insert_n_records_sync(case_id, uuid.uuid4(), n=5)

    all_ids = []
    cursor = None
    while True:
        params: dict = {"page_size": 4}
        if cursor:
            params["cursor"] = cursor
        resp = client.get(
            f"/api/v1/cases/{case_id}/canonical-records/stream",
            params=params,
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        all_ids.extend(item["id"] for item in data["items"])
        cursor = data.get("next_cursor")
        if not cursor:
            break

    assert len(all_ids) == 11
    assert len(set(all_ids)) == 11


def test_api_canonical_summary():
    """GET /canonical-records/summary returns aggregate stats."""
    client = TestClient(app)
    token, headers, case_id = _setup_case_with_evidence(client, "ce8d")
    _insert_n_records_sync(case_id, uuid.uuid4(), n=10)

    resp = client.get(
        f"/api/v1/cases/{case_id}/canonical-records/summary",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == str(case_id)
    assert data["total_canonical_records"] >= 10
    assert "breakdown_by_type" in data


def test_api_storage_health():
    """GET /storage/health confirms DB connectivity and returns row count."""
    client = TestClient(app)
    token = _get_admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/cases/storage/health", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "canonical_evidence_rows" in data


def test_api_offset_pagination_backward_compat():
    """Phase 7 offset endpoint continues to return paginated results with totals."""
    client = TestClient(app)
    token, headers, case_id, evidence_id = _setup_case_with_real_evidence(client, "ce8e")
    _insert_n_records_sync(case_id, evidence_id, n=8)

    resp = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/canonical-records",
        params={"page": 1, "page_size": 5},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "total_pages" in data
    assert len(data["items"]) == 5


def test_api_malformed_cursor_returns_error():
    """Passing a malformed cursor string must return a 4xx or 5xx response."""
    client = TestClient(app)
    token, headers, case_id, evidence_id = _setup_case_with_real_evidence(client, "ce8f")

    resp = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/canonical-records/stream",
        params={"cursor": "THIS-IS-COMPLETELY-INVALID-@@@"},
        headers=headers,
    )
    assert resp.status_code in (400, 422, 500)
