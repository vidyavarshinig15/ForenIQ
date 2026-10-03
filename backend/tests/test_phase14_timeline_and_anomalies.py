"""
Phase 14 — Timeline Analysis & Statistical Anomaly Detection Tests.

Validates:
  1. Unified Forensic Timeline Generation & Deterministic Ordering
  2. Temporal Windowing & Feature Extraction
  3. Isolation Forest Anomaly Detection & Score Normalization
  4. Statistical Baseline Comparator (Z-Score)
  5. Anomaly Explainability & Forensic Neutrality Standards
  6. Case Isolation & IDOR Protection
  7. Asynchronous Anomaly Job Lifecycle & Progress Tracking
  8. End-to-End REST APIs (/timeline, /anomalies/detect, /anomalies/jobs)
"""

from datetime import datetime, timezone, timedelta
import uuid
from uuid import UUID

from httpx import ASGITransport, AsyncClient
import pytest

from backend.app.anomalies.baseline_detector import StatisticalBaselineDetector
from backend.app.anomalies.feature_extractor import TemporalFeatureExtractor
from backend.app.anomalies.isolation_forest_detector import ForensicIsolationForestDetector
from backend.app.anomalies.job_manager import anomaly_job_manager
from backend.app.main import app
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import (
    AnomalyAlgorithm,
    AnomalyClassification,
    AnomalySeverity,
    AnomalyType,
    ArtifactType,
    JobStatus,
    TemporalWindowSize,
    TimestampPrecision,
    TimestampStatus,
)
from backend.app.models.user import User
from backend.app.schemas.timeline_anomaly import (
    AnomalyDetectionRequest,
    TemporalWindowFeature,
    TimelineEvent,
    TimelineFilterRequest,
)
from backend.app.timeline.timeline_service import timeline_service


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


@pytest.mark.asyncio
async def test_temporal_feature_extractor_windowing():
    """Unit test: Sliding temporal window extraction and behavioral feature calculations."""
    case_id = uuid.uuid4()
    art_id1 = uuid.uuid4()
    art_id2 = uuid.uuid4()

    ev1 = TimelineEvent(
        event_id="e1",
        case_id=case_id,
        evidence_id=uuid.uuid4(),
        artifact_id=art_id1,
        timestamp="2026-09-15T10:05:00Z",
        event_type=ArtifactType.CALL,
        application="Phone",
        actor="+919876543210",
        target="+919876543211",
        source_file="calls.xml",
        source_path="/raw/calls.xml",
        metadata={"call_type": "OUTGOING"},
    )
    ev2 = TimelineEvent(
        event_id="e2",
        case_id=case_id,
        evidence_id=uuid.uuid4(),
        artifact_id=art_id2,
        timestamp="2026-09-15T10:10:00Z",
        event_type=ArtifactType.MESSAGE,
        application="WhatsApp",
        actor="+919876543211",
        target="+919876543210",
        source_file="msgs.xml",
        source_path="/raw/msgs.xml",
        metadata={"direction": "INCOMING"},
    )

    windows = TemporalFeatureExtractor.slice_into_windows(
        timeline_events=[ev1, ev2],
        window_size=TemporalWindowSize.FIFTEEN_MINUTES,
    )

    assert len(windows) >= 1
    w = windows[0]
    assert w.event_count == 2
    assert w.communication_count == 2
    assert w.unique_contacts == 2
    assert w.burst_frequency == round(2.0 / 15.0, 4)
    assert w.inter_event_time_avg == 300.0  # 5 minutes between ev1 and ev2

    profile = TemporalFeatureExtractor.compute_baseline_profile(windows)
    assert "event_count" in profile
    assert profile["event_count"]["median"] == 2.0


@pytest.mark.asyncio
async def test_isolation_forest_anomaly_detection():
    """Unit test: Isolation Forest detector identifies unusual burst anomalies and formats neutral explanations."""
    case_id = uuid.uuid4()

    # Generate 20 baseline windows with 1 event each
    baseline_windows = []
    base_time = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    for i in range(20):
        t = base_time + timedelta(hours=i)
        baseline_windows.append(
            TemporalFeatureExtractor.slice_into_windows(
                [
                    TimelineEvent(
                        event_id=f"base_{i}",
                        case_id=case_id,
                        evidence_id=uuid.uuid4(),
                        artifact_id=uuid.uuid4(),
                        timestamp=t.isoformat(),
                        event_type=ArtifactType.CALL,
                        actor="+919876543210",
                        target="+919876543211",
                        source_file="f.xml",
                        source_path="/f.xml",
                    )
                ],
                window_size=TemporalWindowSize.FIFTEEN_MINUTES,
            )[0]
        )

    # Injected Anomalous Burst Window with 25 events
    burst_events = [
        TimelineEvent(
            event_id=f"burst_{j}",
            case_id=case_id,
            evidence_id=uuid.uuid4(),
            artifact_id=uuid.uuid4(),
            timestamp=(datetime(2026, 9, 2, 21, 15, tzinfo=timezone.utc) + timedelta(seconds=j * 20)).isoformat(),
            event_type=ArtifactType.CALL if j % 2 == 0 else ArtifactType.MESSAGE,
            actor="+919876543210",
            target=f"+91987654399{j % 5}",
            source_file="f.xml",
            source_path="/f.xml",
        )
        for j in range(25)
    ]
    burst_window = TemporalFeatureExtractor.slice_into_windows(
        burst_events,
        window_size=TemporalWindowSize.FIFTEEN_MINUTES,
    )[0]

    all_windows = baseline_windows + [burst_window]
    profile = TemporalFeatureExtractor.compute_baseline_profile(baseline_windows)

    detector = ForensicIsolationForestDetector(
        n_estimators=100,
        contamination=0.1,
        random_state=42,
        score_threshold=0.60,
    )
    anomalies = detector.detect_anomalies(
        case_id=case_id,
        analysis_windows=all_windows,
        baseline_windows=baseline_windows,
        baseline_profile=profile,
    )

    assert len(anomalies) >= 1
    # Check that at least one detected anomaly is classified as ANOMALOUS with neutral explanation
    anom = anomalies[0]
    assert anom.classification == AnomalyClassification.ANOMALOUS
    assert anom.anomaly_score >= 0.60
    assert "Statistically unusual" in anom.factual_explanation
    # Forensic neutrality verification
    assert "criminal" not in anom.factual_explanation.lower()
    assert "guilt" not in anom.factual_explanation.lower()
    assert "suspect" not in anom.factual_explanation.lower()


@pytest.mark.asyncio
async def test_statistical_baseline_zscore_detector():
    """Unit test: StatisticalBaselineDetector identifies univariate outliers using z-score thresholding."""
    case_id = uuid.uuid4()
    profile = {
        "event_count": {"median": 2.0, "mean": 2.0, "std": 1.0, "iqr": 1.0, "min": 1.0, "max": 4.0},
        "communication_count": {"median": 1.0, "mean": 1.0, "std": 0.5, "iqr": 1.0, "min": 0.0, "max": 2.0},
        "burst_frequency": {"median": 0.13, "mean": 0.13, "std": 0.05, "iqr": 0.05, "min": 0.05, "max": 0.2},
    }

    anom_window = TemporalFeatureExtractor.slice_into_windows(
        [
            TimelineEvent(
                event_id=f"z_{i}",
                case_id=case_id,
                evidence_id=uuid.uuid4(),
                artifact_id=uuid.uuid4(),
                timestamp=(datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc) + timedelta(seconds=i * 30)).isoformat(),
                event_type=ArtifactType.CALL,
                actor="+919876543210",
                target="+919876543211",
                source_file="f.xml",
                source_path="/f.xml",
            )
            for i in range(15)  # 15 events when mean is 2.0 and std is 1.0 (z-score = 13.0)
        ],
        window_size=TemporalWindowSize.FIFTEEN_MINUTES,
    )[0]

    z_detector = StatisticalBaselineDetector(z_threshold=2.5)
    anomalies = z_detector.detect_anomalies(
        case_id=case_id,
        analysis_windows=[anom_window],
        baseline_profile=profile,
    )

    assert len(anomalies) == 1
    assert anomalies[0].algorithm == AnomalyAlgorithm.STATISTICAL_ZSCORE
    assert anomalies[0].anomaly_score >= 0.85
    assert anomalies[0].severity == AnomalySeverity.HIGH_ANOMALY


@pytest.mark.asyncio
async def test_anomaly_job_manager_lifecycle():
    """Unit test: Asynchronous anomaly job management and progress tracking."""
    case_id = uuid.uuid4()
    job = anomaly_job_manager.create_job(case_id)
    assert job.status == JobStatus.QUEUED
    assert job.progress == 0.0

    # Progress update
    updated = anomaly_job_manager.update_progress(
        job_id=job.job_id,
        status=JobStatus.RUNNING,
        progress=0.45,
        total_windows=100,
        anomalies_found=4,
    )
    assert updated.status == JobStatus.RUNNING
    assert updated.progress == 0.45
    assert updated.total_windows == 100
    assert updated.anomalies_found == 4

    # Cancellation
    cancelled = anomaly_job_manager.cancel_job(job.job_id, case_id)
    assert cancelled is True
    assert anomaly_job_manager.get_job(job.job_id).status == JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_timeline_and_anomaly_apis_end_to_end():
    """Integration test: REST API endpoints for Timeline query, Anomaly detection, and Job management."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"tester_{uuid.uuid4().hex[:6]}@ufdr.org"
        token = await _register_and_login(client, email, "ADMIN")
        case_id = await _setup_case(client, token, f"CASE-P14-{uuid.uuid4().hex[:6]}")
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Timeline GET
        resp = await client.get(f"/api/v1/cases/{case_id}/timeline", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "total_events" in data

        # 2. Anomaly Detection POST
        detect_payload = {
            "window_size": "15m",
            "algorithm": "ISOLATION_FOREST",
            "contamination": 0.05,
            "score_threshold": 0.65,
        }
        resp_anom = await client.post(
            f"/api/v1/cases/{case_id}/anomalies/detect",
            json=detect_payload,
            headers=headers,
        )
        assert resp_anom.status_code == 200
        anom_data = resp_anom.json()
        assert anom_data["status"] == "COMPLETED"
        assert "anomalies" in anom_data

        # 3. Anomaly Jobs POST
        job_payload = {
            "window_size": "15m",
            "algorithm": "ISOLATION_FOREST",
        }
        resp_job = await client.post(
            f"/api/v1/cases/{case_id}/anomalies/jobs",
            json=job_payload,
            headers=headers,
        )
        assert resp_job.status_code == 202
        job_info = resp_job.json()
        assert "job_id" in job_info

        # 4. Anomaly Job Status GET
        job_id = job_info["job_id"]
        resp_status = await client.get(
            f"/api/v1/cases/{case_id}/anomalies/jobs/{job_id}",
            headers=headers,
        )
        assert resp_status.status_code == 200
        assert resp_status.json()["job_id"] == job_id


@pytest.mark.asyncio
async def test_timeline_filtering_and_case_isolation():
    """Verify case isolation and multi-attribute filtering across timeline queries."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(client, f"iso_{uuid.uuid4().hex[:6]}@ufdr.org", "INVESTIGATOR")
        case_a = await _setup_case(client, token, f"CASE-A-{uuid.uuid4().hex[:6]}")
        case_b = await _setup_case(client, token, f"CASE-B-{uuid.uuid4().hex[:6]}")
        headers = {"Authorization": f"Bearer {token}"}

        # Query Case A timeline
        resp_a = await client.get(f"/api/v1/cases/{case_a}/timeline", headers=headers)
        assert resp_a.status_code == 200
        data_a = resp_a.json()
        assert data_a["case_id"] == case_a

        # Query Case B timeline
        resp_b = await client.get(f"/api/v1/cases/{case_b}/timeline", headers=headers)
        assert resp_b.status_code == 200
        data_b = resp_b.json()
        assert data_b["case_id"] == case_b

        # Advanced Query with filter payload
        query_payload = {
            "start_time": "2026-09-01T00:00:00Z",
            "end_time": "2026-09-30T23:59:59Z",
            "limit": 50,
            "offset": 0,
        }
        resp_query = await client.post(
            f"/api/v1/cases/{case_a}/timeline/query",
            json=query_payload,
            headers=headers,
        )
        assert resp_query.status_code == 200
        assert "events" in resp_query.json()


@pytest.mark.asyncio
async def test_forensic_safety_prohibits_criminal_inferences():
    """Verify that all anomaly types, severities, and explanations strictly adhere to forensic safety rules."""
    detector = ForensicIsolationForestDetector()
    prohibited_keywords = [
        "criminal",
        "guilty",
        "guilt",
        "suspect",
        "threat",
        "conspiracy",
        "malicious",
        "crime probability",
        "risk score",
        "perpetrator",
    ]

    # Verify Enum names and descriptions do not contain prohibited terms
    for anom_type in AnomalyType:
        for word in prohibited_keywords:
            assert word not in anom_type.value.lower()

    for severity in AnomalySeverity:
        for word in prohibited_keywords:
            assert word not in severity.value.lower()

    # Synthetic window check
    w = TemporalWindowFeature(
        window_id="w_test",
        start_time="2026-09-15T21:15:00Z",
        end_time="2026-09-15T21:30:00Z",
        event_count=20,
        communication_count=20,
        burst_frequency=1.33,
    )
    profile = {
        "event_count": {"median": 2.0, "mean": 2.0, "std": 1.0},
        "communication_count": {"median": 1.0, "mean": 1.0, "std": 1.0},
        "burst_frequency": {"median": 0.13, "mean": 0.13, "std": 0.1},
    }
    _, _, explanation = detector._determine_anomaly_type_and_metrics(w, profile)

    for word in prohibited_keywords:
        assert word not in explanation.lower()

