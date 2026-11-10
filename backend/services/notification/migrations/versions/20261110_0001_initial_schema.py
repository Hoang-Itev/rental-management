"""Initial Database Design V3 schema for notification. 2026-11-10.
Migration is self-contained and does not import current ORM models.
Generated and reviewed from V3 SQLAlchemy metadata.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "notification_v3_001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('email_jobs',
    sa.Column('source_event_id', sa.UUID(), nullable=False),
    sa.Column('email_type', sa.String(length=30), nullable=False),
    sa.Column('invoice_id', sa.UUID(), nullable=True),
    sa.Column('recipient_email', sa.String(length=254), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('template_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='PENDING', nullable=False),
    sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('provider_message_id', sa.String(length=255), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("email_type IN ('INVOICE', 'REMINDER', 'PAYMENT_RECEIPT', 'CONTRACT_EXPIRING')", name=op.f('ck_email_jobs_email_type_values')),
    sa.CheckConstraint("status IN ('PENDING', 'SENDING', 'SENT', 'FAILED', 'SKIPPED')", name=op.f('ck_email_jobs_status_values')),
    sa.CheckConstraint('attempt_count >= 0', name=op.f('ck_email_jobs_attempts_nonnegative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_email_jobs')),
    sa.UniqueConstraint('source_event_id', name=op.f('uq_email_jobs_source_event_id'))
    )
    op.create_index('ix_email_jobs_due', 'email_jobs', ['status', 'next_attempt_at'], unique=False)
    # ### end Alembic commands ###

def downgrade() -> None:
    op.drop_index('ix_email_jobs_due', table_name='email_jobs')
    op.drop_table('email_jobs')
    # ### end Alembic commands ###
