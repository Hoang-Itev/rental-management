"""Track both logical handover reasons on one physical reading timestamp."""
from alembic import op
import sqlalchemy as sa

revision = "metering_v3_003"
down_revision = "metering_v3_002"
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('meter_cutoff_reasons',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('cutoff_id', sa.UUID(), sa.ForeignKey('meter_cutoffs.id'), nullable=False),
        sa.Column('contract_id', sa.UUID(), nullable=False),
        sa.Column('reason_type', sa.String(25), nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.CheckConstraint("reason_type IN ('CONTRACT_START','CONTRACT_END')",name='ck_meter_cutoff_reasons_reason_type_values'),
        sa.UniqueConstraint('cutoff_id','contract_id','reason_type',name='uq_cutoff_reasons_contract_type'),
    )


def downgrade():
    op.drop_table('meter_cutoff_reasons')
