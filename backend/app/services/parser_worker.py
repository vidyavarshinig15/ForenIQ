import asyncio
from datetime import datetime, timezone
import hashlib
import logging
import os
import shutil
import time
import uuid
from typing import Any, Dict, List, Optional, Set

from backend.app.core.config import get_settings
from backend.app.core.database import async_session_factory
from backend.app.models.enums import (
    ArtifactType,
    AuditAction,
    CustodyEventType,
    EvidenceStatus,
    IntegrityStatus,
    JobPriority,
    JobStatus,
    JobType,
    ProcessingStage,
)
from backend.app.models.raw_artifact import RawArtifact
from backend.app.parser import (
    MalformedXMLError,
    ParserError,
    ParserSecurityError,
    SafeArchiveInspector,
    UFDRDetector,
    UnsupportedUFDRFormatError,
    ZipBombError,
    ZipSlipError,
    get_default_registry,
)
from backend.app.parser.models import ArchiveInventoryItem, ProcessingSummary
from backend.app.repositories.evidence_repo import EvidenceRepository
from backend.app.repositories.processing_job_repo import ProcessingJobRepository
from backend.app.repositories.raw_artifact_repo import RawArtifactRepository
from backend.app.services.audit_service import AuditService
from backend.app.services.custody_service import CustodyService
from backend.app.services.storage.local import LocalStorageService

logger = logging.getLogger(__name__)


class UFDRParserWorker:
    """
    Scalable, resilient forensic processing worker.
    Features:
    - Pre-flight storage and cryptographic integrity verification
    - Bounded-concurrency and resource governance (MAX_TEMP_STORAGE)
    - Checkpointed, resumable archive member processing
    - Memory-bounded streaming XML and backpressure-regulated batch persistence
    - Idempotent duplicate prevention via deterministic fingerprints and ON CONFLICT DO NOTHING
    - Cooperative cancellation support
    - Real-time measurable processing metrics (records/sec, ETA, stages)
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    async def execute_job(self, job_id: uuid.UUID, worker_id: Optional[str] = None) -> None:
        """
        Main worker execution entrypoint called asynchronously from WorkerPool or BackgroundTasks.
        """
        async with async_session_factory() as session:
            job_repo = ProcessingJobRepository(session)
            evidence_repo = EvidenceRepository(session)
            artifact_repo = RawArtifactRepository(session)
            custody_service = CustodyService(session)
            audit_service = AuditService(session)
            storage = LocalStorageService()
            inspector = SafeArchiveInspector()
            detector = UFDRDetector()
            registry = get_default_registry()

            job = await job_repo.get_by_id(job_id)
            if not job:
                logger.error(f"[Worker] Processing job {job_id} not found.")
                return

            evidence = await evidence_repo.get_by_id(job.evidence_id)
            if not evidence:
                logger.error(f"[Worker] Evidence {job.evidence_id} not found for job {job_id}.")
                await job_repo.update_status(
                    job_id=job.id,
                    status=JobStatus.FAILED,
                    error_message=f"Evidence {job.evidence_id} not found.",
                )
                return

            sandbox_dir = os.path.join(self.settings.SCRATCH_STORAGE_PATH, "jobs", str(job.id))
            summary = ProcessingSummary()
            start_wall_time = time.time()

            try:
                # Check for cancellation before starting work
                if job.status in (JobStatus.CANCEL_REQUESTED, JobStatus.CANCELLED):
                    logger.info(f"[Worker] Job {job.id} cancellation acknowledged before start. Aborting cleanly...")
                    await job_repo.update_status(
                        job_id=job.id,
                        status=JobStatus.CANCELLED,
                        current_stage="CANCELLED",
                        error_message="Job cancelled by user request.",
                    )
                    await audit_service.record_event(
                        action=AuditAction.PROCESSING_JOB_CANCELLED.value,
                        resource_type="processing_job",
                        resource_id=str(job.id),
                        user_id=job.created_by,
                        case_id=job.case_id,
                        status="CANCELLED",
                        details={"records_processed": 0, "files_processed": 0},
                    )
                    return

                # -------------------------------------------------------------
                # STAGE 1: VALIDATING (Pre-Flight Integrity & Resource Checks)
                # -------------------------------------------------------------
                await job_repo.update_status(
                    job_id=job.id,
                    status=JobStatus.RUNNING,
                    worker_id=worker_id,
                    current_stage=ProcessingStage.VALIDATING.value,
                    progress=5,
                )

                # Storage capacity check
                os.makedirs(self.settings.SCRATCH_STORAGE_PATH, exist_ok=True)
                free_space_bytes = shutil.disk_usage(self.settings.SCRATCH_STORAGE_PATH).free
                required_space_bytes = self.settings.MAX_TEMP_STORAGE_MB * 1024 * 1024
                if free_space_bytes < min(required_space_bytes, 50 * 1024 * 1024):  # At least 50MB
                    err_msg = f"INSUFFICIENT_TEMP_STORAGE: Scratch volume has {free_space_bytes // (1024*1024)}MB free."
                    logger.error(f"[Worker] {err_msg}")
                    await job_repo.update_status(job_id=job.id, status=JobStatus.FAILED, error_message=err_msg)
                    return

                # Integrity check against baseline
                if evidence.integrity_status == IntegrityStatus.MISMATCH or evidence.status == EvidenceStatus.QUARANTINED:
                    logger.warning(f"[Worker] Aborting parse for compromised/quarantined evidence {evidence.id}")
                    await job_repo.update_status(
                        job_id=job.id,
                        status=JobStatus.FAILED,
                        error_message="INTEGRITY_MISMATCH: Evidence archive is flagged as compromised or quarantined.",
                    )
                    await audit_service.record_event(
                        action=AuditAction.PROCESSING_JOB_FAILED.value,
                        resource_type="processing_job",
                        resource_id=str(job.id),
                        user_id=job.created_by,
                        case_id=job.case_id,
                        status="FAILURE",
                        details={"reason": "INTEGRITY_MISMATCH"},
                    )
                    return

                if not await storage.exists(evidence.storage_path_or_key):
                    logger.error(f"[Worker] Evidence file missing from storage: {evidence.storage_path_or_key}")
                    await job_repo.update_status(
                        job_id=job.id,
                        status=JobStatus.FAILED,
                        error_message="Evidence physical archive file is missing from storage.",
                    )
                    return

                # Streaming SHA-256 calculation
                hasher = hashlib.sha256()
                bytes_hashed = 0
                async for chunk in storage.get_stream(evidence.storage_path_or_key):
                    hasher.update(chunk)
                    bytes_hashed += len(chunk)
                computed_hash = hasher.hexdigest().lower()

                if evidence.sha256_hash and computed_hash != evidence.sha256_hash.lower():
                    logger.error(
                        f"[Worker] Integrity check failed for evidence {evidence.id}. "
                        f"Expected {evidence.sha256_hash}, got {computed_hash}"
                    )
                    evidence.integrity_status = IntegrityStatus.MISMATCH
                    evidence.status = EvidenceStatus.QUARANTINED
                    await session.commit()

                    await custody_service.record_event(
                        evidence_id=evidence.id,
                        case_id=job.case_id,
                        event_type=CustodyEventType.INTEGRITY_MISMATCH,
                        actor_user_id=job.created_by,
                        metadata={"expected_hash": evidence.sha256_hash, "computed_hash": computed_hash},
                    )
                    await job_repo.update_status(
                        job_id=job.id,
                        status=JobStatus.FAILED,
                        error_message="INTEGRITY_MISMATCH: Stored evidence file SHA-256 digest differs from baseline record.",
                    )
                    return

                # Record custody & audit start events
                await custody_service.record_event(
                    evidence_id=evidence.id,
                    case_id=job.case_id,
                    event_type=CustodyEventType.EVIDENCE_PROCESSING_STARTED,
                    actor_user_id=job.created_by,
                    metadata={"job_id": str(job.id), "job_type": job.job_type.value, "worker_id": worker_id},
                )
                await audit_service.record_event(
                    action=AuditAction.PROCESSING_JOB_STARTED.value,
                    resource_type="processing_job",
                    resource_id=str(job.id),
                    user_id=job.created_by,
                    case_id=job.case_id,
                    status="SUCCESS",
                    details={"evidence_id": str(evidence.id), "worker_id": worker_id},
                )

                # -------------------------------------------------------------
                # STAGE 2: INSPECTING_ARCHIVE & UFDR Layout Detection
                # -------------------------------------------------------------
                await job_repo.update_status(
                    job_id=job.id,
                    status=JobStatus.RUNNING,
                    current_stage=ProcessingStage.INSPECTING_ARCHIVE.value,
                    progress=15,
                    bytes_total=evidence.file_size,
                    bytes_processed=bytes_hashed,
                )

                physical_path = storage._resolve_safe_path(evidence.storage_path_or_key)
                inventory = inspector.inspect_and_build_inventory(str(physical_path))
                detection = detector.detect(inventory)

                if not detection.is_supported:
                    raise UnsupportedUFDRFormatError(detection.reason)

                target_items: List[ArchiveInventoryItem] = [
                    item for item in inventory if registry.get_parsers_for_item(item)
                ]
                files_total = len(target_items)
                summary.files_total = files_total

                # -------------------------------------------------------------
                # STAGE 3: RESUMPTION CHECKPOINT & PARSING
                # -------------------------------------------------------------
                checkpoint_data: Dict[str, Any] = job.checkpoint_data or {}
                completed_files_set: Set[str] = set(checkpoint_data.get("completed_files", []))
                total_artifacts: int = int(checkpoint_data.get("records_processed", 0))
                files_processed: int = len(completed_files_set)
                files_failed: int = int(checkpoint_data.get("files_failed", 0))
                for cat, count in checkpoint_data.get("counts_by_type", {}).items():
                    summary.counts_by_type[cat] = count

                batch_size = max(10, self.settings.PARSER_BATCH_SIZE)
                artifacts_batch: List[RawArtifact] = []

                context = {
                    "case_id": job.case_id,
                    "evidence_id": evidence.id,
                    "job_id": job.id,
                }

                await job_repo.update_status(
                    job_id=job.id,
                    status=JobStatus.RUNNING,
                    current_stage=ProcessingStage.PARSING.value,
                    progress=20,
                    files_total=files_total,
                    files_processed=files_processed,
                    records_processed=total_artifacts,
                )

                for item in target_items:
                    # Check for cooperative cancellation request
                    refreshed_job = await job_repo.get_by_id(job.id)
                    if refreshed_job and refreshed_job.status == JobStatus.CANCEL_REQUESTED:
                        logger.info(f"[Worker] Job {job.id} cancellation acknowledged. Aborting cleanly...")
                        await job_repo.update_status(
                            job_id=job.id,
                            status=JobStatus.CANCELLED,
                            current_stage="CANCELLED",
                            error_message="Job cancelled by user request.",
                        )
                        await audit_service.record_event(
                            action=AuditAction.PROCESSING_JOB_CANCELLED.value,
                            resource_type="processing_job",
                            resource_id=str(job.id),
                            user_id=job.created_by,
                            case_id=job.case_id,
                            status="CANCELLED",
                            details={"records_processed": total_artifacts, "files_processed": files_processed},
                        )
                        return

                    # Resumable skip: if file was already completed in prior run, skip it!
                    if item.path in completed_files_set:
                        logger.info(f"[Worker] Resuming: skipping already completed member '{item.path}'")
                        continue

                    matched_parsers = registry.get_parsers_for_item(item)
                    if not matched_parsers:
                        continue

                    # Update current file stage
                    await job_repo.update_status(
                        job_id=job.id,
                        status=JobStatus.RUNNING,
                        current_stage=ProcessingStage.PARSING.value,
                        current_file=item.path,
                    )

                    try:
                        # Extract only this individual member into controlled sandbox
                        inspector.safe_extract_to_sandbox(
                            archive_path=str(physical_path),
                            sandbox_dir=sandbox_dir,
                            file_filter=[item.path],
                        )
                        local_extracted_path = os.path.join(sandbox_dir, item.path)

                        for parser in matched_parsers:
                            for record in parser.parse(local_extracted_path, item, context):
                                # Deterministic identity: composite SHA-256 fingerprint & UUIDv5
                                identity_key = (
                                    f"{evidence.id}:{record.source_file}:{record.source_path}:"
                                    f"{record.record_identifier}:{record.artifact_type.value}"
                                )
                                fingerprint = hashlib.sha256(identity_key.encode("utf-8")).hexdigest()
                                deterministic_id = uuid.uuid5(evidence.id, identity_key)

                                artifact_entity = RawArtifact(
                                    id=deterministic_id,
                                    case_id=job.case_id,
                                    evidence_id=evidence.id,
                                    processing_job_id=job.id,
                                    artifact_type=record.artifact_type,
                                    artifact_fingerprint=fingerprint,
                                    source_file=record.source_file,
                                    source_path=record.source_path,
                                    record_identifier=record.record_identifier,
                                    raw_data=record.raw_data,
                                    parsed_at=record.parsed_at,
                                )
                                artifacts_batch.append(artifact_entity)
                                total_artifacts += 1

                                cat_val = record.artifact_type.value
                                summary.counts_by_type[cat_val] = summary.counts_by_type.get(cat_val, 0) + 1

                                # Bounded batch persistence with backpressure
                                if len(artifacts_batch) >= batch_size:
                                    await job_repo.update_status(
                                        job_id=job.id,
                                        status=JobStatus.RUNNING,
                                        current_stage=ProcessingStage.PERSISTING.value,
                                    )
                                    await artifact_repo.bulk_create_or_ignore(artifacts_batch)
                                    artifacts_batch.clear()

                        # Flush remaining artifacts for this member
                        if artifacts_batch:
                            await artifact_repo.bulk_create_or_ignore(artifacts_batch)
                            artifacts_batch.clear()

                        files_processed += 1
                        completed_files_set.add(item.path)

                        # Clean up individual extracted file to keep disk bounded
                        if os.path.exists(local_extracted_path):
                            try:
                                os.remove(local_extracted_path)
                            except OSError:
                                pass

                    except (MalformedXMLError, ParserError) as pe:
                        files_failed += 1
                        err_msg = f"Failed parsing member '{item.path}': {pe}"
                        logger.warning(f"[Worker] {err_msg}")
                        summary.warnings.append(err_msg)
                    except Exception as e:
                        files_failed += 1
                        err_msg = f"Unexpected error parsing member '{item.path}': {e}"
                        logger.error(f"[Worker] {err_msg}")
                        summary.errors.append(err_msg)

                    # Update checkpoint and real-time processing metrics
                    elapsed = max(0.001, time.time() - start_wall_time)
                    rate = round(total_artifacts / elapsed, 2)
                    remaining_files = max(0, files_total - (files_processed + files_failed))
                    eta_sec = int(remaining_files * (elapsed / max(1, files_processed + files_failed)))

                    progress_pct = 20 + int(((files_processed + files_failed) / max(files_total, 1)) * 75)
                    checkpoint_update = {
                        "completed_files": list(completed_files_set),
                        "records_processed": total_artifacts,
                        "files_failed": files_failed,
                        "last_file": item.path,
                        "counts_by_type": summary.counts_by_type,
                    }

                    await job_repo.update_status(
                        job_id=job.id,
                        status=JobStatus.RUNNING,
                        current_stage=ProcessingStage.PARSING.value,
                        progress=min(95, progress_pct),
                        files_processed=files_processed,
                        artifacts_total=total_artifacts,
                        records_processed=total_artifacts,
                        records_failed=files_failed,
                        processing_rate=rate,
                        estimated_remaining_seconds=eta_sec,
                        checkpoint_data=checkpoint_update,
                        warnings_count=len(summary.warnings),
                        errors_count=len(summary.errors),
                    )

                # -------------------------------------------------------------
                # STAGE 4: FINALIZING & SUMMARY GENERATION
                # -------------------------------------------------------------
                await job_repo.update_status(
                    job_id=job.id,
                    status=JobStatus.RUNNING,
                    current_stage=ProcessingStage.FINALIZING.value,
                    progress=98,
                )

                # Sync actual total counts from repository for exact provenance
                db_counts = await artifact_repo.count_by_artifact_type(evidence.id)
                for cat, count in db_counts.items():
                    summary.counts_by_type[cat] = count

                summary.files_processed = files_processed
                summary.files_failed = files_failed
                summary.artifacts_extracted = max(total_artifacts, sum(summary.counts_by_type.values()))
                total_artifacts = summary.artifacts_extracted

                final_status = JobStatus.COMPLETED
                if files_failed > 0 and files_processed == 0 and total_artifacts == 0:
                    final_status = JobStatus.FAILED
                    error_desc = "; ".join(summary.errors or summary.warnings) or "All artifact files failed parsing."
                elif files_failed > 0:
                    final_status = JobStatus.PARTIAL
                    error_desc = f"Processed {files_processed} files with {files_failed} failed files."
                else:
                    error_desc = None

                elapsed_total = max(0.001, time.time() - start_wall_time)
                final_rate = round(total_artifacts / elapsed_total, 2)

                await job_repo.update_status(
                    job_id=job.id,
                    status=final_status,
                    current_stage=ProcessingStage.COMPLETED.value if final_status == JobStatus.COMPLETED else final_status.value,
                    progress=100,
                    files_processed=files_processed,
                    artifacts_total=total_artifacts,
                    records_processed=total_artifacts,
                    records_failed=files_failed,
                    processing_rate=final_rate,
                    estimated_remaining_seconds=0,
                    warnings_count=len(summary.warnings),
                    errors_count=len(summary.errors),
                    summary_json=summary.to_dict(),
                    error_message=error_desc,
                )

                # Record completion custody & audit events
                await custody_service.record_event(
                    evidence_id=evidence.id,
                    case_id=job.case_id,
                    event_type=CustodyEventType.EVIDENCE_PROCESSING_COMPLETED,
                    actor_user_id=job.created_by,
                    metadata={
                        "job_id": str(job.id),
                        "status": final_status.value,
                        "artifacts_extracted": total_artifacts,
                        "files_processed": files_processed,
                        "worker_id": worker_id,
                    },
                )

                audit_action = (
                    AuditAction.PROCESSING_JOB_PARTIAL.value
                    if final_status == JobStatus.PARTIAL
                    else (
                        AuditAction.PROCESSING_JOB_COMPLETED.value
                        if final_status == JobStatus.COMPLETED
                        else AuditAction.PROCESSING_JOB_FAILED.value
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
                        "artifacts_extracted": total_artifacts,
                        "files_processed": files_processed,
                        "files_failed": files_failed,
                        "worker_id": worker_id,
                    },
                )

                logger.info(
                    f"[Worker] Job {job.id} completed as {final_status.value}. "
                    f"Total records: {total_artifacts} ({final_rate} rec/s)."
                )

            except (ParserSecurityError, ZipBombError, ZipSlipError) as sec_err:
                logger.error(f"[Worker] Security error during processing of evidence {evidence.id}: {sec_err}")
                await job_repo.update_status(
                    job_id=job.id,
                    status=JobStatus.FAILED,
                    error_message=f"SECURITY_VIOLATION: {sec_err}",
                )
                await audit_service.record_event(
                    action=AuditAction.PROCESSING_JOB_FAILED.value,
                    resource_type="processing_job",
                    resource_id=str(job.id),
                    user_id=job.created_by,
                    case_id=job.case_id,
                    status="FAILURE",
                    details={"error": str(sec_err)},
                )
                raise

            except UnsupportedUFDRFormatError as fmt_err:
                logger.error(f"[Worker] Unsupported UFDR format for evidence {evidence.id}: {fmt_err}")
                await job_repo.update_status(
                    job_id=job.id,
                    status=JobStatus.FAILED,
                    error_message=f"UNSUPPORTED_UFDR_STRUCTURE: {fmt_err}",
                )
                await audit_service.record_event(
                    action=AuditAction.PROCESSING_JOB_FAILED.value,
                    resource_type="processing_job",
                    resource_id=str(job.id),
                    user_id=job.created_by,
                    case_id=job.case_id,
                    status="FAILURE",
                    details={"error": str(fmt_err)},
                )
                raise

            except Exception as exc:
                logger.exception(f"[Worker] Unhandled exception in job {job.id}: {exc}")
                await job_repo.update_status(
                    job_id=job.id,
                    status=JobStatus.FAILED,
                    error_message=f"INTERNAL_PROCESSING_ERROR: {str(exc)}",
                )
                await audit_service.record_event(
                    action=AuditAction.PROCESSING_JOB_FAILED.value,
                    resource_type="processing_job",
                    resource_id=str(job.id),
                    user_id=job.created_by,
                    case_id=job.case_id,
                    status="FAILURE",
                    details={"error": str(exc)},
                )
                raise

            finally:
                # Guaranteed cleanup of sandbox
                inspector.cleanup_sandbox(sandbox_dir)
