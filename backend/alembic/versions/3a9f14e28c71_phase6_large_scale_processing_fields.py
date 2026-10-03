"""phase6_large_scale_processing_fields

Revision ID: 3a9f14e28c71
Revises: b2c4e293d042
Create Date: 2026-10-01 07:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a9f14e28c71'
down_revision: Union[str, Sequence[str], None] = 'b2c4e293d042'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns('processing_jobs')]
    if 'priority' not in cols:
        with op.batch_alter_table('processing_jobs', schema=None) as batch_op:
            batch_op.add_column(sa.Column('priority', sa.String(length=20), server_default='NORMAL', nullable=False))
            batch_op.add_column(sa.Column('current_stage', sa.String(length=50), server_default='VALIDATING', nullable=True))
            batch_op.add_column(sa.Column('current_file', sa.String(length=255), nullable=True))
            batch_op.add_column(sa.Column('worker_id', sa.String(length=100), nullable=True))
            batch_op.add_column(sa.Column('records_processed', sa.Integer(), server_default='0', nullable=False))
            batch_op.add_column(sa.Column('records_failed', sa.Integer(), server_default='0', nullable=False))
            batch_op.add_column(sa.Column('bytes_processed', sa.BigInteger(), server_default='0', nullable=False))
            batch_op.add_column(sa.Column('bytes_total', sa.BigInteger(), server_default='0', nullable=False))
            batch_op.add_column(sa.Column('processing_rate', sa.Float(), nullable=True))
            batch_op.add_column(sa.Column('estimated_remaining_seconds', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False))
            batch_op.add_column(sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False))
            batch_op.add_column(sa.Column('checkpoint_data', sa.JSON(), nullable=True))
            batch_op.add_column(sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True))
            batch_op.create_index('ix_processing_jobs_priority', ['priority'], unique=False)
            batch_op.create_index('ix_processing_jobs_worker_id', ['worker_id'], unique=False)
            batch_op.create_index('ix_processing_jobs_lease_expires_at', ['lease_expires_at'], unique=False)

    art_cols = [c['name'] for c in insp.get_columns('raw_artifacts')]
    if 'artifact_fingerprint' not in art_cols:
        with op.batch_alter_table('raw_artifacts', schema=None) as batch_op:
            batch_op.add_column(sa.Column('artifact_fingerprint', sa.String(length=64), nullable=True))

        op.execute("UPDATE raw_artifacts SET artifact_fingerprint = hex(id) WHERE artifact_fingerprint IS NULL OR artifact_fingerprint = ''")

        with op.batch_alter_table('raw_artifacts', schema=None) as batch_op:
            batch_op.alter_column('artifact_fingerprint', nullable=False)
            batch_op.create_index('ix_raw_artifacts_fingerprint', ['artifact_fingerprint'], unique=False)
            batch_op.create_index('uq_raw_artifact_identity', ['evidence_id', 'artifact_fingerprint'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('raw_artifacts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_raw_artifact_identity', type_='unique')
        batch_op.drop_index('ix_raw_artifacts_fingerprint')
        batch_op.drop_column('artifact_fingerprint')

    with op.batch_alter_table('processing_jobs', schema=None) as batch_op:
        batch_op.drop_index('ix_processing_jobs_lease_expires_at')
        batch_op.drop_index('ix_processing_jobs_worker_id')
        batch_op.drop_index('ix_processing_jobs_priority')
        batch_op.drop_column('lease_expires_at')
        batch_op.drop_column('last_heartbeat_at')
        batch_op.drop_column('checkpoint_data')
        batch_op.drop_column('max_retries')
        batch_op.drop_column('retry_count')
        batch_op.drop_column('estimated_remaining_seconds')
        batch_op.drop_column('processing_rate')
        batch_op.drop_column('bytes_total')
        batch_op.drop_column('bytes_processed')
        batch_op.drop_column('records_failed')
        batch_op.drop_column('records_processed')
        batch_op.drop_column('worker_id')
        batch_op.drop_column('current_file')
        batch_op.drop_column('current_stage')
        batch_op.drop_column('priority')
