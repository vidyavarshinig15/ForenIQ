"""
Phase 10 — Evidence Embedding Worker

Asynchronous worker processing CanonicalEvidence records into dense vector embeddings.
Integrates with Phase 6 JobWorker queue infrastructure, supporting batching,
resumable checkpointing, cooperative cancellation, idempotency, and staleness detection.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Set
import uuid

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.database import async_session_factory
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import (
    AuditAction,
    EmbeddingStatus,
    JobStatus,
    ProcessingStage,
)
from backend.app.models.evidence_embedding import EvidenceEmbedding
from backend.app.models.processing_job import ProcessingJob
from backend.app.repositories.embedding_repo import EmbeddingRepository
from backend.app.repositories.processing_job_repo import ProcessingJobRepository
from backend.app.services.audit_service import AuditService
from backend.app.services.embedding_formatter import EmbeddingFormatter
from backend.app.services.embedding_service import get_embedding_service
from backend.app.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class EvidenceEmbeddingWorker:
    """
    Asynchronous forensic worker responsible for generating dense vector embeddings
    for canonical evidence records within a case boundary.
    """

    def __init__(self, batch_size: Optional[int] = None) -> None:
        self.settings = get_settings()
        self.batch_size = batch_size or self.settings.EMBEDDING_BATCH_SIZE
        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store()

    async def execute(self, job_id: uuid.UUID, worker_id: Optional[str] = None) -> bool:
        """Helper alias matching test runner interface."""
        await self.execute_job(job_id, worker_id)
        async with async_session_factory() as session:
            job = await session.get(ProcessingJob, job_id)
            return job is not None and job.status in (JobStatus.COMPLETED, JobStatus.PARTIAL)

    async def execute_job(self, job_id: uuid.UUID, worker_id: Optional[str] = None) -> None:
        worker_id = worker_id or f"embed-worker-{uuid.uuid4().hex[:6]}"
        logger.info(f"[EmbeddingWorker:{worker_id}] Starting embedding generation job {job_id}")

        async with async_session_factory() as session:
            job_repo = ProcessingJobRepository(session)
            emb_repo = EmbeddingRepository(session)
            audit_service = AuditService(session)

            job = await job_repo.get_by_id(job_id)
            if not job:
                logger.error(f"[EmbeddingWorker] Job {job_id} not found.")
                return

            case_id = job.case_id
            evidence_id = job.evidence_id

            # Check pre-flight cancellation
            if job.status in (JobStatus.CANCEL_REQUESTED, JobStatus.CANCELLED):
                logger.info(f"[EmbeddingWorker] Job {job.id} was cancelled before starting.")
                await job_repo.update_status(job_id=job.id, status=JobStatus.CANCELLED, current_stage="CANCELLED")
                return

            # Stage: STARTING
            await job_repo.update_status(
                job_id=job.id,
                status=JobStatus.RUNNING,
                current_stage="GENERATING_EMBEDDINGS",
                worker_id=worker_id,
            )
            await audit_service.record_event(
                action=AuditAction.EMBEDDING_JOB_STARTED.value,
                resource_type="processing_job",
                resource_id=str(job.id),
                user_id=job.created_by,
                case_id=job.case_id,
                status="SUCCESS",
                details={"model": self.settings.EMBEDDING_MODEL_NAME, "dimension": self.settings.EMBEDDING_DIMENSION},
            )

            # Count total canonical records for this case / evidence
            count_stmt = select(func.count(CanonicalEvidence.id)).where(CanonicalEvidence.case_id == case_id)
            if evidence_id:
                count_stmt = count_stmt.where(CanonicalEvidence.evidence_id == evidence_id)
            total_records_res = await session.execute(count_stmt)
            total_records = total_records_res.scalar() or 0

            if total_records == 0:
                logger.info(f"[EmbeddingWorker] No canonical records found for case {case_id}.")
                await job_repo.update_status(
                    job_id=job.id,
                    status=JobStatus.COMPLETED,
                    current_stage="COMPLETED",
                    processed_items=0,
                    total_items=0,
                    progress_percentage=100.0,
                )
                return

            # Process in streaming batches
            offset = 0
            processed_count = 0
            embedded_count = 0
            skipped_count = 0
            not_embeddable_count = 0
            error_count = 0

            # Restore from checkpoint if available
            if job.checkpoint_data and "processed_count" in job.checkpoint_data:
                processed_count = job.checkpoint_data.get("processed_count", 0)
                offset = processed_count
                logger.info(f"[EmbeddingWorker] Resuming job {job.id} from record offset {offset}")

            while offset < total_records:
                # Check for cancellation between batches
                fresh_job = await session.get(ProcessingJob, job.id)
                if fresh_job and fresh_job.status in (JobStatus.CANCEL_REQUESTED, JobStatus.CANCELLED):
                    logger.info(f"[EmbeddingWorker] Cancellation requested for job {job.id} at offset {offset}")
                    await job_repo.update_status(job_id=job.id, status=JobStatus.CANCELLED, current_stage="CANCELLED")
                    return

                # Fetch batch of CanonicalEvidence records
                stmt = select(CanonicalEvidence).where(CanonicalEvidence.case_id == case_id)
                if evidence_id:
                    stmt = stmt.where(CanonicalEvidence.evidence_id == evidence_id)
                stmt = stmt.order_by(CanonicalEvidence.created_at.asc()).offset(offset).limit(self.batch_size)
                res = await session.execute(stmt)
                records = list(res.scalars().all())

                if not records:
                    break

                batch_texts: List[str] = []
                batch_ids: List[uuid.UUID] = []
                batch_records: List[CanonicalEvidence] = []
                batch_hashes: List[str] = []

                for record in records:
                    formatted_text, content_hash = EmbeddingFormatter.format_canonical_record(record)
                    if formatted_text is None or content_hash is None:
                        # Not embeddable
                        await emb_repo.upsert_embedding_record(
                            case_id=case_id,
                            canonical_id=record.id,
                            model_name=self.settings.EMBEDDING_MODEL_NAME,
                            model_version=self.settings.EMBEDDING_MODEL_VERSION,
                            dimension=self.settings.EMBEDDING_DIMENSION,
                            content_hash="",
                            status=EmbeddingStatus.NOT_EMBEDDABLE,
                        )
                        not_embeddable_count += 1
                        continue

                    # Check if already generated and current
                    existing_emb = await emb_repo.get_by_canonical_id(record.id)
                    if (
                        existing_emb
                        and existing_emb.status == EmbeddingStatus.READY
                        and existing_emb.content_hash == content_hash
                        and existing_emb.model_name == self.settings.EMBEDDING_MODEL_NAME
                        and existing_emb.model_version == self.settings.EMBEDDING_MODEL_VERSION
                    ):
                        skipped_count += 1
                        continue

                    batch_texts.append(formatted_text)
                    batch_ids.append(record.id)
                    batch_records.append(record)
                    batch_hashes.append(content_hash)

                # Generate embeddings for valid batch items
                if batch_texts:
                    try:
                        vectors = self.embedding_service.embed_texts(batch_texts)
                        # Add to vector store
                        self.vector_store.add(
                            case_id=case_id,
                            ids=batch_ids,
                            vectors=vectors,
                        )

                        # Update database embedding records
                        for rec, hsh in zip(batch_records, batch_hashes):
                            await emb_repo.upsert_embedding_record(
                                case_id=case_id,
                                canonical_id=rec.id,
                                model_name=self.settings.EMBEDDING_MODEL_NAME,
                                model_version=self.settings.EMBEDDING_MODEL_VERSION,
                                dimension=self.settings.EMBEDDING_DIMENSION,
                                content_hash=hsh,
                                status=EmbeddingStatus.READY,
                            )
                        embedded_count += len(batch_ids)

                    except Exception as e:
                        logger.error(f"[EmbeddingWorker] Error generating embeddings for batch: {e}")
                        error_count += len(batch_ids)
                        for rec, hsh in zip(batch_records, batch_hashes):
                            await emb_repo.upsert_embedding_record(
                                case_id=case_id,
                                canonical_id=rec.id,
                                model_name=self.settings.EMBEDDING_MODEL_NAME,
                                model_version=self.settings.EMBEDDING_MODEL_VERSION,
                                dimension=self.settings.EMBEDDING_DIMENSION,
                                content_hash=hsh,
                                status=EmbeddingStatus.FAILED,
                                error_message=str(e)[:500],
                            )

                processed_count += len(records)
                offset += len(records)

                # Checkpoint progress
                pct = min(100.0, round((processed_count / total_records) * 100.0, 1))
                await job_repo.update_progress(
                    job_id=job.id,
                    processed_items=processed_count,
                    total_items=total_records,
                    progress_percentage=pct,
                    checkpoint_data={
                        "processed_count": processed_count,
                        "embedded_count": embedded_count,
                        "skipped_count": skipped_count,
                        "not_embeddable_count": not_embeddable_count,
                        "error_count": error_count,
                    },
                )
                await session.commit()

            # Finalize: persist vector index to disk
            self.vector_store.persist(case_id)

            final_status = JobStatus.PARTIAL if error_count > 0 and embedded_count > 0 else (
                JobStatus.FAILED if error_count > 0 and embedded_count == 0 else JobStatus.COMPLETED
            )

            await job_repo.update_status(
                job_id=job.id,
                status=final_status,
                current_stage="COMPLETED",
                processed_items=processed_count,
                total_items=total_records,
                progress_percentage=100.0,
                error_message=f"Encountered {error_count} record errors" if error_count > 0 else None,
            )

            await audit_service.record_event(
                action=AuditAction.EMBEDDING_JOB_COMPLETED.value if final_status == JobStatus.COMPLETED else AuditAction.EMBEDDING_JOB_FAILED.value,
                resource_type="processing_job",
                resource_id=str(job.id),
                user_id=job.created_by,
                case_id=job.case_id,
                status="SUCCESS" if final_status == JobStatus.COMPLETED else "PARTIAL",
                details={
                    "total_records": total_records,
                    "embedded_count": embedded_count,
                    "skipped_count": skipped_count,
                    "not_embeddable_count": not_embeddable_count,
                    "error_count": error_count,
                },
            )
            await session.commit()
            logger.info(
                f"[EmbeddingWorker] Completed job {job.id}: embedded={embedded_count}, skipped={skipped_count}, not_embeddable={not_embeddable_count}, errors={error_count}"
            )
