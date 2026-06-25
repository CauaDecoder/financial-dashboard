"""Add PDV snapshot tables.

Revision ID: 0008_pdv_snapshots
Revises: 0007_asaas_reconciliations
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op

revision = "0008_pdv_snapshots"
down_revision = "0007_asaas_reconciliations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pdv_categories (
            pdv_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pdv_products (
            pdv_id TEXT PRIMARY KEY,
            category_pdv_id TEXT REFERENCES pdv_categories(pdv_id),
            sku TEXT,
            name TEXT NOT NULL,
            price_cents INTEGER NOT NULL DEFAULT 0 CHECK (price_cents >= 0),
            stock_quantity REAL NOT NULL DEFAULT 0,
            stock_value_cents INTEGER NOT NULL DEFAULT 0 CHECK (stock_value_cents >= 0),
            is_active INTEGER NOT NULL DEFAULT 1,
            raw_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pdv_sales (
            pdv_id TEXT PRIMARY KEY,
            sold_at TEXT NOT NULL,
            total_cents INTEGER NOT NULL CHECK (total_cents > 0),
            payment_method TEXT,
            status TEXT NOT NULL,
            imported_transaction_id INTEGER REFERENCES financial_transactions(id),
            raw_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade() -> None:
    op.drop_table("pdv_sales")
    op.drop_table("pdv_products")
    op.drop_table("pdv_categories")
