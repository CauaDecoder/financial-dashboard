"""Add sensitive operation execution log.

Revision ID: 0012_sensitive_operation_executions
Revises: 0011_sensitive_operation_approvals
Create Date: 2026-06-19
"""

from __future__ import annotations

from alembic import op

revision = "0012_sensitive_operation_executions"
down_revision = "0011_sensitive_operation_approvals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sensitive_operation_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL UNIQUE REFERENCES sensitive_operation_requests(id),
            status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed')),
            idempotency_key TEXT NOT NULL UNIQUE,
            external_id TEXT,
            response_json TEXT,
            error_message TEXT,
            executed_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sensitive_operation_executions")
