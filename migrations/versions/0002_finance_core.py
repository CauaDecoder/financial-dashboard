"""finance core schema

Revision ID: 0002_finance_core
Revises: 0001_foundation
Create Date: 2026-06-16
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_finance_core"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("account_type", sa.String(), nullable=False),
        sa.Column("institution", sa.String(), nullable=True),
        sa.Column("masked_number", sa.String(), nullable=True),
        sa.Column("opening_balance_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_balance_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("balance_date", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("integration_name", sa.String(), nullable=True),
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
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.String(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("kind IN ('revenue', 'expense')", name="ck_categories_kind"),
        sa.UniqueConstraint("name", "kind", "parent_id", name="uq_categories_name_kind_parent"),
    )
    op.create_table(
        "cost_centers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.String(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "financial_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("financial_accounts.id"),
            nullable=False,
        ),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column(
            "cost_center_id",
            sa.Integer(),
            sa.ForeignKey("cost_centers.id"),
            nullable=True,
        ),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="posted"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.String(), nullable=False),
        sa.Column("due_date", sa.String(), nullable=True),
        sa.Column("paid_at", sa.String(), nullable=True),
        sa.Column("transfer_group_id", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("origin", sa.String(), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.String(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("amount_cents > 0", name="ck_financial_transactions_amount"),
        sa.CheckConstraint(
            "transaction_type IN ('revenue', 'expense', 'transfer_in', 'transfer_out')",
            name="ck_financial_transactions_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("financial_transactions")
    op.drop_table("cost_centers")
    op.drop_table("categories")
    op.drop_table("financial_accounts")
