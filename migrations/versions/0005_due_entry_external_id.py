"""due entry external id

Revision ID: 0005_due_entry_external_id
Revises: 0004_installments_recurrence
Create Date: 2026-06-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_due_entry_external_id"
down_revision = "0004_installments_recurrence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payable_receivable_entries",
        sa.Column("external_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payable_receivable_entries", "external_id")
