"""phase10_evidence_embeddings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-02 18:00:00.000000

Phase 10 — Advanced Text Search & Semantic Retrieval Foundation.

Creates:
  - evidence_embeddings table: vector metadata, model provenance, and content hashes.
  - Unique index on canonical_evidence_id for 1:1 mapping.
  - Compound indexes for case_id + status and model_name + model_version.
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_embeddings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_evidence_id", sa.String(36), sa.ForeignKey("canonical_evidence.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("dimension", sa.Integer, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="NOT_GENERATED"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index(
        "ix_evidence_embeddings_canonical_id",
        "evidence_embeddings",
        ["canonical_evidence_id"],
        unique=True,
    )
    op.create_index(
        "ix_evidence_embeddings_case_status",
        "evidence_embeddings",
        ["case_id", "status"],
    )
    op.create_index(
        "ix_evidence_embeddings_content_hash",
        "evidence_embeddings",
        ["content_hash"],
    )
    op.create_index(
        "ix_evidence_embeddings_model_version",
        "evidence_embeddings",
        ["model_name", "model_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_embeddings_model_version", table_name="evidence_embeddings")
    op.drop_index("ix_evidence_embeddings_content_hash", table_name="evidence_embeddings")
    op.drop_index("ix_evidence_embeddings_case_status", table_name="evidence_embeddings")
    op.drop_index("ix_evidence_embeddings_canonical_id", table_name="evidence_embeddings")
    op.drop_table("evidence_embeddings")
