"""installments and recurrence metadata

Revision ID: 0004_installments_recurrence
Revises: 0003_payables_receivables
Create Date: 2026-06-16
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_installments_recurrence"
down_revision = "0003_payables_receivables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ["financial_transactions", "payable_receivable_entries"]:
        op.add_column(table_name, sa.Column("series_group_id", sa.String(), nullable=True))
        op.add_column(
            table_name,
            sa.Column("installment_number", sa.Integer(), nullable=False, server_default="1"),
        )
        op.add_column(
            table_name,
            sa.Column("installment_count", sa.Integer(), nullable=False, server_default="1"),
        )
        op.add_column(table_name, sa.Column("recurrence_rule", sa.String(), nullable=True))


def downgrade() -> None:
    for table_name in ["payable_receivable_entries", "financial_transactions"]:
        op.drop_column(table_name, "recurrence_rule")
        op.drop_column(table_name, "installment_count")
        op.drop_column(table_name, "installment_number")
        op.drop_column(table_name, "series_group_id")
