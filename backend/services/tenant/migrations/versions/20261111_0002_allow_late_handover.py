
"""Allow actual handover after planned contract end date."""

from alembic import op

revision = "tenant_v3_002"
down_revision = "tenant_v3_001"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        op.f("ck_contracts_actual_end_valid"),
        "contracts",
        type_="check",
    )

    op.create_check_constraint(
        op.f("ck_contracts_actual_end_valid"),
        "contracts",
        "actual_end_date IS NULL OR actual_end_date >= start_date",
    )


def downgrade():
    # Fails if existing data contains late handovers.
    op.drop_constraint(
        op.f("ck_contracts_actual_end_valid"),
        "contracts",
        type_="check",
    )

    op.create_check_constraint(
        op.f("ck_contracts_actual_end_valid"),
        "contracts",
        "actual_end_date IS NULL OR "
        "(actual_end_date BETWEEN start_date AND end_date)",
    )
