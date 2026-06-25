"""payables and receivables

Revision ID: 0003_payables_receivables
Revises: 0002_finance_core
Create Date: 2026-06-16
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_payables_receivables"
down_revision = "0002_finance_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payable_receivable_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("financial_accounts.id"),
            nullable=True,
        ),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("cost_center_id", sa.Integer(), sa.ForeignKey("cost_centers.id"), nullable=True),
        sa.Column("counterparty", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("paid_amount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_date", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("paid_at", sa.String(), nullable=True),
        sa.Column(
            "settlement_transaction_id",
            sa.Integer(),
            sa.ForeignKey("financial_transactions.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.String(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.String(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("entry_type IN ('payable', 'receivable')", name="ck_due_entry_type"),
        sa.CheckConstraint("amount_cents > 0", name="ck_due_entry_amount"),
        sa.CheckConstraint("paid_amount_cents >= 0", name="ck_due_entry_paid_amount"),
        sa.CheckConstraint(
            "status IN ('open', 'partial', 'paid', 'overdue', 'canceled')",
            name="ck_due_entry_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("payable_receivable_entries")
