import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.models.enums import ArtifactType

if TYPE_CHECKING:
    from backend.app.models.case import Case
    from backend.app.models.evidence import Evidence
    from backend.app.models.processing_job import ProcessingJob


class RawArtifact(Base):
    """
    Raw Forensic Artifact.
    Represents an unprocessed or minimally structured artifact extracted from UFDR containers,
    retaining full source provenance and traceability.
    """
    __tablename__ = "raw_artifacts"

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
    processing_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        SQLEnum(ArtifactType, name="artifact_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    artifact_fingerprint: Mapped[str] = mapped_column(
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
    raw_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    case: Mapped["Case"] = relationship(
        "Case",
    )
    evidence: Mapped["Evidence"] = relationship(
        "Evidence",
        back_populates="artifacts",
    )
    processing_job: Mapped["ProcessingJob"] = relationship(
        "ProcessingJob",
        back_populates="artifacts",
    )
    canonical_record: Mapped[Optional["backend.app.models.canonical_evidence.CanonicalEvidence"]] = relationship(
        "backend.app.models.canonical_evidence.CanonicalEvidence",
        back_populates="raw_artifact",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_raw_artifacts_case_evidence_type", "case_id", "evidence_id", "artifact_type"),
        Index("ix_raw_artifacts_job_type", "processing_job_id", "artifact_type"),
        Index("ix_raw_artifacts_evidence_source", "evidence_id", "source_file"),
        Index("ix_raw_artifacts_traceability", "evidence_id", "record_identifier"),
        UniqueConstraint("evidence_id", "artifact_fingerprint", name="uq_raw_artifact_identity"),
    )
