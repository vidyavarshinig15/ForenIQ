import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.models.enums import CaseAccessRole, CaseStatus

if TYPE_CHECKING:
    from backend.app.models.processing_job import ProcessingJob


class Case(Base):
    """
    Forensic Case Entity.
    The primary boundary for forensic evidence, analysis, and access scoping.
    """
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    case_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[CaseStatus] = mapped_column(
        SQLEnum(CaseStatus, name="case_status_enum", native_enum=False),
        nullable=False,
        default=CaseStatus.OPEN,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
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
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    members: Mapped[List["CaseMember"]] = relationship(
        "CaseMember",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    evidence_items: Mapped[List["Evidence"]] = relationship(
        "backend.app.models.evidence.Evidence",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    processing_jobs: Mapped[List["ProcessingJob"]] = relationship(
        "backend.app.models.processing_job.ProcessingJob",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CaseMember(Base):
    """
    Case Membership Entity.
    Explicitly binds an authorized investigator or analyst to a case with a specific role.
    """
    __tablename__ = "case_members"
    __table_args__ = (
        UniqueConstraint("case_id", "user_id", name="uq_case_user_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    access_role: Mapped[CaseAccessRole] = mapped_column(
        SQLEnum(CaseAccessRole, name="case_access_role_enum", native_enum=False),
        nullable=False,
        default=CaseAccessRole.CONTRIBUTOR,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    case: Mapped["Case"] = relationship(
        "Case",
        back_populates="members",
    )
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
