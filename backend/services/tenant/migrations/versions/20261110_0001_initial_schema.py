"""Initial Database Design V3 schema for tenant. 2026-11-10.
Migration is self-contained and does not import current ORM models.
Generated and reviewed from V3 SQLAlchemy metadata.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "tenant_v3_001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
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
    op.create_index('ix_tenant_outbox_unpublished', 'outbox_events', ['created_at'], unique=False, postgresql_where=sa.text('published_at IS NULL'))
    op.create_table('tenants',
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('phone', sa.String(length=30), nullable=True),
    sa.Column('email', sa.String(length=254), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tenants'))
    )
    op.create_table('contracts',
    sa.Column('contract_code', sa.String(length=60), nullable=False),
    sa.Column('room_id', sa.UUID(), nullable=False),
    sa.Column('room_code_snapshot', sa.String(length=60), nullable=False),
    sa.Column('representative_tenant_id', sa.UUID(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('actual_end_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=32), server_default='DRAFT', nullable=False),
    sa.Column('deposit_amount', sa.BigInteger(), nullable=True),
    sa.Column('end_reason', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    postgresql.ExcludeConstraint((sa.column('room_id'), '='), (sa.text("daterange(start_date, end_date + 1, '[)')"), '&&'), where=sa.text("status IN ('SCHEDULED','ACTIVE','EXPIRED_PENDING')"), using='gist', name='ex_contracts_room_period'),
    sa.CheckConstraint("status IN ('DRAFT', 'SCHEDULED', 'ACTIVE', 'EXPIRED_PENDING', 'ENDED', 'CANCELLED')", name=op.f('ck_contracts_status_values')),
    sa.CheckConstraint('actual_end_date IS NULL OR (actual_end_date BETWEEN start_date AND end_date)', name=op.f('ck_contracts_actual_end_valid')),
    sa.CheckConstraint('deposit_amount IS NULL OR deposit_amount >= 0', name=op.f('ck_contracts_deposit_nonnegative')),
    sa.CheckConstraint('end_date >= start_date', name=op.f('ck_contracts_date_order')),
    sa.ForeignKeyConstraint(['representative_tenant_id'], ['tenants.id'], name=op.f('fk_contracts_representative_tenant_id_tenants')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_contracts')),
    sa.UniqueConstraint('contract_code', name=op.f('uq_contracts_contract_code'))
    )
    op.create_index('ix_contracts_room_status', 'contracts', ['room_id', 'status'], unique=False)
    op.create_table('contract_events',
    sa.Column('contract_id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("event_type IN ('CREATED', 'CONFIRMED', 'STARTED', 'EXTENDED', 'TERMINATION_RECORDED', 'ENDED', 'CANCELLED')", name=op.f('ck_contract_events_event_types')),
    sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], name=op.f('fk_contract_events_contract_id_contracts')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_contract_events'))
    )
    op.create_index('ix_contract_events_contract_time', 'contract_events', ['contract_id', 'occurred_at'], unique=False)
    op.create_table('contract_terms',
    sa.Column('contract_id', sa.UUID(), nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('effective_to', sa.Date(), nullable=True),
    sa.Column('monthly_rent', sa.BigInteger(), nullable=False),
    sa.Column('electricity_unit_price', sa.BigInteger(), nullable=False),
    sa.Column('water_unit_price', sa.BigInteger(), nullable=False),
    sa.Column('monthly_service_fee', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    postgresql.ExcludeConstraint((sa.column('contract_id'), '='), (sa.text("daterange(effective_from, effective_to, '[)')"), '&&'), using='gist', name='ex_contract_terms_period'),
    sa.CheckConstraint('effective_to IS NULL OR effective_to > effective_from', name=op.f('ck_contract_terms_term_date_order')),
    sa.CheckConstraint('monthly_rent >= 0 AND electricity_unit_price >= 0 AND water_unit_price >= 0 AND monthly_service_fee >= 0', name=op.f('ck_contract_terms_price_nonnegative')),
    sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], name=op.f('fk_contract_terms_contract_id_contracts')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_contract_terms'))
    )
    # ### end Alembic commands ###

def downgrade() -> None:
    op.drop_table('contract_terms')
    op.drop_index('ix_contract_events_contract_time', table_name='contract_events')
    op.drop_table('contract_events')
    op.drop_index('ix_contracts_room_status', table_name='contracts')
    op.drop_table('contracts')
    op.drop_table('tenants')
    op.drop_index('ix_tenant_outbox_unpublished', table_name='outbox_events', postgresql_where=sa.text('published_at IS NULL'))
    op.drop_table('outbox_events')
    # ### end Alembic commands ###
    # Keep btree_gist installed; dropping can break other database objects.
