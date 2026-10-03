import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.models.enums import EvidenceStatus, IntegrityStatus

if TYPE_CHECKING:
    from backend.app.models.case import Case
    from backend.app.models.custody import EvidenceCustodyEvent
    from backend.app.models.processing_job import ProcessingJob
    from backend.app.models.raw_artifact import RawArtifact
    from backend.app.models.user import User


class Evidence(Base):
    """
    Forensic Evidence Entity.
    Represents an ingested UFDR or physical/logical archive scoped strictly to a Case.
    The original archive is preserved immutably.
    """
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    storage_path_or_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    detected_mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    file_extension: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    status: Mapped[EvidenceStatus] = mapped_column(
        SQLEnum(EvidenceStatus, name="evidence_status_enum", native_enum=False),
        nullable=False,
        default=EvidenceStatus.UPLOADING,
        index=True,
    )
    sha256_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    integrity_status: Mapped[IntegrityStatus] = mapped_column(
        SQLEnum(IntegrityStatus, name="integrity_status_enum", native_enum=False),
        nullable=False,
        default=IntegrityStatus.VALID,
        index=True,
    )
    last_integrity_check_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
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
        back_populates="evidence_items",
    )
    uploader: Mapped["User"] = relationship(
        "User",
        foreign_keys=[uploaded_by],
        lazy="selectin",
    )
    custody_events: Mapped[List["EvidenceCustodyEvent"]] = relationship(
        "EvidenceCustodyEvent",
        back_populates="evidence",
        cascade="all, delete-orphan",
        order_by="EvidenceCustodyEvent.sequence_number",
        lazy="selectin",
    )
    processing_jobs: Mapped[List["ProcessingJob"]] = relationship(
        "backend.app.models.processing_job.ProcessingJob",
        back_populates="evidence",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    artifacts: Mapped[List["RawArtifact"]] = relationship(
        "backend.app.models.raw_artifact.RawArtifact",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )
    canonical_records: Mapped[List["backend.app.models.canonical_evidence.CanonicalEvidence"]] = relationship(
        "backend.app.models.canonical_evidence.CanonicalEvidence",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )


