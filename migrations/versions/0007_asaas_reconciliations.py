"""asaas reconciliations

Revision ID: 0007_asaas_reconciliations
Revises: 0006_asaas_payments
Create Date: 2026-06-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_asaas_reconciliations"
down_revision = "0006_asaas_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asaas_reconciliations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "asaas_id",
            sa.String(),
            sa.ForeignKey("asaas_payments.asaas_id"),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("financial_transactions.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="accepted"),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.String(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("status IN ('accepted', 'canceled')", name="ck_asaas_recon_status"),
        sa.UniqueConstraint("asaas_id", "transaction_id", name="uq_asaas_recon_pair"),
    )


def downgrade() -> None:
    op.drop_table("asaas_reconciliations")
