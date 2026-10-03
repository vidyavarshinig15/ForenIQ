import asyncio
import hashlib
import io
import os
import time
import zipfile
import pytest
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from backend.app.core.config import get_settings
from backend.app.core.database import async_session_factory
from backend.app.main import app
from backend.app.models.enums import ArtifactType, JobPriority, JobStatus, ProcessingStage
from backend.app.models.evidence import Evidence
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.raw_artifact import RawArtifact
from backend.app.queue.database_queue import DatabaseJobQueue
from backend.app.queue.redis_queue import RedisJobQueue
from backend.app.services.parser_worker import UFDRParserWorker
from backend.app.services.storage.local import LocalStorageService

settings = get_settings()


def get_auth_token(client: TestClient, email: str, password: str, name: str, role: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": name, "password": password, "role": role},
    )
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]


def make_synthetic_ufdr_bytes(num_calls: int = 5, num_messages: int = 5) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest_xml = """<?xml version="1.0" encoding="UTF-8"?>
<report>
    <case_info><investigator>Special Agent Fox</investigator></case_info>
</report>"""
        zf.writestr("report.xml", manifest_xml)

        calls_xml = '<?xml version="1.0" encoding="UTF-8"?><calls>\n'
        for i in range(num_calls):
            calls_xml += f"""  <call>
    <id>call_{i}</id>
    <number>+1555010{i:02d}</number>
    <timestamp>2026-03-01T10:00:{i:02d}Z</timestamp>
    <duration>{60 * (i + 1)}</duration>
    <type>INCOMING</type>
  </call>\n"""
        calls_xml += "</calls>"
        zf.writestr("calls.xml", calls_xml)

        msgs_xml = '<?xml version="1.0" encoding="UTF-8"?><messages>\n'
        for i in range(num_messages):
            msgs_xml += f"""  <message>
    <id>msg_{i}</id>
    <sender>+1555010{i:02d}</sender>
    <timestamp>2026-03-01T12:00:{i:02d}Z</timestamp>
    <body>Investigative message #{i}</body>
  </message>\n"""
        msgs_xml += "</messages>"
        zf.writestr("messages.xml", msgs_xml)

    return buf.getvalue()


def setup_case_and_evidence(client: TestClient, prefix: str, num_calls: int = 5, num_messages: int = 5):
    """Sets up an authenticated case, evidence record, and user ID."""
    token = get_auth_token(client, f"{prefix}@ufdr.org", "Pass12345!", f"User {prefix}", "INVESTIGATOR")
    headers = {"Authorization": f"Bearer {token}"}
    
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    user_id = UUID(me_res.json()["id"])

    case_res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={"title": f"Phase 6 Case {prefix}"},
    )
    assert case_res.status_code == 201
    case_id = UUID(case_res.json()["id"])

    ufdr_bytes = make_synthetic_ufdr_bytes(num_calls=num_calls, num_messages=num_messages)
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=headers,
        files={"file": (f"{prefix}.ufdr", ufdr_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    evidence_id = UUID(upload_res.json()["id"])
    return token, headers, case_id, evidence_id, user_id


@pytest.mark.asyncio
async def test_database_queue_priority_ordering():
    """Verify that DatabaseJobQueue dequeues HIGH priority jobs before NORMAL and LOW."""
    with TestClient(app) as client:
        _, _, case_id, evidence_id, user_id = setup_case_and_evidence(client, "db_priority", 2, 2)
    db_queue = DatabaseJobQueue(default_lease_seconds=30)

    async with async_session_factory() as session:
        low_job = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.LOW,
            job_type="UFDR_PARSE",
        )
        normal_job = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.NORMAL,
            job_type="UFDR_PARSE",
        )
        high_job = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.HIGH,
            job_type="UFDR_PARSE",
        )
        session.add_all([low_job, normal_job, high_job])
        await session.commit()
        low_id, norm_id, high_id = low_job.id, normal_job.id, high_job.id

    # Enqueue in arbitrary order: LOW, NORMAL, HIGH
    await db_queue.enqueue(low_id, priority=JobPriority.LOW)
    await db_queue.enqueue(norm_id, priority=JobPriority.NORMAL)
    await db_queue.enqueue(high_id, priority=JobPriority.HIGH)

    # Dequeue 1: must be HIGH
    job1 = await db_queue.dequeue(worker_id="test-worker-1")
    assert job1 is not None
    assert job1 == high_id

    # Dequeue 2: must be NORMAL
    job2 = await db_queue.dequeue(worker_id="test-worker-1")
    assert job2 is not None
    assert job2 == norm_id

    # Dequeue 3: must be LOW
    job3 = await db_queue.dequeue(worker_id="test-worker-1")
    assert job3 is not None
    assert job3 == low_id


@pytest.mark.asyncio
async def test_redis_queue_priority_ordering():
    """Verify that RedisJobQueue dequeues HIGH priority jobs before NORMAL and LOW."""
    redis_queue = RedisJobQueue(redis_url=settings.REDIS_URL)
    try:
        await redis_queue.client.ping()
    except Exception:
        pytest.skip("Local Redis server not reachable for Redis test")

    # Clear pending queue
    await redis_queue.client.delete(redis_queue.queue_key)

    with TestClient(app) as client:
        _, _, case_id, evidence_id, user_id = setup_case_and_evidence(client, "redis_priority", 2, 2)

    async with async_session_factory() as session:
        low_job = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.LOW,
            job_type="UFDR_PARSE",
        )
        normal_job = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.NORMAL,
            job_type="UFDR_PARSE",
        )
        high_job = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.HIGH,
            job_type="UFDR_PARSE",
        )
        session.add_all([low_job, normal_job, high_job])
        await session.commit()
        low_id, norm_id, high_id = low_job.id, normal_job.id, high_job.id

    await redis_queue.enqueue(low_id, priority=JobPriority.LOW)
    await redis_queue.enqueue(norm_id, priority=JobPriority.NORMAL)
    await redis_queue.enqueue(high_id, priority=JobPriority.HIGH)

    # Dequeue 1: HIGH
    j1 = await redis_queue.dequeue(worker_id="w-redis-1")
    assert j1 == high_id

    # Dequeue 2: NORMAL
    j2 = await redis_queue.dequeue(worker_id="w-redis-1")
    assert j2 == norm_id

    # Dequeue 3: LOW
    j3 = await redis_queue.dequeue(worker_id="w-redis-1")
    assert j3 == low_id

    await redis_queue.close()


@pytest.mark.asyncio
async def test_job_heartbeat_and_lease():
    """Verify that worker heartbeat updates last_heartbeat_at and lease_expires_at."""
    with TestClient(app) as client:
        _, _, case_id, evidence_id, user_id = setup_case_and_evidence(client, "heartbeat_test", 2, 2)
    db_queue = DatabaseJobQueue(default_lease_seconds=30)

    async with async_session_factory() as session:
        job = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.NORMAL,
            job_type="UFDR_PARSE",
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    await db_queue.enqueue(job_id, priority=JobPriority.NORMAL)
    dequeued = await db_queue.dequeue(worker_id="worker-hb-1")
    assert dequeued == job_id

    # Heartbeat
    success = await db_queue.heartbeat(job_id, worker_id="worker-hb-1")
    assert success is True

    async with async_session_factory() as session:
        j = await session.get(ProcessingJob, job_id)
        assert j.last_heartbeat_at is not None
        assert j.lease_expires_at is not None
        lease_at = j.lease_expires_at.replace(tzinfo=timezone.utc) if j.lease_expires_at.tzinfo is None else j.lease_expires_at
        assert lease_at > datetime.now(timezone.utc) + timedelta(seconds=10)


@pytest.mark.asyncio
async def test_stale_job_detection_and_reaper():
    """Verify that stale jobs whose leases expire are detected and recovered."""
    with TestClient(app) as client:
        _, _, case_id, evidence_id, user_id = setup_case_and_evidence(client, "stale_test", 2, 2)
    db_queue = DatabaseJobQueue(default_lease_seconds=30)

    async with async_session_factory() as session:
        stale_job = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.RUNNING,
            priority=JobPriority.NORMAL,
            job_type="UFDR_PARSE",
            worker_id="dead-worker",
            lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=60),
            retry_count=0,
            max_retries=3,
        )
        session.add(stale_job)
        await session.commit()
        stale_id = stale_job.id

    # Run reaper
    reaped_jobs = await db_queue.reap_stale_jobs()
    assert len(reaped_jobs) >= 1

    async with async_session_factory() as session:
        j = await session.get(ProcessingJob, stale_id)
        assert j.status in (JobStatus.RETRYING, JobStatus.QUEUED)
        assert j.retry_count == 1
        assert j.worker_id is None


@pytest.mark.asyncio
async def test_idempotent_duplicate_prevention_on_reparse():
    """Test 12 & 13: Reparsing the same UFDR package does not create duplicate artifacts."""
    with TestClient(app) as client:
        _, _, case_id, evidence_id, user_id = setup_case_and_evidence(client, "idemp_test", 5, 5)

    async with async_session_factory() as session:
        job1 = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.NORMAL,
            job_type="UFDR_PARSE",
        )
        session.add(job1)
        await session.commit()
        job1_id = job1.id

    # Run first parse
    worker = UFDRParserWorker()
    await worker.execute_job(job1_id, worker_id="test-idemp-worker")

    async with async_session_factory() as session:
        j1 = await session.get(ProcessingJob, job1_id)
        assert j1.status == JobStatus.COMPLETED
        stmt = select(func.count(RawArtifact.id)).where(RawArtifact.evidence_id == evidence_id)
        count_after_first = (await session.execute(stmt)).scalar_one()
        assert count_after_first == 10  # 5 calls + 5 messages

    # Create second job for same evidence
    async with async_session_factory() as session:
        job2 = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.NORMAL,
            job_type="UFDR_PARSE",
        )
        session.add(job2)
        await session.commit()
        job2_id = job2.id

    # Run second parse
    await worker.execute_job(job2_id, worker_id="test-idemp-worker")

    async with async_session_factory() as session:
        j2 = await session.get(ProcessingJob, job2_id)
        assert j2.status == JobStatus.COMPLETED

        # Verify count did NOT double to 20! It MUST remain strictly 10.
        stmt = select(func.count(RawArtifact.id)).where(RawArtifact.evidence_id == evidence_id)
        count_after_second = (await session.execute(stmt)).scalar_one()
        assert count_after_second == 10, f"Expected 10 artifacts, found {count_after_second} (duplicate artifacts created!)"


@pytest.mark.asyncio
async def test_checkpoint_and_resumable_ingestion():
    """Test 14 & 15: Checkpoint is written after each file and completed files are skipped on resume."""
    with TestClient(app) as client:
        _, _, case_id, evidence_id, user_id = setup_case_and_evidence(client, "resumable_test", 10, 10)

    async with async_session_factory() as session:
        job = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.NORMAL,
            job_type="UFDR_PARSE",
            checkpoint_data={
                "completed_files": ["calls.xml"],
                "records_processed": 10,
            },
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    worker = UFDRParserWorker()
    await worker.execute_job(job_id, worker_id="resume-worker")

    async with async_session_factory() as session:
        j = await session.get(ProcessingJob, job_id)
        assert j.status == JobStatus.COMPLETED
        assert "calls.xml" in j.checkpoint_data["completed_files"]
        assert "messages.xml" in j.checkpoint_data["completed_files"]
        assert j.files_processed == 2


@pytest.mark.asyncio
async def test_cooperative_job_cancellation():
    """Test 22: Requesting cancellation transitions job to CANCEL_REQUESTED and worker halts cleanly."""
    with TestClient(app) as client:
        _, headers, case_id, evidence_id, user_id = setup_case_and_evidence(client, "cancel_agent", 10, 10)

        # Create job directly in RUNNING state to avoid race condition with synchronous background tasks
        async with async_session_factory() as session:
            job = ProcessingJob(
                id=uuid4(),
                case_id=case_id,
                evidence_id=evidence_id,
                created_by=user_id,
                status=JobStatus.RUNNING,
                priority=JobPriority.NORMAL,
                job_type="UFDR_PARSE",
            )
            session.add(job)
            await session.commit()
            job_id = job.id

        # Request cancellation
        cancel_res = client.post(f"/api/v1/cases/{case_id}/processing-jobs/{job_id}/cancel", headers=headers)
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "CANCEL_REQUESTED"

        # Worker resumes/runs and detects cancellation request -> transitions to CANCELLED
        worker = UFDRParserWorker()
        await worker.execute_job(job_id, worker_id="cancel-test-worker")

        async with async_session_factory() as session:
            cancelled_job = await session.get(ProcessingJob, job_id)
            assert cancelled_job.status == JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_non_admin_priority_enforcement():
    """Test 5: Non-admin users cannot abuse HIGH priority (must be capped at NORMAL)."""
    with TestClient(app) as client:
        _, headers, case_id, evidence_id, _ = setup_case_and_evidence(client, "prio_agent", 2, 2)

        # Investigator tries to request HIGH priority
        parse_res = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/parse",
            json={"priority": "HIGH"},
            headers=headers,
        )
        assert parse_res.status_code == 202
        # Capped at NORMAL for non-admin
        assert parse_res.json()["priority"] == "NORMAL"


@pytest.mark.asyncio
async def test_processing_job_idor_isolation():
    """Test 57: User authorized only for Case A cannot view, cancel, or retry Case B's job."""
    with TestClient(app) as client:
        _, headers_a, case_a, ev_a, _ = setup_case_and_evidence(client, "case_a_agent", 2, 2)
        _, headers_b, case_b, ev_b, _ = setup_case_and_evidence(client, "case_b_agent", 2, 2)

        job_a = client.post(f"/api/v1/cases/{case_a}/evidence/{ev_a}/parse", headers=headers_a).json()["id"]

        # Agent B tries to access Job A via Case A -> 403 Forbidden
        idor_get = client.get(f"/api/v1/cases/{case_a}/processing-jobs/{job_a}", headers=headers_b)
        assert idor_get.status_code in [403, 404]

        # Agent B tries to cancel Job A via Case B (path tampering) -> 404 Not Found
        idor_cancel = client.post(f"/api/v1/cases/{case_b}/processing-jobs/{job_a}/cancel", headers=headers_b)
        assert idor_cancel.status_code in [403, 404]

        # Agent B tries to retry Job A via Case B -> 404 Not Found
        idor_retry = client.post(f"/api/v1/cases/{case_b}/processing-jobs/{job_a}/retry", headers=headers_b)
        assert idor_retry.status_code in [403, 404]


@pytest.mark.asyncio
async def test_original_evidence_sha256_preservation():
    """Test 59: The large-scale processing pipeline must never modify the original uploaded evidence."""
    with TestClient(app) as client:
        _, _, case_id, evidence_id, user_id = setup_case_and_evidence(client, "hash_preservation", 8, 8)

    async with async_session_factory() as session:
        ev = await session.get(Evidence, evidence_id)
        original_sha256 = ev.sha256_hash
        stored_path = ev.storage_path_or_key

        job = ProcessingJob(
            id=uuid4(),
            case_id=case_id,
            evidence_id=evidence_id,
            created_by=user_id,
            status=JobStatus.QUEUED,
            priority=JobPriority.NORMAL,
            job_type="UFDR_PARSE",
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    worker = UFDRParserWorker()
    await worker.execute_job(job_id, worker_id="hash-preservation-worker")

    # Re-calculate hash of the file on disk
    storage = LocalStorageService()
    abs_path = storage._resolve_safe_path(stored_path)
    with open(abs_path, "rb") as f:
        after_sha256 = hashlib.sha256(f.read()).hexdigest()

    assert after_sha256 == original_sha256, "Original evidence file was altered during processing!"
