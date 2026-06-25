"""Add sensitive operation approval workflow.

Revision ID: 0011_sensitive_operation_approvals
Revises: 0010_documents_google_sheets
Create Date: 2026-06-18
"""

from __future__ import annotations

from alembic import op

revision = "0011_sensitive_operation_approvals"
down_revision = "0010_documents_google_sheets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sensitive_operation_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL CHECK (
                operation_type IN (
                    'asaas_create_charge', 'asaas_cancel_charge', 'asaas_refund_payment'
                )
            ),
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (
                status IN ('pending', 'approved', 'rejected', 'canceled', 'executed')
            ),
            amount_cents INTEGER CHECK (amount_cents IS NULL OR amount_cents > 0),
            external_reference TEXT,
            payload_json TEXT NOT NULL,
            requested_by INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sensitive_operation_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL REFERENCES sensitive_operation_requests(id),
            approver_user_id INTEGER NOT NULL REFERENCES users(id),
            decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (request_id, approver_user_id)
        )
        """
    )
    op.execute(
        """
        INSERT OR IGNORE INTO permissions (code, description)
        VALUES (
            'sensitive_operations.approve',
            'Aprovar operacoes sensiveis com dupla aprovacao'
        )
        """
    )
    op.execute(
        """
        INSERT OR IGNORE INTO role_permissions (role_name, permission_code)
        VALUES ('gestor_financeiro', 'sensitive_operations.approve')
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sensitive_operation_approvals")
    op.execute("DROP TABLE IF EXISTS sensitive_operation_requests")
