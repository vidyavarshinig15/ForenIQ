from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Set
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.database import async_session_factory
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import (
    AuditAction,
    CustodyEventType,
    DataQualityStatus,
    EvidenceStatus,
    IntegrityStatus,
    JobStatus,
    ProcessingStage,
)
from backend.app.models.evidence import Evidence
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.pipeline import NormalizationPipeline
from backend.app.repositories.canonical_evidence_repo import CanonicalEvidenceRepository
from backend.app.repositories.processing_job_repo import ProcessingJobRepository
from backend.app.services.audit_service import AuditService
from backend.app.services.custody_service import CustodyService

logger = logging.getLogger(__name__)


class EvidenceNormalizationWorker:
    """
    Asynchronous forensic worker responsible for executing batch normalization
    of RawArtifacts into CanonicalEvidence models with bounded memory,
    idempotent persistence, and cooperative cancellation.
    """

    def __init__(self, batch_size: Optional[int] = None) -> None:
        self.settings = get_settings()
        self.pipeline = NormalizationPipeline()
        self.batch_size_override = batch_size

    async def execute(self, job_id: uuid.UUID, worker_id: Optional[str] = None) -> bool:
        """Helper alias matching test runner interface."""
        await self.execute_job(job_id, worker_id)
        async with async_session_factory() as session:
            job = await session.get(ProcessingJob, job_id)
            return job is not None and job.status in (JobStatus.COMPLETED, JobStatus.PARTIAL)

    async def execute_job(self, job_id: uuid.UUID, worker_id: Optional[str] = None) -> None:
        """
        Executes a normalization job against the raw artifacts of an evidence container.
        Processes in bounded streaming chunks, updating progress and heartbeats.
        """
        worker_id = worker_id or f"norm-worker-{uuid.uuid4().hex[:6]}"
        logger.info(f"[NormWorker:{worker_id}] Starting normalization job {job_id}")

        async with async_session_factory() as session:
            job_repo = ProcessingJobRepository(session)
            canonical_repo = CanonicalEvidenceRepository(session)
            audit_service = AuditService(session)
            custody_service = CustodyService(session)

            job = await job_repo.get_by_id(job_id)
            if not job:
                logger.error(f"[NormWorker] ProcessingJob {job_id} not found in database.")
                return

            evidence = await session.get(Evidence, job.evidence_id)
            if not evidence:
                logger.error(f"[NormWorker] Evidence {job.evidence_id} not found.")
                await job_repo.update_status(job_id=job.id, status=JobStatus.FAILED, error_message="Evidence record missing.")
                return

            # Check pre-flight cancellation
            if job.status in (JobStatus.CANCEL_REQUESTED, JobStatus.CANCELLED):
                logger.info(f"[NormWorker] Job {job.id} was cancelled before execution.")
                await job_repo.update_status(job_id=job.id, status=JobStatus.CANCELLED, current_stage="CANCELLED")
                return

            # Pre-flight integrity verification
            if evidence.integrity_status == IntegrityStatus.MISMATCH or evidence.status == EvidenceStatus.QUARANTINED:
                err_msg = "INTEGRITY_MISMATCH: Evidence archive is flagged as compromised or quarantined."
                logger.warning(f"[NormWorker] Aborting normalization: {err_msg}")
                await job_repo.update_status(job_id=job.id, status=JobStatus.FAILED, error_message=err_msg)
                await audit_service.record_event(
                    action=AuditAction.NORMALIZATION_FAILED.value,
                    resource_type="processing_job",
                    resource_id=str(job.id),
                    user_id=job.created_by,
                    case_id=job.case_id,
                    status="FAILURE",
                    details={"reason": "INTEGRITY_MISMATCH"},
                )
                return

            # Stage 1: Initializing
            await job_repo.update_status(
                job_id=job.id,
                status=JobStatus.RUNNING,
                worker_id=worker_id,
                current_stage=ProcessingStage.FETCHING_RAW.value,
                progress=5,
            )

            await audit_service.record_event(
                action=AuditAction.NORMALIZATION_STARTED.value,
                resource_type="processing_job",
                resource_id=str(job.id),
                user_id=job.created_by,
                case_id=job.case_id,
                status="RUNNING",
                details={"evidence_id": str(evidence.id), "worker_id": worker_id},
            )

            await custody_service.record_event(
                evidence_id=evidence.id,
                case_id=job.case_id,
                event_type=CustodyEventType.EVIDENCE_NORMALIZATION_STARTED,
                actor_user_id=job.created_by,
                metadata={"job_id": str(job.id), "worker_id": worker_id},
            )

            # Stage 2: Batch Processing
            start_wall_time = time.time()
            batch_size = self.batch_size_override or max(10, self.settings.PARSER_BATCH_SIZE)

            # Count total raw artifacts to normalize
            count_stmt = select(func.count(RawArtifact.id)).where(RawArtifact.evidence_id == evidence.id)
            count_res = await session.execute(count_stmt)
            total_raw_count = count_res.scalar() or 0

            checkpoint_data: Dict[str, Any] = job.checkpoint_data or {}
            processed_count: int = int(checkpoint_data.get("records_processed", 0))
            failed_count: int = int(checkpoint_data.get("records_failed", 0))
            partial_count: int = 0

            await job_repo.update_status(
                job_id=job.id,
                status=JobStatus.RUNNING,
                current_stage=ProcessingStage.NORMALIZING.value,
                progress=10,
                files_total=total_raw_count,
                records_processed=processed_count,
            )

            offset = processed_count
            while offset < total_raw_count:
                # Check for cooperative cancellation
                if await job_repo.is_cancel_requested(job.id):
                    logger.info(f"[NormWorker] Cooperative cancellation acknowledged for job {job.id}")
                    await job_repo.update_status(
                        job_id=job.id,
                        status=JobStatus.CANCELLED,
                        current_stage="CANCELLED",
                        error_message="Job cancelled by user request during normalization.",
                    )
                    await audit_service.record_event(
                        action=AuditAction.PROCESSING_JOB_CANCELLED.value,
                        resource_type="processing_job",
                        resource_id=str(job.id),
                        user_id=job.created_by,
                        case_id=job.case_id,
                        status="CANCELLED",
                        details={"records_processed": processed_count},
                    )
                    return

                # Fetch batch of RawArtifacts
                raw_stmt = (
                    select(RawArtifact)
                    .where(RawArtifact.evidence_id == evidence.id)
                    .order_by(RawArtifact.created_at.asc(), RawArtifact.id.asc())
                    .offset(offset)
                    .limit(batch_size)
                )
                raw_res = await session.execute(raw_stmt)
                raw_batch = list(raw_res.scalars().all())

                if not raw_batch:
                    break

                # Normalize batch
                canonical_batch: List[CanonicalEvidence] = []
                for raw_art in raw_batch:
                    try:
                        canon = self.pipeline.normalize(raw_art, processing_job_id=job.id)
                        canonical_batch.append(canon)
                        if canon.data_quality_status == DataQualityStatus.PARTIAL:
                            partial_count += 1
                        elif canon.data_quality_status == DataQualityStatus.INVALID:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"[NormWorker] Error normalizing raw artifact {raw_art.id}: {e}")
                        failed_count += 1

                # Idempotent batch persistence
                if canonical_batch:
                    await canonical_repo.bulk_create_or_ignore(canonical_batch)

                processed_count += len(raw_batch)
                offset += len(raw_batch)

                # Compute telemetry
                elapsed = max(0.001, time.time() - start_wall_time)
                rate = round(processed_count / elapsed, 2)
                remaining_records = max(0, total_raw_count - processed_count)
                eta_sec = int(remaining_records / max(1.0, rate))
                progress_pct = min(95, 10 + int((processed_count / max(1, total_raw_count)) * 85))

                checkpoint_update = {
                    "records_processed": processed_count,
                    "records_failed": failed_count,
                    "records_partial": partial_count,
                    "last_offset": offset,
                }

                await job_repo.update_status(
                    job_id=job.id,
                    status=JobStatus.RUNNING,
                    current_stage=ProcessingStage.NORMALIZING.value,
                    progress=progress_pct,
                    records_processed=processed_count,
                    records_failed=failed_count,
                    artifacts_total=processed_count,
                    processing_rate=rate,
                    estimated_remaining_seconds=eta_sec,
                    checkpoint_data=checkpoint_update,
                )

            # Stage 3: Finalizing
            await job_repo.update_status(
                job_id=job.id,
                status=JobStatus.RUNNING,
                current_stage=ProcessingStage.FINALIZING.value,
                progress=98,
            )

            # Count total canonical records in DB
            db_counts = await canonical_repo.count_by_artifact_type(evidence.id)
            total_canonical = sum(db_counts.values())

            final_status = JobStatus.COMPLETED
            if failed_count > 0 and total_canonical == 0 and total_raw_count > 0:
                final_status = JobStatus.FAILED
                error_desc = "All raw artifacts failed normalization."
            elif failed_count > 0 or partial_count > 0:
                final_status = JobStatus.PARTIAL
                error_desc = f"Normalized {total_canonical} records ({partial_count} partial, {failed_count} failed)."
            else:
                error_desc = None

            elapsed_total = max(0.001, time.time() - start_wall_time)
            final_rate = round(processed_count / elapsed_total, 2)

            summary_json = {
                "total_raw_records": total_raw_count,
                "total_canonical_records": total_canonical,
                "counts_by_type": db_counts,
                "records_failed": failed_count,
                "records_partial": partial_count,
                "throughput_rec_sec": final_rate,
                "duration_seconds": round(elapsed_total, 2),
            }

            await job_repo.update_status(
                job_id=job.id,
                status=final_status,
                current_stage=ProcessingStage.COMPLETED.value if final_status == JobStatus.COMPLETED else final_status.value,
                progress=100,
                records_processed=total_canonical,
                records_failed=failed_count,
                artifacts_total=total_canonical,
                processing_rate=final_rate,
                estimated_remaining_seconds=0,
                summary_json=summary_json,
                error_message=error_desc,
            )

            # Update evidence status to PROCESSED
            evidence.status = EvidenceStatus.PROCESSED
            await session.commit()

            # Record completion custody & audit events
            await custody_service.record_event(
                evidence_id=evidence.id,
                case_id=job.case_id,
                event_type=CustodyEventType.EVIDENCE_NORMALIZATION_COMPLETED,
                actor_user_id=job.created_by,
                metadata={
                    "job_id": str(job.id),
                    "status": final_status.value,
                    "canonical_records": total_canonical,
                    "worker_id": worker_id,
                },
            )

            audit_action = (
                AuditAction.NORMALIZATION_PARTIAL.value
                if final_status == JobStatus.PARTIAL
                else (
                    AuditAction.NORMALIZATION_COMPLETED.value
                    if final_status == JobStatus.COMPLETED
                    else AuditAction.NORMALIZATION_FAILED.value
                )
            )

            await audit_service.record_event(
                action=audit_action,
                resource_type="processing_job",
                resource_id=str(job.id),
                user_id=job.created_by,
                case_id=job.case_id,
                status="SUCCESS" if final_status in (JobStatus.COMPLETED, JobStatus.PARTIAL) else "FAILURE",
                details={
                    "evidence_id": str(evidence.id),
                    "canonical_records": total_canonical,
                    "records_failed": failed_count,
                    "worker_id": worker_id,
                },
            )

            logger.info(
                f"[NormWorker:{worker_id}] Job {job.id} completed as {final_status.value}. "
                f"Canonical records: {total_canonical} ({final_rate} rec/s)."
            )
