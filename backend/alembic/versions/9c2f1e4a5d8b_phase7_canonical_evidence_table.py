"""phase7_canonical_evidence_table

Revision ID: 9c2f1e4a5d8b
Revises: 3a9f14e28c71
Create Date: 2026-10-01 13:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c2f1e4a5d8b'
down_revision: Union[str, Sequence[str], None] = '3a9f14e28c71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()
    if 'canonical_evidence' not in tables:
        op.create_table(
            'canonical_evidence',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('case_id', sa.UUID(), nullable=False),
            sa.Column('evidence_id', sa.UUID(), nullable=False),
            sa.Column('raw_artifact_id', sa.UUID(), nullable=False),
            sa.Column('processing_job_id', sa.UUID(), nullable=True),
            sa.Column('artifact_type', sa.String(length=50), nullable=False),
            sa.Column('canonical_fingerprint', sa.String(length=64), nullable=False),
            sa.Column('source_file', sa.String(length=255), nullable=False),
            sa.Column('source_path', sa.Text(), nullable=False),
            sa.Column('record_identifier', sa.String(length=255), nullable=False),
            sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=True),
            sa.Column('timestamp_precision', sa.String(length=20), server_default='UNKNOWN', nullable=False),
            sa.Column('timestamp_status', sa.String(length=20), server_default='UNKNOWN', nullable=False),
            sa.Column('original_timestamp', sa.String(length=255), nullable=True),
            sa.Column('original_timezone', sa.String(length=50), nullable=True),
            sa.Column('device_id', sa.String(length=100), nullable=True),
            sa.Column('application', sa.String(length=100), nullable=True),
            sa.Column('original_application', sa.String(length=100), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('entities', sa.JSON(), server_default='[]', nullable=False),
            sa.Column('metadata', sa.JSON(), server_default='{}', nullable=False),
            sa.Column('data_quality_status', sa.String(length=20), server_default='VALID', nullable=False),
            sa.Column('validation_warnings', sa.JSON(), server_default='[]', nullable=False),
            sa.Column('parser_version', sa.String(length=32), server_default='1.0.0', nullable=False),
            sa.Column('normalizer_version', sa.String(length=32), server_default='1.0.0', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['raw_artifact_id'], ['raw_artifacts.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['processing_job_id'], ['processing_jobs.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('evidence_id', 'canonical_fingerprint', name='uq_canonical_evidence_identity'),
            sa.UniqueConstraint('raw_artifact_id', name='uq_canonical_evidence_raw_artifact'),
        )
        op.create_index('ix_canonical_evidence_case_id', 'canonical_evidence', ['case_id'], unique=False)
        op.create_index('ix_canonical_evidence_evidence_id', 'canonical_evidence', ['evidence_id'], unique=False)
        op.create_index('ix_canonical_evidence_raw_artifact_id', 'canonical_evidence', ['raw_artifact_id'], unique=False)
        op.create_index('ix_canonical_evidence_processing_job_id', 'canonical_evidence', ['processing_job_id'], unique=False)
        op.create_index('ix_canonical_evidence_artifact_type', 'canonical_evidence', ['artifact_type'], unique=False)
        op.create_index('ix_canonical_evidence_canonical_fingerprint', 'canonical_evidence', ['canonical_fingerprint'], unique=False)
        op.create_index('ix_canonical_evidence_source_file', 'canonical_evidence', ['source_file'], unique=False)
        op.create_index('ix_canonical_evidence_record_identifier', 'canonical_evidence', ['record_identifier'], unique=False)
        op.create_index('ix_canonical_evidence_event_timestamp', 'canonical_evidence', ['event_timestamp'], unique=False)
        op.create_index('ix_canonical_evidence_device_id', 'canonical_evidence', ['device_id'], unique=False)
        op.create_index('ix_canonical_evidence_application', 'canonical_evidence', ['application'], unique=False)
        op.create_index('ix_canonical_evidence_data_quality_status', 'canonical_evidence', ['data_quality_status'], unique=False)
        op.create_index('ix_canonical_evidence_created_at', 'canonical_evidence', ['created_at'], unique=False)
        op.create_index(
            'ix_canonical_evidence_case_type_time',
            'canonical_evidence',
            ['case_id', 'artifact_type', 'event_timestamp'],
            unique=False,
        )
        op.create_index(
            'ix_canonical_evidence_evidence_type',
            'canonical_evidence',
            ['evidence_id', 'artifact_type'],
            unique=False,
        )
        op.create_index(
            'ix_canonical_evidence_app_time',
            'canonical_evidence',
            ['application', 'event_timestamp'],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()
    if 'canonical_evidence' in tables:
        op.drop_table('canonical_evidence')
