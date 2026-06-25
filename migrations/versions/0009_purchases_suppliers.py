"""Add purchase and supplier tables.

Revision ID: 0009_purchases_suppliers
Revises: 0008_pdv_snapshots
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op

revision = "0009_purchases_suppliers"
down_revision = "0008_pdv_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            document TEXT,
            contact_name TEXT,
            email TEXT,
            phone TEXT,
            notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
            description TEXT NOT NULL,
            total_cents INTEGER NOT NULL CHECK (total_cents > 0),
            received_cents INTEGER NOT NULL DEFAULT 0 CHECK (received_cents >= 0),
            status TEXT NOT NULL DEFAULT 'requested' CHECK (
                status IN (
                    'requested', 'quoted', 'approved', 'ordered', 'partially_received',
                    'received', 'checked', 'stock_entered', 'payable_generated',
                    'closed', 'canceled'
                )
            ),
            expected_date TEXT,
            payable_entry_id INTEGER REFERENCES payable_receivable_entries(id),
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            received_date TEXT NOT NULL,
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade() -> None:
    op.drop_table("purchase_receipts")
    op.drop_table("purchase_orders")
    op.drop_table("suppliers")
