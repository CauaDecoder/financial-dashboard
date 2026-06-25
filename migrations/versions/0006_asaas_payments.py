"""asaas read only payments

Revision ID: 0006_asaas_payments
Revises: 0005_due_entry_external_id
Create Date: 2026-06-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_asaas_payments"
down_revision = "0005_due_entry_external_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asaas_payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("asaas_id", sa.String(), nullable=False, unique=True),
        sa.Column("customer_name", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("billing_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("value_cents", sa.Integer(), nullable=False),
        sa.Column("net_value_cents", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.String(), nullable=True),
        sa.Column("payment_date", sa.String(), nullable=True),
        sa.Column("external_reference", sa.String(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column(
            "synced_at",
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
    )


def downgrade() -> None:
    op.drop_table("asaas_payments")
