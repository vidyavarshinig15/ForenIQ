"""
Phase 9 — Forensic Search Engine Tests

Coverage:
  1. Exact identifier search (record_identifier, device_id)
  2. Partial text search (content, application)
  3. Artifact type filter
  4. Evidence ID filter (with cross-case IDOR check)
  5. Application filter (case-insensitive)
  6. Device ID filter
  7. Date range filter
  8. Date range validation (start > end rejected)
  9. Timestamp precision filter
  10. Source file filter
  11. Combined filter (AND semantics)
  12. Entity value search
  13. Cursor pagination (no duplicates)
  14. Sort ordering
  15. Page size cap enforcement
  16. Query length cap enforcement
  17. Wildcard-only query rejection
  18. Malformed cursor rejection
  19. Case isolation (IDOR: Case A cannot see Case B results)
  20. Cross-case evidence filter IDOR
  21. Unauthenticated access rejected
  22. Search history recorded after search
  23. Search history is case-scoped
  24. Facets return correct counts
  25. Empty result set
  26. Unicode query support
  27. Special characters handled safely (SQL injection attempt)
  28. Search history endpoint (authorized)

Architecture note:
  All tests use TestClient (synchronous HTTPX wrapper) and in-memory SQLite
  via the shared test database fixture from conftest.py.
  Direct DB inserts via _insert_canonical_record_sync() bypass the normalization
  pipeline to isolate search logic.
"""
import asyncio
import uuid
import io
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.main import app
from backend.app.core.database import async_session_factory
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import (
    ArtifactType,
    DataQualityStatus,
    TimestampPrecision,
    TimestampStatus,
)

# ============================================================= #
# Helpers                                                       #
# ============================================================= #

def _make_minimal_ufdr() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.xml", '<?xml version="1.0"?><report><case_info></case_info></report>')
    return buf.getvalue()


def _register_and_login(client: TestClient, prefix: str) -> str:
    email = f"s9_{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Search9Pass!", "name": f"Agent {prefix}"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Search9Pass!"},
    )
    return resp.json()["access_token"]


def _get_admin_token(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@ufdr.org", "password": "ForensicAdmin2026!"},
    )
    return resp.json()["access_token"]


def _setup_case(client: TestClient, prefix: str):
    """Create user + case, return (token, headers, case_id)."""
    token = _register_and_login(client, prefix)
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/v1/cases", headers=headers, json={"title": f"Search9 {prefix}"})
    assert res.status_code == 201
    return token, headers, UUID(res.json()["id"])


def _setup_case_with_evidence(client: TestClient, prefix: str):
    """Create user + case + uploaded evidence, return (token, headers, case_id, evidence_id)."""
    token, headers, case_id = _setup_case(client, prefix)
    ufdr = _make_minimal_ufdr()
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=headers,
        files={"file": (f"{prefix}.ufdr", ufdr, "application/zip")},
    )
    assert res.status_code == 201
    return token, headers, case_id, UUID(res.json()["id"])


def _insert_canonical_record_sync(
    case_id: UUID,
    evidence_id: UUID,
    *,
    artifact_type: ArtifactType = ArtifactType.MESSAGE,
    content: Optional[str] = None,
    application: Optional[str] = "WhatsApp",
    device_id: Optional[str] = "device-001",
    event_timestamp: Optional[datetime] = None,
    source_file: str = "messages.xml",
    record_identifier: Optional[str] = None,
    entities: Optional[list] = None,
    timestamp_precision: TimestampPrecision = TimestampPrecision.SECOND,
    data_quality_status: DataQualityStatus = DataQualityStatus.VALID,
) -> CanonicalEvidence:
    """Insert a CanonicalEvidence record directly into the DB for test isolation."""
    async def _run():
        async with async_session_factory() as session:
            rec = CanonicalEvidence(
                id=uuid.uuid4(),
                case_id=case_id,
                evidence_id=evidence_id,
                raw_artifact_id=uuid.uuid4(),
                artifact_type=artifact_type,
                canonical_fingerprint=uuid.uuid4().hex,
                source_file=source_file,
                source_path=f"data/{source_file}",
                record_identifier=record_identifier or f"rec-{uuid.uuid4().hex[:8]}",
                event_timestamp=event_timestamp or datetime.now(timezone.utc),
                timestamp_precision=timestamp_precision,
                timestamp_status=TimestampStatus.VALID,
                device_id=device_id,
                application=application,
                content=content,
                entities=entities or [],
                metadata_={},
                data_quality_status=data_quality_status,
                validation_warnings=[],
                parser_version="1.0.0",
                normalizer_version="1.0.0",
            )
            session.add(rec)
            await session.commit()
            await session.refresh(rec)
            return rec

    return asyncio.run(_run())


# ============================================================= #
# 1. Exact identifier search                                    #
# ============================================================= #

def test_exact_record_identifier_search():
    """Searching by record_identifier value returns that record."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9a")
    unique_id = f"REC-EXACT-{uuid.uuid4().hex[:8]}"
    _insert_canonical_record_sync(case_id, evidence_id, record_identifier=unique_id)

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"q": unique_id},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]
    ids_found = [r["id"] for r in data["results"]]
    # At least one result matches
    assert any(
        r["source"]["record_identifier"] == unique_id
        for r in data["results"]
    )


# ============================================================= #
# 2. Partial text search                                        #
# ============================================================= #

def test_partial_text_search_content():
    """Partial text match in content field returns matching records."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9b")
    unique_fragment = f"xray{uuid.uuid4().hex[:6]}delta"
    _insert_canonical_record_sync(
        case_id, evidence_id,
        content=f"Meeting at 5pm. {unique_fragment} is the code.",
    )

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"q": unique_fragment},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(
        unique_fragment in (r.get("content_preview") or "")
        for r in data["results"]
    )


# ============================================================= #
# 3. Artifact type filter                                       #
# ============================================================= #

def test_artifact_type_filter_returns_only_matching_type():
    """artifact_type=CALL returns only CALL records."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9c")
    _insert_canonical_record_sync(case_id, evidence_id, artifact_type=ArtifactType.CALL)
    _insert_canonical_record_sync(case_id, evidence_id, artifact_type=ArtifactType.MESSAGE)

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"artifact_type": "CALL"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]
    for r in data["results"]:
        assert r["artifact_type"] == "CALL"


# ============================================================= #
# 4. Evidence ID filter                                         #
# ============================================================= #

def test_evidence_id_filter_restricts_results():
    """evidence_id filter only returns records from that evidence."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9d")
    # Insert record for this evidence
    _insert_canonical_record_sync(case_id, evidence_id, application="FilterTestApp")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"evidence_id": str(evidence_id)},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    for r in data["results"]:
        assert r["source"]["evidence_id"] == str(evidence_id)


# ============================================================= #
# 5. Application filter (case-insensitive)                      #
# ============================================================= #

def test_application_filter_case_insensitive():
    """application=whatsapp matches records with application='WhatsApp'."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9e")
    _insert_canonical_record_sync(case_id, evidence_id, application="WhatsApp")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"application": "whatsapp"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]
    # All results should have an application matching whatsapp (case-insensitive)
    for r in data["results"]:
        assert "whatsapp" in (r["application"] or "").lower()


# ============================================================= #
# 6. Device ID filter                                           #
# ============================================================= #

def test_device_id_exact_filter():
    """device_id filter returns only records with that exact device_id."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9f")
    target_device = f"DEV-{uuid.uuid4().hex[:8]}"
    _insert_canonical_record_sync(case_id, evidence_id, device_id=target_device)
    _insert_canonical_record_sync(case_id, evidence_id, device_id="other-device")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"device_id": target_device},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]
    for r in data["results"]:
        assert r["device_id"] == target_device


# ============================================================= #
# 7. Date range filter                                          #
# ============================================================= #

def test_date_range_filter_returns_records_in_range():
    """start_time / end_time filter returns only records within the range."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9g")

    ts_in = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    ts_out = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)

    _insert_canonical_record_sync(case_id, evidence_id, event_timestamp=ts_in)
    _insert_canonical_record_sync(case_id, evidence_id, event_timestamp=ts_out)

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={
            "start_time": "2026-09-01T00:00:00Z",
            "end_time": "2026-09-30T23:59:59Z",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]
    for r in data["results"]:
        if r["event_timestamp"] is not None:
            ts_raw = r["event_timestamp"]
            # Normalize Z or +00:00 suffix; SQLite may return naive timestamps
            if ts_raw.endswith("Z"):
                ts_raw = ts_raw[:-1] + "+00:00"
            ts = datetime.fromisoformat(ts_raw)
            # Make aware if SQLite returned naive
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            assert datetime(2026, 9, 1, tzinfo=timezone.utc) <= ts <= datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc)


# ============================================================= #
# 8. Date range validation                                      #
# ============================================================= #

def test_date_range_start_after_end_rejected():
    """start_time > end_time must return HTTP 400."""
    client = TestClient(app)
    _, headers, case_id, _ = _setup_case_with_evidence(client, "s9h")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={
            "start_time": "2026-12-31T00:00:00Z",
            "end_time": "2026-01-01T00:00:00Z",
        },
        headers=headers,
    )
    assert resp.status_code == 400


# ============================================================= #
# 9. Timestamp precision filter                                 #
# ============================================================= #

def test_timestamp_precision_filter():
    """timestamp_precision=DAY returns only records with that precision."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9i")
    _insert_canonical_record_sync(case_id, evidence_id, timestamp_precision=TimestampPrecision.DAY)
    _insert_canonical_record_sync(case_id, evidence_id, timestamp_precision=TimestampPrecision.SECOND)

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"timestamp_precision": "DAY"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]
    for r in data["results"]:
        assert r["timestamp_precision"] == "DAY"


# ============================================================= #
# 10. Source file filter                                        #
# ============================================================= #

def test_source_file_filter_exact():
    """source_file filter restricts results to that source file."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9j")
    _insert_canonical_record_sync(case_id, evidence_id, source_file="calls.xml")
    _insert_canonical_record_sync(case_id, evidence_id, source_file="messages.xml")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"source_file": "calls.xml"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]
    for r in data["results"]:
        assert r["source"]["source_file"] == "calls.xml"


# ============================================================= #
# 11. Combined filters (AND semantics)                          #
# ============================================================= #

def test_combined_filters_use_and_semantics():
    """Multiple filters combine as AND: only records matching ALL conditions returned."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9k")

    ts = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)
    _insert_canonical_record_sync(
        case_id, evidence_id,
        artifact_type=ArtifactType.MESSAGE,
        application="WhatsApp",
        event_timestamp=ts,
    )
    # This record should NOT match (wrong type)
    _insert_canonical_record_sync(
        case_id, evidence_id,
        artifact_type=ArtifactType.CALL,
        application="WhatsApp",
        event_timestamp=ts,
    )

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={
            "artifact_type": "MESSAGE",
            "application": "WhatsApp",
            "start_time": "2026-09-01T00:00:00Z",
            "end_time": "2026-09-30T23:59:59Z",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]
    for r in data["results"]:
        assert r["artifact_type"] == "MESSAGE"


# ============================================================= #
# 12. Entity value search                                       #
# ============================================================= #

def test_entity_value_search():
    """entity_value search finds records containing that value in entities array."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9l")
    target_phone = "+919876543210"
    _insert_canonical_record_sync(
        case_id, evidence_id,
        entities=[{"type": "PHONE_NUMBER", "value": target_phone}],
    )
    _insert_canonical_record_sync(case_id, evidence_id, entities=[])

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"entity_value": target_phone},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]
    # At least one result should have the phone in matched_entities
    found = False
    for r in data["results"]:
        for ent in r.get("matched_entities", []):
            if target_phone in str(ent.get("value", "")):
                found = True
    assert found


# ============================================================= #
# 13. Cursor pagination — no duplicates                         #
# ============================================================= #

def test_cursor_pagination_no_duplicates():
    """Cursor chain delivers all records without duplication."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9m")

    for i in range(15):
        _insert_canonical_record_sync(
            case_id, evidence_id,
            event_timestamp=datetime(2026, 9, i + 1, 12, 0, 0, tzinfo=timezone.utc),
        )

    all_ids = []
    cursor = None
    pages = 0
    while True:
        params: Dict[str, Any] = {"page_size": 5}
        if cursor:
            params["cursor"] = cursor
        resp = client.get(
            f"/api/v1/cases/{case_id}/search",
            params=params,
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        all_ids.extend(r["id"] for r in data["results"])
        cursor = data["pagination"].get("next_cursor")
        pages += 1
        if not cursor:
            break
        assert pages <= 10  # safety limit

    assert len(all_ids) >= 15
    assert len(set(all_ids)) == len(all_ids)  # no duplicates


# ============================================================= #
# 14. Sort ordering                                             #
# ============================================================= #

def test_sort_timestamp_asc():
    """timestamp_asc returns records in ascending timestamp order."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9n")
    for i in range(5):
        _insert_canonical_record_sync(
            case_id, evidence_id,
            event_timestamp=datetime(2026, 9, i + 1, 12, 0, 0, tzinfo=timezone.utc),
        )

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"sort": "timestamp_asc", "page_size": 10},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    timestamps = [
        r["event_timestamp"] for r in data["results"] if r["event_timestamp"]
    ]
    assert timestamps == sorted(timestamps)


# ============================================================= #
# 15. Page size cap enforcement                                 #
# ============================================================= #

def test_page_size_cap_enforced():
    """page_size > MAX_SEARCH_PAGE_SIZE (100) is rejected."""
    client = TestClient(app)
    _, headers, case_id, _ = _setup_case_with_evidence(client, "s9o")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"page_size": 9999},
        headers=headers,
    )
    assert resp.status_code in (400, 422)


# ============================================================= #
# 16. Query length cap enforcement                              #
# ============================================================= #

def test_query_length_cap_enforced():
    """Query exceeding MAX_QUERY_LENGTH (500 chars) is rejected."""
    client = TestClient(app)
    _, headers, case_id, _ = _setup_case_with_evidence(client, "s9p")

    long_q = "A" * 501
    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"q": long_q},
        headers=headers,
    )
    assert resp.status_code in (400, 422)


# ============================================================= #
# 17. Wildcard-only query rejection                             #
# ============================================================= #

def test_wildcard_only_query_rejected():
    """A query consisting only of % and _ characters must be rejected."""
    client = TestClient(app)
    _, headers, case_id, _ = _setup_case_with_evidence(client, "s9q")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"q": "%%%___%%%"},
        headers=headers,
    )
    assert resp.status_code == 400


# ============================================================= #
# 18. Malformed cursor rejection                                #
# ============================================================= #

def test_malformed_cursor_rejected():
    """Malformed cursor string returns HTTP 400."""
    client = TestClient(app)
    _, headers, case_id, _ = _setup_case_with_evidence(client, "s9r")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"cursor": "TOTALLY-INVALID-CURSOR!!!"},
        headers=headers,
    )
    assert resp.status_code in (400, 422)


# ============================================================= #
# 19. Case isolation — IDOR test                               #
# ============================================================= #

def test_case_isolation_idor_protection():
    """Investigator for Case A cannot see Case B's evidence via search."""
    client = TestClient(app)
    _, headers_a, case_a, evidence_a = _setup_case_with_evidence(client, "s9s_a")
    _, headers_b, case_b, evidence_b = _setup_case_with_evidence(client, "s9s_b")

    unique_secret = f"CASE-B-SECRET-{uuid.uuid4().hex}"
    _insert_canonical_record_sync(
        case_b, evidence_b,
        content=unique_secret,
        record_identifier=unique_secret,
    )

    # User A searches their own case with Case B's secret term
    resp = client.get(
        f"/api/v1/cases/{case_a}/search",
        params={"q": unique_secret},
        headers=headers_a,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Must find 0 results from Case B
    assert len(data["results"]) == 0


# ============================================================= #
# 20. Cross-case evidence filter IDOR                           #
# ============================================================= #

def test_cross_case_evidence_id_rejected():
    """Using evidence_id from Case B while searching Case A returns 404."""
    client = TestClient(app)
    _, headers_a, case_a, _ = _setup_case_with_evidence(client, "s9t_a")
    _, headers_b, case_b, evidence_b = _setup_case_with_evidence(client, "s9t_b")

    resp = client.get(
        f"/api/v1/cases/{case_a}/search",
        params={"evidence_id": str(evidence_b)},
        headers=headers_a,
    )
    # Must be rejected — evidence_b doesn't belong to case_a
    assert resp.status_code == 404


# ============================================================= #
# 21. Unauthenticated access rejected                           #
# ============================================================= #

def test_search_requires_authentication():
    """Search without a token returns 401."""
    client = TestClient(app)
    _, _, case_id, _ = _setup_case_with_evidence(client, "s9u")

    resp = client.get(f"/api/v1/cases/{case_id}/search", params={"q": "test"})
    assert resp.status_code == 401


# ============================================================= #
# 22. Search history recorded                                   #
# ============================================================= #

def test_search_history_recorded_after_search():
    """After a search, an entry appears in the search history endpoint."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9v")
    _insert_canonical_record_sync(case_id, evidence_id, content="history-check-content")

    client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"q": "history-check-content"},
        headers=headers,
    )

    hist_resp = client.get(
        f"/api/v1/cases/{case_id}/search/history",
        headers=headers,
    )
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["total"] >= 1
    assert any(
        "history-check-content" in (item.get("query") or "")
        for item in hist_data["items"]
    )


# ============================================================= #
# 23. Search history is case-scoped                             #
# ============================================================= #

def test_search_history_is_case_scoped():
    """User A's search history for Case A does not appear in Case B's history."""
    client = TestClient(app)
    _, headers_a, case_a, evidence_a = _setup_case_with_evidence(client, "s9w_a")
    _, headers_b, case_b, evidence_b = _setup_case_with_evidence(client, "s9w_b")

    unique_q = f"UNIQUE-Q-{uuid.uuid4().hex}"

    # User A searches Case A
    client.get(
        f"/api/v1/cases/{case_a}/search",
        params={"q": unique_q},
        headers=headers_a,
    )

    # User B retrieves history for Case B — should not contain User A's search
    hist_resp = client.get(
        f"/api/v1/cases/{case_b}/search/history",
        headers=headers_b,
    )
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    for item in hist_data["items"]:
        assert unique_q not in (item.get("query") or "")


# ============================================================= #
# 24. Facets return correct counts                              #
# ============================================================= #

def test_facets_return_correct_counts():
    """include_facets=true returns real counts per artifact type."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9x")
    for _ in range(3):
        _insert_canonical_record_sync(case_id, evidence_id, artifact_type=ArtifactType.MESSAGE)
    for _ in range(2):
        _insert_canonical_record_sync(case_id, evidence_id, artifact_type=ArtifactType.CALL)

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"include_facets": "true"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    facets = data.get("facets")
    assert facets is not None
    by_type = facets.get("by_artifact_type", {})
    assert by_type.get("MESSAGE", 0) >= 3
    assert by_type.get("CALL", 0) >= 2


# ============================================================= #
# 25. Empty result set                                          #
# ============================================================= #

def test_empty_results_return_empty_list_not_error():
    """Searching for a term that matches nothing returns empty results, not an error."""
    client = TestClient(app)
    _, headers, case_id, _ = _setup_case_with_evidence(client, "s9y")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"q": f"NO-MATCH-{uuid.uuid4().hex}"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == []
    assert data["pagination"]["has_more"] is False


# ============================================================= #
# 26. Unicode query support                                     #
# ============================================================= #

def test_unicode_query_support():
    """Unicode text in query is handled safely without crashes."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9z1")
    unique_text = "ಕನ್ನಡ-forensic"
    _insert_canonical_record_sync(case_id, evidence_id, content=f"Evidence in Kannada: {unique_text}")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"q": unique_text},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should find the record
    assert any(
        unique_text in (r.get("content_preview") or "")
        for r in data["results"]
    )


def test_unicode_emoji_query_safe():
    """Emoji in query is handled safely."""
    client = TestClient(app)
    _, headers, case_id, _ = _setup_case_with_evidence(client, "s9z2")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"q": "emoji 🔍 test"},
        headers=headers,
    )
    assert resp.status_code == 200


# ============================================================= #
# 27. SQL injection safety                                      #
# ============================================================= #

def test_sql_injection_in_query_is_safe():
    """SQL injection attempt in q parameter does not cause error or data leak."""
    client = TestClient(app)
    _, headers, case_id, _ = _setup_case_with_evidence(client, "s9z3")

    payloads = [
        "'; DROP TABLE canonical_evidence; --",
        "' OR '1'='1",
        "' UNION SELECT * FROM users --",
        "\\x00\\x1f",
    ]
    for payload in payloads:
        resp = client.get(
            f"/api/v1/cases/{case_id}/search",
            params={"q": payload},
            headers=headers,
        )
        # Should return 200 (empty) or 400 (wildcard protection) — never 500
        assert resp.status_code in (200, 400), f"Unexpected {resp.status_code} for payload: {payload!r}"


def test_sql_injection_in_application_param():
    """SQL injection in application parameter is safely parameterized."""
    client = TestClient(app)
    _, headers, case_id, _ = _setup_case_with_evidence(client, "s9z4")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"application": "'; SELECT * FROM users; --"},
        headers=headers,
    )
    assert resp.status_code in (200, 400)


# ============================================================= #
# 28. History endpoint requires authentication                  #
# ============================================================= #

def test_search_history_requires_authentication():
    """GET /search/history without token returns 401."""
    client = TestClient(app)
    _, _, case_id, _ = _setup_case_with_evidence(client, "s9z5")

    resp = client.get(f"/api/v1/cases/{case_id}/search/history")
    assert resp.status_code == 401


# ============================================================= #
# 29. Invalid sort field rejected                               #
# ============================================================= #

def test_invalid_sort_field_rejected():
    """Unsupported sort value returns HTTP 400."""
    client = TestClient(app)
    _, headers, case_id, _ = _setup_case_with_evidence(client, "s9z6")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={"sort": "malicious_sort_field; DROP TABLE"},
        headers=headers,
    )
    assert resp.status_code == 400


# ============================================================= #
# 30. Traceability: every result has source fields              #
# ============================================================= #

def test_every_result_has_full_traceability_fields():
    """Every search result exposes canonical_id, raw_artifact_id, evidence_id, source_file, record_identifier."""
    client = TestClient(app)
    _, headers, case_id, evidence_id = _setup_case_with_evidence(client, "s9z7")
    _insert_canonical_record_sync(case_id, evidence_id, content="traceability-test")

    resp = client.get(
        f"/api/v1/cases/{case_id}/search",
        params={},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]
    for r in data["results"]:
        assert "id" in r
        assert "artifact_type" in r
        source = r.get("source", {})
        assert "evidence_id" in source
        assert "raw_artifact_id" in source
        assert "source_file" in source
        assert "record_identifier" in source
        assert "source_path" in source
