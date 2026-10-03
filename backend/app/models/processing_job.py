import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import BigInteger, DateTime, Enum as SQLEnum, Float, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.models.enums import JobPriority, JobStatus, JobType, ProcessingStage

if TYPE_CHECKING:
    from backend.app.models.case import Case
    from backend.app.models.evidence import Evidence
    from backend.app.models.raw_artifact import RawArtifact
    from backend.app.models.user import User


class ProcessingJob(Base):
    """
    Forensic Ingestion and Processing Job.
    Represents an asynchronous pipeline execution against an Evidence package.
    """
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[JobType] = mapped_column(
        SQLEnum(JobType, name="job_type_enum", native_enum=False),
        nullable=False,
        default=JobType.UFDR_PARSE,
        index=True,
    )
    priority: Mapped[JobPriority] = mapped_column(
        SQLEnum(JobPriority, name="job_priority_enum", native_enum=False),
        nullable=False,
        default=JobPriority.NORMAL,
        index=True,
    )
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, name="job_status_enum", native_enum=False),
        nullable=False,
        default=JobStatus.QUEUED,
        index=True,
    )
    current_stage: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default=ProcessingStage.VALIDATING.value,
    )
    current_file: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    worker_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    files_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    files_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    artifacts_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    records_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    records_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    bytes_processed: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    bytes_total: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    processing_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    estimated_remaining_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )
    checkpoint_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    warnings_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    errors_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    summary_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="processing_jobs",
    )
    evidence: Mapped["Evidence"] = relationship(
        "Evidence",
        back_populates="processing_jobs",
    )
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="selectin",
    )
    artifacts: Mapped[List["RawArtifact"]] = relationship(
        "RawArtifact",
        back_populates="processing_job",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_processing_jobs_case_evidence", "case_id", "evidence_id"),
        Index("ix_processing_jobs_status_type", "status", "job_type"),
        # Phase 8: efficient worker dispatch — find QUEUED jobs by priority + age
        Index("ix_processing_jobs_status_priority_created", "status", "priority", "created_at"),
    )
