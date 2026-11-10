"""Initial Database Design V3 schema for metering. 2026-11-10.
Migration is self-contained and does not import current ORM models.
Generated and reviewed from V3 SQLAlchemy metadata.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "metering_v3_001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('meters',
    sa.Column('room_id', sa.UUID(), nullable=False),
    sa.Column('meter_code', sa.String(length=80), nullable=False),
    sa.Column('meter_type', sa.String(length=20), nullable=False),
    sa.Column('unit', sa.String(length=10), nullable=False),
    sa.Column('initial_reading', sa.Numeric(precision=16, scale=3), server_default='0', nullable=False),
    sa.Column('status', sa.String(length=16), server_default='ACTIVE', nullable=False),
    sa.Column('last_received_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(meter_type = 'ELECTRICITY' AND unit = 'KWH') OR (meter_type = 'WATER' AND unit = 'M3')", name=op.f('ck_meters_unit_matches_type')),
    sa.CheckConstraint("meter_type IN ('ELECTRICITY', 'WATER')", name=op.f('ck_meters_meter_type_values')),
    sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f('ck_meters_status_values')),
    sa.CheckConstraint('initial_reading >= 0', name=op.f('ck_meters_initial_nonnegative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_meters')),
    sa.UniqueConstraint('meter_code', name=op.f('uq_meters_meter_code')),
    sa.UniqueConstraint('room_id', 'meter_type', name='uq_meters_room_type')
    )
    op.create_table('processed_events',
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.String(length=80), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('event_id', name=op.f('pk_processed_events'))
    )
    op.create_table('meter_cutoffs',
    sa.Column('meter_id', sa.UUID(), nullable=False),
    sa.Column('contract_id', sa.UUID(), nullable=True),
    sa.Column('cutoff_type', sa.String(length=25), nullable=False),
    sa.Column('cutoff_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('reading_value', sa.Numeric(precision=16, scale=3), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('source_reading_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('manual_reason', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('confirmed_by', sa.UUID(), nullable=True),
    sa.Column('supersedes_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("cutoff_type IN ('CONTRACT_START', 'CONTRACT_END', 'MONTHLY')", name=op.f('ck_meter_cutoffs_cutoff_type_values')),
    sa.CheckConstraint("source <> 'MANUAL' OR (manual_reason IS NOT NULL AND confirmed_by IS NOT NULL)", name=op.f('ck_meter_cutoffs_manual_audit_required')),
    sa.CheckConstraint("source IN ('AUTOMATIC', 'MANUAL')", name=op.f('ck_meter_cutoffs_source_values')),
    sa.CheckConstraint("status <> 'CONFIRMED' OR (reading_value IS NOT NULL AND confirmed_at IS NOT NULL)", name=op.f('ck_meter_cutoffs_confirmed_complete')),
    sa.CheckConstraint("status IN ('PENDING', 'CONFIRMED', 'SUPERSEDED')", name=op.f('ck_meter_cutoffs_status_values')),
    sa.CheckConstraint('reading_value IS NULL OR reading_value >= 0', name=op.f('ck_meter_cutoffs_reading_nonnegative')),
    sa.ForeignKeyConstraint(['meter_id'], ['meters.id'], name=op.f('fk_meter_cutoffs_meter_id_meters')),
    sa.ForeignKeyConstraint(['supersedes_id'], ['meter_cutoffs.id'], name=op.f('fk_meter_cutoffs_supersedes_id_meter_cutoffs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_meter_cutoffs'))
    )
    op.create_index('uq_meter_cutoffs_active_scope', 'meter_cutoffs', ['meter_id', 'cutoff_type', 'cutoff_at', 'contract_id'], unique=True, postgresql_where=sa.text("status <> 'SUPERSEDED'"), postgresql_nulls_not_distinct=True)
    op.create_table('meter_readings',
    sa.Column('meter_id', sa.UUID(), nullable=False),
    sa.Column('measured_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('reading_value', sa.Numeric(precision=16, scale=3), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('validation_status', sa.String(length=20), server_default='VALID', nullable=False),
    sa.Column('anomaly_reason', sa.Text(), nullable=True),
    sa.CheckConstraint("validation_status IN ('VALID', 'SUSPECT', 'REJECTED')", name=op.f('ck_meter_readings_validation_values')),
    sa.CheckConstraint('reading_value >= 0', name=op.f('ck_meter_readings_reading_nonnegative')),
    sa.ForeignKeyConstraint(['meter_id'], ['meters.id'], name=op.f('fk_meter_readings_meter_id_meters')),
    sa.PrimaryKeyConstraint('meter_id', 'measured_at', name=op.f('pk_meter_readings'))
    )
    op.create_index('ix_meter_readings_valid_time', 'meter_readings', ['meter_id', 'measured_at'], unique=False, postgresql_where=sa.text("validation_status = 'VALID'"))
    op.create_table('meter_alerts',
    sa.Column('meter_id', sa.UUID(), nullable=False),
    sa.Column('alert_type', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='OPEN', nullable=False),
    sa.Column('related_measured_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('related_cutoff_id', sa.UUID(), nullable=True),
    sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolution_note', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("alert_type IN ('OFFLINE', 'READING_DECREASE', 'LATE_AFTER_CUTOFF', 'CONFLICTING_DUPLICATE')", name=op.f('ck_meter_alerts_alert_type_values')),
    sa.CheckConstraint("status IN ('OPEN', 'RESOLVED')", name=op.f('ck_meter_alerts_status_values')),
    sa.ForeignKeyConstraint(['meter_id'], ['meters.id'], name=op.f('fk_meter_alerts_meter_id_meters')),
    sa.ForeignKeyConstraint(['related_cutoff_id'], ['meter_cutoffs.id'], name=op.f('fk_meter_alerts_related_cutoff_id_meter_cutoffs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_meter_alerts'))
    )
    op.create_index('uq_meter_alerts_open_offline', 'meter_alerts', ['meter_id'], unique=True, postgresql_where=sa.text("status = 'OPEN' AND alert_type = 'OFFLINE'"))
    # ### end Alembic commands ###

def downgrade() -> None:
    op.drop_index('uq_meter_alerts_open_offline', table_name='meter_alerts', postgresql_where=sa.text("status = 'OPEN' AND alert_type = 'OFFLINE'"))
    op.drop_table('meter_alerts')
    op.drop_index('ix_meter_readings_valid_time', table_name='meter_readings', postgresql_where=sa.text("validation_status = 'VALID'"))
    op.drop_table('meter_readings')
    op.drop_index('uq_meter_cutoffs_active_scope', table_name='meter_cutoffs', postgresql_where=sa.text("status <> 'SUPERSEDED'"), postgresql_nulls_not_distinct=True)
    op.drop_table('meter_cutoffs')
    op.drop_table('processed_events')
    op.drop_table('meters')
    # ### end Alembic commands ###
