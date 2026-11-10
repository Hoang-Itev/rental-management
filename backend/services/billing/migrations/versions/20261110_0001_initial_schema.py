"""Initial Database Design V3 schema for billing. 2026-11-10.
Migration is self-contained and does not import current ORM models.
Generated and reviewed from V3 SQLAlchemy metadata.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "billing_v3_001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table('billing_runs',
    sa.Column('billing_month', sa.Date(), nullable=False),
    sa.Column('trigger_type', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='RUNNING', nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('issued_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('waiting_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('skipped_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('failed_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("status IN ('RUNNING', 'COMPLETED', 'FAILED')", name=op.f('ck_billing_runs_status_values')),
    sa.CheckConstraint("trigger_type IN ('SCHEDULED', 'MANUAL')", name=op.f('ck_billing_runs_trigger_values')),
    sa.CheckConstraint('issued_count >= 0 AND waiting_count >= 0 AND skipped_count >= 0 AND failed_count >= 0', name=op.f('ck_billing_runs_counts_nonnegative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_billing_runs'))
    )
    op.create_index('ix_billing_runs_month', 'billing_runs', ['billing_month'], unique=False)
    op.create_table('invoices',
    sa.Column('invoice_code', sa.String(length=80), nullable=False),
    sa.Column('contract_id', sa.UUID(), nullable=False),
    sa.Column('room_id', sa.UUID(), nullable=False),
    sa.Column('invoice_type', sa.String(length=16), nullable=False),
    sa.Column('billing_month', sa.Date(), nullable=True),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='DRAFT', nullable=False),
    sa.Column('blocked_reason', sa.Text(), nullable=True),
    sa.Column('revision', sa.Integer(), server_default='1', nullable=False),
    sa.Column('replaces_invoice_id', sa.UUID(), nullable=True),
    sa.Column('void_reason', sa.Text(), nullable=True),
    sa.Column('total_amount', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tenant_name_snapshot', sa.String(length=200), nullable=False),
    sa.Column('tenant_email_snapshot', sa.String(length=254), nullable=True),
    sa.Column('room_code_snapshot', sa.String(length=60), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    postgresql.ExcludeConstraint((sa.column('contract_id'), '='), (sa.text("daterange(period_start, period_end, '[)')"), '&&'), where=sa.text("status <> 'VOID'"), using='gist', name='ex_invoices_contract_period'),
    sa.CheckConstraint("invoice_type <> 'PERIODIC' OR billing_month IS NOT NULL", name=op.f('ck_invoices_periodic_has_month')),
    sa.CheckConstraint("invoice_type IN ('PERIODIC', 'FINAL')", name=op.f('ck_invoices_invoice_type_values')),
    sa.CheckConstraint("status IN ('DRAFT', 'ISSUED', 'PAID', 'VOID')", name=op.f('ck_invoices_status_values')),
    sa.CheckConstraint('period_end > period_start', name=op.f('ck_invoices_period_order')),
    sa.CheckConstraint('revision >= 1', name=op.f('ck_invoices_revision_positive')),
    sa.CheckConstraint('total_amount >= 0', name=op.f('ck_invoices_total_nonnegative')),
    sa.ForeignKeyConstraint(['replaces_invoice_id'], ['invoices.id'], name=op.f('fk_invoices_replaces_invoice_id_invoices')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invoices')),
    sa.UniqueConstraint('invoice_code', name=op.f('uq_invoices_invoice_code'))
    )
    op.create_index('ix_invoices_contract_month', 'invoices', ['contract_id', 'billing_month'], unique=False)
    op.create_index('ix_invoices_status_due', 'invoices', ['status', 'due_date'], unique=False)
    op.create_index('uq_invoices_final_live', 'invoices', ['contract_id'], unique=True, postgresql_where=sa.text("invoice_type = 'FINAL' AND status <> 'VOID'"))
    op.create_index('uq_invoices_month_live', 'invoices', ['contract_id', 'billing_month'], unique=True, postgresql_where=sa.text("invoice_type = 'PERIODIC' AND status <> 'VOID'"))
    op.create_table('outbox_events',
    sa.Column('aggregate_type', sa.String(length=80), nullable=False),
    sa.Column('aggregate_id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.String(length=80), nullable=False),
    sa.Column('event_version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('correlation_id', sa.UUID(), nullable=True),
    sa.Column('dedupe_key', sa.String(length=180), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint('attempts >= 0', name=op.f('ck_outbox_events_attempts_nonnegative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_events')),
    sa.UniqueConstraint('dedupe_key', name=op.f('uq_outbox_events_dedupe_key'))
    )
    op.create_index('ix_billing_outbox_unpublished', 'outbox_events', ['created_at'], unique=False, postgresql_where=sa.text('published_at IS NULL'))
    op.create_table('invoice_access_tokens',
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=255), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_invoice_access_tokens_invoice_id_invoices')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invoice_access_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_invoice_access_tokens_token_hash'))
    )
    op.create_table('invoice_adjustments',
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('amount_delta', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='OPEN', nullable=False),
    sa.Column('resolution_note', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("status IN ('OPEN', 'RESOLVED', 'REJECTED')", name=op.f('ck_invoice_adjustments_status_values')),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_invoice_adjustments_invoice_id_invoices')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invoice_adjustments'))
    )
    op.create_table('invoice_items',
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('item_type', sa.String(length=20), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=16, scale=3), nullable=False),
    sa.Column('unit', sa.String(length=30), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('amount', sa.BigInteger(), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=True),
    sa.Column('period_end', sa.Date(), nullable=True),
    sa.Column('meter_start_value', sa.Numeric(precision=16, scale=3), nullable=True),
    sa.Column('meter_end_value', sa.Numeric(precision=16, scale=3), nullable=True),
    sa.Column('source_term_id', sa.UUID(), nullable=True),
    sa.Column('source_cutoff_start_id', sa.UUID(), nullable=True),
    sa.Column('source_cutoff_end_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("item_type IN ('RENT', 'ELECTRICITY', 'WATER', 'SERVICE')", name=op.f('ck_invoice_items_item_type_values')),
    sa.CheckConstraint('period_start IS NULL OR period_end IS NULL OR period_end > period_start', name=op.f('ck_invoice_items_item_period_valid')),
    sa.CheckConstraint('quantity >= 0 AND unit_price >= 0 AND amount >= 0', name=op.f('ck_invoice_items_price_nonnegative')),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_invoice_items_invoice_id_invoices')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invoice_items'))
    )
    op.create_table('payment_attempts',
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=30), nullable=False),
    sa.Column('order_id', sa.String(length=120), nullable=False),
    sa.Column('request_id', sa.String(length=120), nullable=False),
    sa.Column('provider_transaction_id', sa.String(length=120), nullable=True),
    sa.Column('amount', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='PENDING', nullable=False),
    sa.Column('pay_url', sa.Text(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('result_code', sa.String(length=60), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_reconciled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('PENDING', 'SUCCESS', 'FAILED', 'EXPIRED')", name=op.f('ck_payment_attempts_status_values')),
    sa.CheckConstraint('amount > 0', name=op.f('ck_payment_attempts_amount_positive')),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_payment_attempts_invoice_id_invoices')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_attempts')),
    sa.UniqueConstraint('order_id', name=op.f('uq_payment_attempts_order_id')),
    sa.UniqueConstraint('request_id', name=op.f('uq_payment_attempts_request_id'))
    )
    op.create_index('uq_payment_pending_invoice', 'payment_attempts', ['invoice_id'], unique=True, postgresql_where=sa.text("status = 'PENDING'"))
    op.create_index('uq_payment_success_invoice', 'payment_attempts', ['invoice_id'], unique=True, postgresql_where=sa.text("status = 'SUCCESS'"))
    op.create_table('payment_webhook_receipts',
    sa.Column('payment_attempt_id', sa.UUID(), nullable=True),
    sa.Column('order_id', sa.String(length=120), nullable=False),
    sa.Column('payload_fingerprint', sa.String(length=128), nullable=False),
    sa.Column('signature_valid', sa.Boolean(), nullable=False),
    sa.Column('processing_result', sa.String(length=50), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("processing_result IN ('PROCESSED', 'DUPLICATE', 'INVALID_SIGNATURE', 'UNKNOWN_ORDER', 'AMOUNT_MISMATCH', 'RECONCILIATION_REQUIRED')", name=op.f('ck_payment_webhook_receipts_result_values')),
    sa.ForeignKeyConstraint(['payment_attempt_id'], ['payment_attempts.id'], name=op.f('fk_payment_webhook_receipts_payment_attempt_id_payment_attempts')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_webhook_receipts'))
    )
    op.create_index('ix_payment_webhook_order', 'payment_webhook_receipts', ['order_id'], unique=False)
    # ### end Alembic commands ###

def downgrade() -> None:
    op.drop_index('ix_payment_webhook_order', table_name='payment_webhook_receipts')
    op.drop_table('payment_webhook_receipts')
    op.drop_index('uq_payment_success_invoice', table_name='payment_attempts', postgresql_where=sa.text("status = 'SUCCESS'"))
    op.drop_index('uq_payment_pending_invoice', table_name='payment_attempts', postgresql_where=sa.text("status = 'PENDING'"))
    op.drop_table('payment_attempts')
    op.drop_table('invoice_items')
    op.drop_table('invoice_adjustments')
    op.drop_table('invoice_access_tokens')
    op.drop_index('ix_billing_outbox_unpublished', table_name='outbox_events', postgresql_where=sa.text('published_at IS NULL'))
    op.drop_table('outbox_events')
    op.drop_index('uq_invoices_month_live', table_name='invoices', postgresql_where=sa.text("invoice_type = 'PERIODIC' AND status <> 'VOID'"))
    op.drop_index('uq_invoices_final_live', table_name='invoices', postgresql_where=sa.text("invoice_type = 'FINAL' AND status <> 'VOID'"))
    op.drop_index('ix_invoices_status_due', table_name='invoices')
    op.drop_index('ix_invoices_contract_month', table_name='invoices')
    op.drop_table('invoices')
    op.drop_index('ix_billing_runs_month', table_name='billing_runs')
    op.drop_table('billing_runs')
    # ### end Alembic commands ###
    # Keep btree_gist installed; dropping can break other database objects.
