"""Enforce one active cutoff per physical meter at each instant.

Pre-existing conflicting cutoffs must be reconciled manually first.
Never change metering_v3_001, which is already deployed.
"""
from alembic import op, context
import sqlalchemy as sa

revision = "metering_v3_002"
down_revision = "metering_v3_001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    conflicts = None
    if not context.is_offline_mode():
        bind = op.get_bind()
        conflicts = bind.execute(sa.text(
        "SELECT meter_id, cutoff_at, COUNT(*) AS n "
        "FROM meter_cutoffs WHERE status <> 'SUPERSEDED' "
        "GROUP BY meter_id, cutoff_at HAVING COUNT(*) > 1 LIMIT 1"
        )).first()
    if conflicts is not None:
        raise RuntimeError(
            "Conflicting active meter_cutoffs detected at the same meter/time. "
            "Reconcile or supersede duplicates before applying metering_v3_002. "
            f"Example: {conflicts.meter_id} at {conflicts.cutoff_at}"
        )
    op.drop_index("uq_meter_cutoffs_active_scope", table_name="meter_cutoffs")
    op.create_index(
        "uq_meter_cutoffs_active_time", "meter_cutoffs",
        ["meter_id", "cutoff_at"], unique=True,
        postgresql_where=sa.text("status <> 'SUPERSEDED'"),
    )

def downgrade() -> None:
    op.drop_index("uq_meter_cutoffs_active_time", table_name="meter_cutoffs")
    op.create_index(
        "uq_meter_cutoffs_active_scope", "meter_cutoffs",
        ["meter_id", "cutoff_type", "cutoff_at", "contract_id"],
        unique=True, postgresql_where=sa.text("status <> 'SUPERSEDED'"),
        postgresql_nulls_not_distinct=True,
    )
