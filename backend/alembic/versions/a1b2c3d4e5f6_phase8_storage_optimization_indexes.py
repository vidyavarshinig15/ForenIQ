"""phase8_storage_optimization_indexes

Revision ID: a1b2c3d4e5f6
Revises: 9c2f1e4a5d8b
Create Date: 2026-10-01 20:00:00.000000

Phase 8 — Structured Database & Document Storage Optimization.

This migration adds targeted composite indexes that support the new query patterns
introduced in Phase 8:

  * Case-scoped canonical timeline queries (case_id, event_timestamp DESC)
  * Device-scoped forensic queries    (case_id, device_id, event_timestamp)
  * Quality-filtered case queries     (case_id, data_quality_status, artifact_type)
  * Audit log composite for case+time (case_id, timestamp)

These are SAFE additive migrations — no existing indexes, constraints, or data
are removed or modified. Downgrade drops only the newly created indexes.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9c2f1e4a5d8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # ------------------------------------------------------------------ #
    # canonical_evidence  — Phase 8 query-optimizing composite indexes    #
    # ------------------------------------------------------------------ #
    if "canonical_evidence" in insp.get_table_names():
        existing_indexes = {
            idx["name"] for idx in insp.get_indexes("canonical_evidence")
        }

        # Case-wide timeline scan: used by list_by_case cursor pagination
        # SELECT … WHERE case_id=? ORDER BY event_timestamp DESC NULLS LAST, id DESC
        if "ix_canonical_evidence_case_time_id" not in existing_indexes:
            op.create_index(
                "ix_canonical_evidence_case_time_id",
                "canonical_evidence",
                ["case_id", "event_timestamp", "id"],
                unique=False,
            )

        # Device-scoped timeline: case_id + device_id + event_timestamp
        if "ix_canonical_evidence_case_device_time" not in existing_indexes:
            op.create_index(
                "ix_canonical_evidence_case_device_time",
                "canonical_evidence",
                ["case_id", "device_id", "event_timestamp"],
                unique=False,
            )

        # Quality-filtered browsing: case_id + data_quality_status + artifact_type
        if "ix_canonical_evidence_case_quality_type" not in existing_indexes:
            op.create_index(
                "ix_canonical_evidence_case_quality_type",
                "canonical_evidence",
                ["case_id", "data_quality_status", "artifact_type"],
                unique=False,
            )

        # Evidence-scoped cursor pagination: evidence_id + event_timestamp + id
        if "ix_canonical_evidence_evidence_time_id" not in existing_indexes:
            op.create_index(
                "ix_canonical_evidence_evidence_time_id",
                "canonical_evidence",
                ["evidence_id", "event_timestamp", "id"],
                unique=False,
            )

    # ------------------------------------------------------------------ #
    # audit_logs — composite for case-scoped audit retrieval with time    #
    # ------------------------------------------------------------------ #
    if "audit_logs" in insp.get_table_names():
        existing_audit = {idx["name"] for idx in insp.get_indexes("audit_logs")}

        if "ix_audit_logs_case_timestamp" not in existing_audit:
            op.create_index(
                "ix_audit_logs_case_timestamp",
                "audit_logs",
                ["case_id", "timestamp"],
                unique=False,
            )

        # User activity timeline
        if "ix_audit_logs_user_timestamp" not in existing_audit:
            op.create_index(
                "ix_audit_logs_user_timestamp",
                "audit_logs",
                ["user_id", "timestamp"],
                unique=False,
            )

    # ------------------------------------------------------------------ #
    # processing_jobs — lease-expiry + status for worker polling          #
    # ------------------------------------------------------------------ #
    if "processing_jobs" in insp.get_table_names():
        existing_jobs = {idx["name"] for idx in insp.get_indexes("processing_jobs")}

        # Worker dispatch: find QUEUED jobs ordered by priority + created_at
        if "ix_processing_jobs_status_priority_created" not in existing_jobs:
            op.create_index(
                "ix_processing_jobs_status_priority_created",
                "processing_jobs",
                ["status", "priority", "created_at"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "canonical_evidence" in insp.get_table_names():
        existing = {idx["name"] for idx in insp.get_indexes("canonical_evidence")}
        for idx_name in [
            "ix_canonical_evidence_case_time_id",
            "ix_canonical_evidence_case_device_time",
            "ix_canonical_evidence_case_quality_type",
            "ix_canonical_evidence_evidence_time_id",
        ]:
            if idx_name in existing:
                op.drop_index(idx_name, table_name="canonical_evidence")

    if "audit_logs" in insp.get_table_names():
        existing_audit = {idx["name"] for idx in insp.get_indexes("audit_logs")}
        for idx_name in ["ix_audit_logs_case_timestamp", "ix_audit_logs_user_timestamp"]:
            if idx_name in existing_audit:
                op.drop_index(idx_name, table_name="audit_logs")

    if "processing_jobs" in insp.get_table_names():
        existing_jobs = {idx["name"] for idx in insp.get_indexes("processing_jobs")}
        if "ix_processing_jobs_status_priority_created" in existing_jobs:
            op.drop_index(
                "ix_processing_jobs_status_priority_created",
                table_name="processing_jobs",
            )
