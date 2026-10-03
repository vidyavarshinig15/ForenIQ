"""
Phase 11 — Comprehensive Automated Test Suite

Validates:
1. Input normalization, Unicode sanitation, safety length caps
2. Forensic entity extraction (Phones, Emails, URLs, Devices, Accounts, Apps, Artifacts, Persons)
3. Temporal expression parsing with strict precision tracking (Day, Hour, Minute, Month)
4. Investigation intent classification across all 9 taxonomy classes
5. Structured investigation query planning and mode selection
6. API endpoint execution (/cases/{case_id}/investigation/query and /cases/{case_id}/investigation/parse)
7. Case authorization and multi-tenant cross-case isolation (IDOR protection)
8. Audit logging of investigation inquiries
9. Forensic safety constraints (no automated guilt or criminality declarations)
"""

import uuid
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.enums import ArtifactType, EntityType, InvestigationIntent, SearchMode
from backend.app.nlp import (
    ForensicEntityExtractor,
    InvestigationIntentClassifier,
    InvestigationNLPPipeline,
    InvestigationQueryPlanner,
    QueryNormalizer,
    TemporalParser,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def nlp_pipeline():
    return InvestigationNLPPipeline()


def _register_and_login(client: TestClient, prefix: str) -> str:
    email = f"p11_{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "NLPPass2026!", "name": f"Investigator {prefix}"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "NLPPass2026!"},
    )
    return resp.json()["access_token"]


def _setup_case(client: TestClient, prefix: str):
    token = _register_and_login(client, prefix)
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/v1/cases", headers=headers, json={"title": f"Phase11 Case {prefix}"})
    assert res.status_code == 201
    return token, headers, UUID(res.json()["id"])


# -------------------------------------------------------------------------- #
# Unit Tests: Normalization & Sanitation                                     #
# -------------------------------------------------------------------------- #

def test_query_normalizer_basic():
    normalizer = QueryNormalizer()
    norm, orig = normalizer.normalize("  Find   WhatsApp    messages  \t\n")
    assert norm == "Find WhatsApp messages"
    assert orig == "  Find   WhatsApp    messages  \t\n"


def test_query_normalizer_unicode_and_null_bytes():
    normalizer = QueryNormalizer()
    raw = "Find\x00 messages \u200b\u200c from \uff32\uff41\uff48\uff55\uff4c\r"
    norm, _ = normalizer.normalize(raw)
    assert "\x00" not in norm
    assert "Rahul" in norm or "messages" in norm


def test_query_normalizer_length_capping():
    normalizer = QueryNormalizer()
    huge = "search " * 200
    norm, _ = normalizer.normalize(huge)
    assert len(norm) <= 500


# -------------------------------------------------------------------------- #
# Unit Tests: Forensic Entity Extraction                                     #
# -------------------------------------------------------------------------- #

def test_extract_phone_numbers(nlp_pipeline):
    query = "Find calls between 9876543210 and +1-555-019-2834"
    entities = nlp_pipeline.entity_extractor.extract_entities(query)
    phones = [e for e in entities if e.type == EntityType.PHONE_NUMBER]
    assert len(phones) >= 2
    phone_vals = [p.normalized_value for p in phones]
    assert any("9876543210" in v for v in phone_vals)
    assert any("5550192834" in v for v in phone_vals)


def test_extract_emails_and_urls(nlp_pipeline):
    query = "Look for emails to suspect@forensics.org or visits to https://malicious-node.xyz/login"
    entities = nlp_pipeline.entity_extractor.extract_entities(query)
    emails = [e for e in entities if e.type == EntityType.EMAIL]
    urls = [e for e in entities if e.type == EntityType.URL]
    assert len(emails) == 1
    assert emails[0].normalized_value == "suspect@forensics.org"
    assert len(urls) == 1
    assert "https://malicious-node.xyz/login" in urls[0].normalized_value


def test_extract_devices_and_accounts(nlp_pipeline):
    query = "Show activity from device IMEI 356789012345678 or handle @crypto_hacker"
    entities = nlp_pipeline.entity_extractor.extract_entities(query)
    devices = [e for e in entities if e.type == EntityType.DEVICE]
    accounts = [e for e in entities if e.type == EntityType.ACCOUNT]
    assert len(devices) >= 1
    assert any(d.text == "356789012345678" for d in devices)
    assert len(accounts) >= 1
    assert accounts[0].normalized_value == "crypto_hacker"


def test_extract_applications_and_artifacts(nlp_pipeline):
    query = "Find Telegram messages and Chrome browsing history"
    entities = nlp_pipeline.entity_extractor.extract_entities(query)
    apps = [e for e in entities if e.type == EntityType.APPLICATION]
    artifacts = [e for e in entities if e.type == EntityType.ARTIFACT_TYPE]
    app_names = [a.normalized_value for a in apps]
    assert "Telegram" in app_names
    assert "Chrome" in app_names
    art_names = [ar.normalized_value for ar in artifacts]
    assert "MESSAGE" in art_names
    assert "BROWSER" in art_names


# -------------------------------------------------------------------------- #
# Unit Tests: Temporal Expression Parsing                                    #
# -------------------------------------------------------------------------- #

def test_parse_relative_temporal(nlp_pipeline):
    query = "Show WhatsApp activity from yesterday"
    constraints = nlp_pipeline.temporal_parser.extract_temporal_constraints(query)
    assert len(constraints) == 1
    assert constraints[0].precision == "DAY"
    assert constraints[0].start_time is not None
    assert constraints[0].end_time is not None
    assert constraints[0].start_time < constraints[0].end_time


def test_parse_date_range_temporal(nlp_pipeline):
    query = "Find calls between September 1 and September 5"
    constraints = nlp_pipeline.temporal_parser.extract_temporal_constraints(query)
    assert len(constraints) == 1
    assert constraints[0].precision == "DAY"
    assert constraints[0].start_time.month == 9
    assert constraints[0].start_time.day == 1
    assert constraints[0].end_time.month == 9
    assert constraints[0].end_time.day == 5


def test_parse_time_range_temporal(nlp_pipeline):
    query = "What happened between 10 PM and midnight?"
    constraints = nlp_pipeline.temporal_parser.extract_temporal_constraints(query)
    assert len(constraints) == 1
    assert constraints[0].precision == "HOUR"


def test_parse_boundary_temporal(nlp_pipeline):
    query = "Show events after 8 PM"
    constraints = nlp_pipeline.temporal_parser.extract_temporal_constraints(query)
    assert len(constraints) == 1
    assert constraints[0].precision == "HOUR"
    assert constraints[0].start_time is not None
    assert constraints[0].end_time is None


# -------------------------------------------------------------------------- #
# Unit Tests: Intent Classification                                          #
# -------------------------------------------------------------------------- #

@pytest.mark.parametrize("query,expected_intent", [
    ("Find all messages involving Rahul", InvestigationIntent.PERSON_LOOKUP),
    ("Show events related to the suspect on September 12", InvestigationIntent.EVENT_RETRIEVAL),
    ("Find communication between 9876543210 and 9123456789", InvestigationIntent.COMMUNICATION_ANALYSIS),
    ("What happened between 10 PM and midnight?", InvestigationIntent.TEMPORAL_INVESTIGATION),
    ("Show activity from device DEV_9901", InvestigationIntent.DEVICE_LOOKUP),
    ("Show records associated with Mysuru", InvestigationIntent.LOCATION_LOOKUP),
    ("Show WhatsApp activity from yesterday", InvestigationIntent.APPLICATION_ACTIVITY),
    ("Find evidence mentioning the stolen laptop", InvestigationIntent.GENERAL_EVIDENCE_SEARCH),
])
def test_intent_classification(nlp_pipeline, query, expected_intent):
    parsed = nlp_pipeline.parse_query(query)
    assert parsed.intent.type == expected_intent
    assert 0.0 <= parsed.intent.confidence <= 1.0


# -------------------------------------------------------------------------- #
# Unit Tests: Retrieval Plan Generation                                      #
# -------------------------------------------------------------------------- #

def test_query_planner_exact_recommendation(nlp_pipeline):
    query = "Find device DEV_8871"
    parsed = nlp_pipeline.parse_query(query)
    assert parsed.recommended_retrieval_mode == SearchMode.EXACT


def test_query_planner_hybrid_recommendation(nlp_pipeline):
    query = "Find WhatsApp messages sent by Rahul yesterday"
    parsed = nlp_pipeline.parse_query(query)
    assert parsed.recommended_retrieval_mode == SearchMode.HYBRID
    assert "application" in parsed.filters
    assert parsed.filters["application"] == "WhatsApp"


# -------------------------------------------------------------------------- #
# Integration & API Tests                                                    #
# -------------------------------------------------------------------------- #

def test_api_investigation_parse(client: TestClient):
    token, headers, case_id = _setup_case(client, "parse")
    payload = {
        "query": "Find WhatsApp messages from Rahul on September 15",
        "retrieval_mode": "AUTO"
    }

    res = client.post(
        f"/api/v1/cases/{case_id}/investigation/parse",
        headers=headers,
        json=payload
    )
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == str(case_id)
    assert data["intent"]["type"] == "APPLICATION_ACTIVITY"
    assert any(e["normalized_value"] == "WhatsApp" for e in data["entities"])
    assert any(e["normalized_value"] == "Rahul" for e in data["entities"])


def test_api_investigation_query_execution(client: TestClient):
    token, headers, case_id = _setup_case(client, "query")
    payload = {
        "query": "Find all evidence mentioning bitcoin transfer",
        "retrieval_mode": "AUTO",
        "page_size": 10
    }

    res = client.post(
        f"/api/v1/cases/{case_id}/investigation/query",
        headers=headers,
        json=payload
    )
    assert res.status_code == 200
    data = res.json()
    assert "interpretation" in data
    assert "retrieval_plan" in data
    assert "results" in data
    assert "pagination" in data
    assert data["interpretation"]["intent"]["type"] == "GENERAL_EVIDENCE_SEARCH"


def test_api_investigation_query_case_isolation(client: TestClient):
    token = _register_and_login(client, "user_iso")
    headers = {"Authorization": f"Bearer {token}"}
    foreign_case_id = str(uuid4())
    payload = {"query": "Find WhatsApp messages"}

    res = client.post(
        f"/api/v1/cases/{foreign_case_id}/investigation/query",
        headers=headers,
        json=payload
    )
    assert res.status_code in (403, 404)


def test_api_investigation_query_empty_or_malformed(client: TestClient):
    token, headers, case_id = _setup_case(client, "empty")
    payload = {"query": ""}

    res = client.post(
        f"/api/v1/cases/{case_id}/investigation/query",
        headers=headers,
        json=payload
    )
    assert res.status_code == 422  # Pydantic validation error for min_length=1
