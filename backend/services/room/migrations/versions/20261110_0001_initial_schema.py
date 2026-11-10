"""Initial Database Design V3 schema for room. 2026-11-10.
Migration is self-contained and does not import current ORM models.
Generated and reviewed from V3 SQLAlchemy metadata.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "room_v3_001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
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
    op.create_index('ix_room_outbox_unpublished', 'outbox_events', ['created_at'], unique=False, postgresql_where=sa.text('published_at IS NULL'))
    op.create_table('processed_events',
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.String(length=80), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('event_id', name=op.f('pk_processed_events'))
    )
    op.create_table('properties',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('address', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='ACTIVE', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f('ck_properties_status_values')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_properties'))
    )
    op.create_table('buildings',
    sa.Column('property_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='ACTIVE', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f('ck_buildings_status_values')),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], name=op.f('fk_buildings_property_id_properties')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_buildings')),
    sa.UniqueConstraint('property_id', 'name', name='uq_buildings_property_name')
    )
    op.create_table('floors',
    sa.Column('building_id', sa.UUID(), nullable=False),
    sa.Column('floor_number', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='ACTIVE', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f('ck_floors_status_values')),
    sa.ForeignKeyConstraint(['building_id'], ['buildings.id'], name=op.f('fk_floors_building_id_buildings')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_floors')),
    sa.UniqueConstraint('building_id', 'floor_number', name='uq_floors_building_number')
    )
    op.create_table('rooms',
    sa.Column('property_id', sa.UUID(), nullable=False),
    sa.Column('floor_id', sa.UUID(), nullable=False),
    sa.Column('room_code', sa.String(length=60), nullable=False),
    sa.Column('area_m2', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('listed_rent', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='ACTIVE', nullable=False),
    sa.Column('occupancy_contract_id', sa.UUID(), nullable=True),
    sa.Column('occupancy_updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=op.f('ck_rooms_status_values')),
    sa.CheckConstraint('area_m2 > 0', name=op.f('ck_rooms_area_positive')),
    sa.CheckConstraint('listed_rent >= 0', name=op.f('ck_rooms_rent_nonnegative')),
    sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], name=op.f('fk_rooms_floor_id_floors')),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], name=op.f('fk_rooms_property_id_properties')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rooms')),
    sa.UniqueConstraint('property_id', 'room_code', name='uq_rooms_property_code')
    )
    op.create_index('ix_rooms_occupancy_contract_id', 'rooms', ['occupancy_contract_id'], unique=False)
    # ### end Alembic commands ###

def downgrade() -> None:
    op.drop_index('ix_rooms_occupancy_contract_id', table_name='rooms')
    op.drop_table('rooms')
    op.drop_table('floors')
    op.drop_table('buildings')
    op.drop_table('properties')
    op.drop_table('processed_events')
    op.drop_index('ix_room_outbox_unpublished', table_name='outbox_events', postgresql_where=sa.text('published_at IS NULL'))
    op.drop_table('outbox_events')
    # ### end Alembic commands ###
