"""Add attachment_url to contracts for paper contract upload."""
from alembic import op
import sqlalchemy as sa

revision = "tenant_v3_003"
down_revision = "tenant_v3_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("attachment_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("contracts", "attachment_url")