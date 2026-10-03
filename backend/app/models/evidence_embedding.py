"""
Phase 10 — Evidence Embedding Model

Stores vector embedding metadata, content hashes, model versions, and status
for CanonicalEvidence records. The actual high-dimensional vectors are stored
in the case-scoped vector index (FAISS), while this table maintains forensic
traceability, staleness detection, and idempotency.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.models.enums import EmbeddingStatus

if TYPE_CHECKING:
    from backend.app.models.canonical_evidence import CanonicalEvidence
    from backend.app.models.case import Case


class EvidenceEmbedding(Base):
    """
    Forensic vector embedding metadata record.
    Tracks embedding generation lifecycle, model provenance, and content hash
    for staleness verification without duplicating large text payloads.
    """
    __tablename__ = "evidence_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canonical_evidence.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    status: Mapped[EmbeddingStatus] = mapped_column(
        SQLEnum(EmbeddingStatus, name="embedding_status_enum", native_enum=False),
        nullable=False,
        default=EmbeddingStatus.NOT_GENERATED,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
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
    case: Mapped["Case"] = relationship("Case", lazy="selectin")
    canonical_evidence: Mapped["CanonicalEvidence"] = relationship("CanonicalEvidence", lazy="selectin")

    __table_args__ = (
        Index("ix_evidence_embeddings_case_status", "case_id", "status"),
        Index("ix_evidence_embeddings_model_version", "model_name", "model_version"),
    )
