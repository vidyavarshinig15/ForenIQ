"""phase9_search_engine

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-10-02 12:00:00.000000

Phase 9 — Forensic Search Engine: Exact Search, Filtering & Evidence Retrieval.

Creates:
  - search_history table: case-scoped, user-scoped audit of completed searches.
  - ix_search_history_case_user: composite index for case+user history lookup.
  - ix_search_history_case_time:  composite index for chronological case history.

The canonical_evidence table already has all necessary query indexes from
Phase 7 and Phase 8. No additional indexes on that table are required for this phase.
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query", sa.Text, nullable=True),
        sa.Column("filters_json", sa.Text, nullable=True),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=True),
    )

    op.create_index(
        "ix_search_history_case_user",
        "search_history",
        ["case_id", "user_id"],
    )
    op.create_index(
        "ix_search_history_case_time",
        "search_history",
        ["case_id", "executed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_search_history_case_time", table_name="search_history")
    op.drop_index("ix_search_history_case_user", table_name="search_history")
    op.drop_table("search_history")
