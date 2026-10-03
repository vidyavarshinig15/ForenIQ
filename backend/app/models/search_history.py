"""
Search History Model — Phase 9

Stores a case-scoped, user-scoped record of each completed forensic search.
This table supports:
  - Search audit trail (who searched what, when)
  - Case-scoped history (investigators can review their own searches)
  - Performance measurement (duration_ms)

IMPORTANT:
  - Only completed search operations are recorded (not keystrokes).
  - Sensitive forensic content is NOT stored here; only query terms and filter
    parameters that the investigator already submitted.
  - Access is case-scoped: an investigator can only see history for cases they
    are authorized to access.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class SearchHistory(Base):
    """
    Case-scoped forensic search history record.
    One row per completed search operation.
    """
    __tablename__ = "search_history"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Raw query string submitted by the investigator (may be empty for filter-only searches)
    query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON-serialized dict of applied filter parameters (artifact_type, date range, etc.)
    filters_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Number of results returned (null if search errored)
    result_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # UTC timestamp of the search execution
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    # Server-side execution time in milliseconds
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
