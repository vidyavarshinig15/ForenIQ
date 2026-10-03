import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.models.enums import ArtifactType, DataQualityStatus, TimestampPrecision, TimestampStatus

if TYPE_CHECKING:
    from backend.app.models.case import Case
    from backend.app.models.evidence import Evidence
    from backend.app.models.processing_job import ProcessingJob
    from backend.app.models.raw_artifact import RawArtifact


class CanonicalEvidence(Base):
    """
    Canonical Forensic Evidence Record.
    Standardized, normalized forensic entity representing calls, messages, contacts,
    locations, browser events, applications, and filesystem objects in a unified schema.
    Maintains full forensic lineage to the originating RawArtifact and Evidence package.
    """
    __tablename__ = "canonical_evidence"

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
    raw_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("raw_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    processing_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        SQLEnum(ArtifactType, name="artifact_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    canonical_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    source_file: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    source_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    record_identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # Normalized Timestamps
    event_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    timestamp_precision: Mapped[TimestampPrecision] = mapped_column(
        SQLEnum(TimestampPrecision, name="timestamp_precision_enum", native_enum=False),
        nullable=False,
        default=TimestampPrecision.UNKNOWN,
    )
    timestamp_status: Mapped[TimestampStatus] = mapped_column(
        SQLEnum(TimestampStatus, name="timestamp_status_enum", native_enum=False),
        nullable=False,
        default=TimestampStatus.UNKNOWN,
    )
    original_timestamp: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    original_timezone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Device & Application Provenance
    device_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    application: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    original_application: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Normalized Content & Structured References
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    entities: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    # Data Quality & Validation
    data_quality_status: Mapped[DataQualityStatus] = mapped_column(
        SQLEnum(DataQualityStatus, name="data_quality_status_enum", native_enum=False),
        nullable=False,
        default=DataQualityStatus.VALID,
        index=True,
    )
    validation_warnings: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Version Tracking
    parser_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="1.0.0",
    )
    normalizer_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="1.0.0",
    )

    # Timestamps
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
    )
    evidence: Mapped["Evidence"] = relationship(
        "Evidence",
        back_populates="canonical_records",
    )
    raw_artifact: Mapped["RawArtifact"] = relationship(
        "RawArtifact",
        back_populates="canonical_record",
    )
    processing_job: Mapped[Optional["ProcessingJob"]] = relationship(
        "ProcessingJob",
    )

    __table_args__ = (
        UniqueConstraint("evidence_id", "canonical_fingerprint", name="uq_canonical_evidence_identity"),
        UniqueConstraint("raw_artifact_id", name="uq_canonical_evidence_raw_artifact"),
        # Original Phase 7 indexes
        Index("ix_canonical_evidence_case_type_time", "case_id", "artifact_type", "event_timestamp"),
        Index("ix_canonical_evidence_evidence_type", "evidence_id", "artifact_type"),
        Index("ix_canonical_evidence_app_time", "application", "event_timestamp"),
        # Phase 8: cursor-pagination and case-scoped query indexes
        Index("ix_canonical_evidence_case_time_id", "case_id", "event_timestamp", "id"),
        Index("ix_canonical_evidence_case_device_time", "case_id", "device_id", "event_timestamp"),
        Index("ix_canonical_evidence_case_quality_type", "case_id", "data_quality_status", "artifact_type"),
        Index("ix_canonical_evidence_evidence_time_id", "evidence_id", "event_timestamp", "id"),
    )
