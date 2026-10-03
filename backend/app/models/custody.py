import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.models.enums import CustodyEventType

if TYPE_CHECKING:
    from backend.app.models.case import Case
    from backend.app.models.evidence import Evidence
    from backend.app.models.user import User


class EvidenceCustodyEvent(Base):
    """
    Append-Only Tamper-Evident Chain of Custody Record.
    Tracks chronological, verifiable lifecycle events for ingested evidence items.
    Each event links cryptographically to the previous event hash.
    """
    __tablename__ = "evidence_custody_events"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[CustodyEventType] = mapped_column(
        SQLEnum(CustodyEventType, name="custody_event_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    previous_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("evidence_custody_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    previous_event_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    event_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    metadata_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    evidence: Mapped["Evidence"] = relationship(
        "Evidence",
        back_populates="custody_events",
    )
    case: Mapped["Case"] = relationship(
        "Case",
    )
    actor: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[actor_user_id],
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_custody_evidence_sequence", "evidence_id", "sequence_number"),
    )
