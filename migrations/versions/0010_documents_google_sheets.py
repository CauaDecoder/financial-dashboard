"""Add documents and Google Sheets import tracking.

Revision ID: 0010_documents_google_sheets
Revises: 0009_purchases_suppliers
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op

revision = "0010_documents_google_sheets"
down_revision = "0009_purchases_suppliers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            mime_type TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id),
            entity_type TEXT NOT NULL CHECK (
                entity_type IN (
                    'financial_transaction', 'payable_receivable_entry',
                    'supplier', 'purchase_order'
                )
            ),
            entity_id INTEGER NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (document_id, entity_type, entity_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS google_sheet_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spreadsheet_id TEXT NOT NULL,
            sheet_name TEXT NOT NULL,
            rows_count INTEGER NOT NULL CHECK (rows_count >= 0),
            imported_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade() -> None:
    op.drop_table("google_sheet_imports")
    op.drop_table("document_links")
    op.drop_table("documents")
