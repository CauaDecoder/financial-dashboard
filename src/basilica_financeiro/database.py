from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Literal

SCHEMA_VERSION = 15


class ClosingConnection(sqlite3.Connection):
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return False


def connect(database_path: Path, encryption_key: str | None = None) -> sqlite3.Connection:
    if encryption_key is None:
        import keyring
        import os
        # Usamos APP_SECRET_KEY como chave de criptografia do banco
        encryption_key = keyring.get_password("basilica_financeiro", "APP_SECRET_KEY") or os.getenv("APP_SECRET_KEY")
        
    database_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Tentativa de usar pysqlcipher3 se instalado, caso contrário usa sqlite3 padrão
    try:
        from pysqlcipher3 import dbapi2 as db_module
    except ImportError:
        db_module = sqlite3
        
    connection = db_module.connect(database_path, factory=ClosingConnection)
    
    if encryption_key:
        try:
            # EXCEÇÃO: O driver SQLite nativo não permite bind parameters (?) para PRAGMA.
            # Por isso, usamos interpolação, mas capturamos qualquer erro imediatamente 
            # para evitar que o comando com a chave em texto plano vaze em stack traces.
            connection.execute(f"PRAGMA key = '{encryption_key}'")
        except Exception as e:
            connection.close()
            raise RuntimeError("Falha ao configurar a criptografia do banco de dados (PRAGMA key).") from None
            
    connection.row_factory = db_module.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def migrate(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id TEXT,
            before_json TEXT,
            after_json TEXT,
            origin TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS backup_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS roles (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS permissions (
            code TEXT PRIMARY KEY,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS role_permissions (
            role_name TEXT NOT NULL REFERENCES roles(name),
            permission_code TEXT NOT NULL REFERENCES permissions(code),
            PRIMARY KEY (role_name, permission_code)
        );

        CREATE TABLE IF NOT EXISTS financial_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            account_type TEXT NOT NULL,
            institution TEXT,
            masked_number TEXT,
            opening_balance_cents INTEGER NOT NULL DEFAULT 0,
            current_balance_cents INTEGER NOT NULL DEFAULT 0,
            balance_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            color TEXT,
            notes TEXT,
            integration_name TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('revenue', 'expense')),
            parent_id INTEGER REFERENCES categories(id),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (name, kind, parent_id)
        );

        CREATE TABLE IF NOT EXISTS cost_centers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS financial_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL REFERENCES financial_accounts(id),
            category_id INTEGER REFERENCES categories(id),
            cost_center_id INTEGER REFERENCES cost_centers(id),
            transaction_type TEXT NOT NULL CHECK (
                transaction_type IN ('revenue', 'expense', 'transfer_in', 'transfer_out')
            ),
            status TEXT NOT NULL DEFAULT 'posted',
            description TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            effective_date TEXT NOT NULL,
            due_date TEXT,
            paid_at TEXT,
            transfer_group_id TEXT,
            series_group_id TEXT,
            installment_number INTEGER NOT NULL DEFAULT 1,
            installment_count INTEGER NOT NULL DEFAULT 1,
            recurrence_rule TEXT,
            external_id TEXT,
            origin TEXT NOT NULL DEFAULT 'manual',
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS payable_receivable_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_type TEXT NOT NULL CHECK (entry_type IN ('payable', 'receivable')),
            account_id INTEGER REFERENCES financial_accounts(id),
            category_id INTEGER REFERENCES categories(id),
            cost_center_id INTEGER REFERENCES cost_centers(id),
            counterparty TEXT NOT NULL,
            description TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            paid_amount_cents INTEGER NOT NULL DEFAULT 0 CHECK (paid_amount_cents >= 0),
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK (
                status IN ('open', 'partial', 'paid', 'overdue', 'canceled')
            ),
            paid_at TEXT,
            settlement_transaction_id INTEGER REFERENCES financial_transactions(id),
            series_group_id TEXT,
            installment_number INTEGER NOT NULL DEFAULT 1,
            installment_count INTEGER NOT NULL DEFAULT 1,
            recurrence_rule TEXT,
            external_id TEXT,
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS asaas_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asaas_id TEXT NOT NULL UNIQUE,
            customer_name TEXT,
            description TEXT,
            billing_type TEXT,
            status TEXT NOT NULL,
            value_cents INTEGER NOT NULL,
            net_value_cents INTEGER,
            due_date TEXT,
            payment_date TEXT,
            external_reference TEXT,
            raw_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS asaas_reconciliations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asaas_id TEXT NOT NULL REFERENCES asaas_payments(asaas_id),
            transaction_id INTEGER NOT NULL REFERENCES financial_transactions(id),
            status TEXT NOT NULL DEFAULT 'accepted' CHECK (status IN ('accepted', 'canceled')),
            confidence INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (asaas_id, transaction_id)
        );

        CREATE TABLE IF NOT EXISTS pdv_categories (
            pdv_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

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
        );

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
        );

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
        );

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
        );

        CREATE TABLE IF NOT EXISTS purchase_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            received_date TEXT NOT NULL,
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            mime_type TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

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
        );

        CREATE TABLE IF NOT EXISTS google_sheet_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spreadsheet_id TEXT NOT NULL,
            sheet_name TEXT NOT NULL,
            rows_count INTEGER NOT NULL CHECK (rows_count >= 0),
            imported_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            category_id INTEGER NOT NULL REFERENCES categories(id),
            cost_center_id INTEGER REFERENCES cost_centers(id),
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (year, month, category_id, cost_center_id)
        );

        CREATE TABLE IF NOT EXISTS categorization_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            transaction_type TEXT CHECK (transaction_type IN ('revenue', 'expense')),
            category_id INTEGER NOT NULL REFERENCES categories(id),
            cost_center_id INTEGER REFERENCES cost_centers(id),
            priority INTEGER NOT NULL DEFAULT 100,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (keyword, transaction_type)
        );

        CREATE TABLE IF NOT EXISTS custom_dashboards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            period_preset TEXT NOT NULL CHECK (
                period_preset IN ('current_month', 'last_30_days', 'current_year', 'custom')
            ),
            item_limit INTEGER NOT NULL DEFAULT 8 CHECK (item_limit BETWEEN 1 AND 20),
            alert_days INTEGER NOT NULL DEFAULT 7 CHECK (alert_days BETWEEN 0 AND 90),
            show_revenue_categories INTEGER NOT NULL DEFAULT 1,
            show_expense_categories INTEGER NOT NULL DEFAULT 1,
            show_cost_centers INTEGER NOT NULL DEFAULT 1,
            show_due_alerts INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

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
        );

        CREATE TABLE IF NOT EXISTS sensitive_operation_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL REFERENCES sensitive_operation_requests(id),
            approver_user_id INTEGER NOT NULL REFERENCES users(id),
            decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (request_id, approver_user_id)
        );

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
        );
        """
    )
    _ensure_column(connection, "financial_transactions", "series_group_id", "TEXT")
    _ensure_column(
        connection,
        "financial_transactions",
        "installment_number",
        "INTEGER NOT NULL DEFAULT 1",
    )
    _ensure_column(
        connection,
        "financial_transactions",
        "installment_count",
        "INTEGER NOT NULL DEFAULT 1",
    )
    _ensure_column(connection, "financial_transactions", "recurrence_rule", "TEXT")
    _ensure_column(connection, "payable_receivable_entries", "series_group_id", "TEXT")
    _ensure_column(
        connection,
        "payable_receivable_entries",
        "installment_number",
        "INTEGER NOT NULL DEFAULT 1",
    )
    _ensure_column(
        connection,
        "payable_receivable_entries",
        "installment_count",
        "INTEGER NOT NULL DEFAULT 1",
    )
    _ensure_column(connection, "payable_receivable_entries", "recurrence_rule", "TEXT")
    _ensure_column(connection, "payable_receivable_entries", "external_id", "TEXT")
    _ensure_table(
        connection,
        "asaas_payments",
        """
        CREATE TABLE asaas_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asaas_id TEXT NOT NULL UNIQUE,
            customer_name TEXT,
            description TEXT,
            billing_type TEXT,
            status TEXT NOT NULL,
            value_cents INTEGER NOT NULL,
            net_value_cents INTEGER,
            due_date TEXT,
            payment_date TEXT,
            external_reference TEXT,
            raw_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    _ensure_table(
        connection,
        "asaas_reconciliations",
        """
        CREATE TABLE asaas_reconciliations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asaas_id TEXT NOT NULL REFERENCES asaas_payments(asaas_id),
            transaction_id INTEGER NOT NULL REFERENCES financial_transactions(id),
            status TEXT NOT NULL DEFAULT 'accepted' CHECK (status IN ('accepted', 'canceled')),
            confidence INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (asaas_id, transaction_id)
        )
        """,
    )
    _ensure_table(
        connection,
        "pdv_categories",
        """
        CREATE TABLE pdv_categories (
            pdv_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    _ensure_table(
        connection,
        "pdv_products",
        """
        CREATE TABLE pdv_products (
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
        """,
    )
    _ensure_table(
        connection,
        "pdv_sales",
        """
        CREATE TABLE pdv_sales (
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
        """,
    )
    _ensure_table(
        connection,
        "suppliers",
        """
        CREATE TABLE suppliers (
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
        """,
    )
    _ensure_table(
        connection,
        "purchase_orders",
        """
        CREATE TABLE purchase_orders (
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
        """,
    )
    _ensure_table(
        connection,
        "purchase_receipts",
        """
        CREATE TABLE purchase_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id),
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            received_date TEXT NOT NULL,
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    _ensure_table(
        connection,
        "documents",
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            mime_type TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    _ensure_table(
        connection,
        "document_links",
        """
        CREATE TABLE document_links (
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
        """,
    )
    _ensure_table(
        connection,
        "google_sheet_imports",
        """
        CREATE TABLE google_sheet_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spreadsheet_id TEXT NOT NULL,
            sheet_name TEXT NOT NULL,
            rows_count INTEGER NOT NULL CHECK (rows_count >= 0),
            imported_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    _ensure_table(
        connection,
        "budgets",
        """
        CREATE TABLE budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
            month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
            category_id INTEGER NOT NULL REFERENCES categories(id),
            cost_center_id INTEGER REFERENCES cost_centers(id),
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            notes TEXT,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (year, month, category_id, cost_center_id)
        )
        """,
    )
    _ensure_table(
        connection,
        "categorization_rules",
        """
        CREATE TABLE categorization_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            transaction_type TEXT CHECK (transaction_type IN ('revenue', 'expense')),
            category_id INTEGER NOT NULL REFERENCES categories(id),
            cost_center_id INTEGER REFERENCES cost_centers(id),
            priority INTEGER NOT NULL DEFAULT 100,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (keyword, transaction_type)
        )
        """,
    )
    _ensure_table(
        connection,
        "custom_dashboards",
        """
        CREATE TABLE custom_dashboards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            period_preset TEXT NOT NULL CHECK (
                period_preset IN ('current_month', 'last_30_days', 'current_year', 'custom')
            ),
            item_limit INTEGER NOT NULL DEFAULT 8 CHECK (item_limit BETWEEN 1 AND 20),
            alert_days INTEGER NOT NULL DEFAULT 7 CHECK (alert_days BETWEEN 0 AND 90),
            show_revenue_categories INTEGER NOT NULL DEFAULT 1,
            show_expense_categories INTEGER NOT NULL DEFAULT 1,
            show_cost_centers INTEGER NOT NULL DEFAULT 1,
            show_due_alerts INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    _ensure_table(
        connection,
        "sensitive_operation_requests",
        """
        CREATE TABLE sensitive_operation_requests (
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
        """,
    )
    _ensure_table(
        connection,
        "sensitive_operation_approvals",
        """
        CREATE TABLE sensitive_operation_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL REFERENCES sensitive_operation_requests(id),
            approver_user_id INTEGER NOT NULL REFERENCES users(id),
            decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (request_id, approver_user_id)
        )
        """,
    )
    _ensure_table(
        connection,
        "sensitive_operation_executions",
        """
        CREATE TABLE sensitive_operation_executions (
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
        """,
    )
    _seed_access_control(connection)
    current = connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if current is None:
        connection.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    elif int(current["version"]) < SCHEMA_VERSION:
        connection.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    connection.commit()


def _seed_access_control(connection: sqlite3.Connection) -> None:
    roles = [
        ("administrador", "Acesso total ao sistema"),
        ("gestor_financeiro", "Dashboards, aprovacoes e relatorios completos"),
        ("operador_financeiro", "Lancamentos, conciliacoes e rotinas financeiras"),
        ("auditor", "Consulta de auditoria e relatorios em modo leitura"),
        ("consulta", "Consulta basica sem edicao"),
    ]
    permissions = [
        ("users.manage", "Gerenciar usuarios e perfis"),
        ("audit.read", "Consultar trilha de auditoria"),
        ("backup.create", "Criar backup manual"),
        ("finance.write", "Registrar operacoes financeiras"),
        ("reports.export", "Exportar relatorios"),
        ("sensitive_operations.approve", "Aprovar operacoes sensiveis com dupla aprovacao"),
    ]
    connection.executemany("INSERT OR IGNORE INTO roles (name, description) VALUES (?, ?)", roles)
    connection.executemany(
        "INSERT OR IGNORE INTO permissions (code, description) VALUES (?, ?)",
        permissions,
    )
    role_permissions = [
        *[("administrador", code) for code, _ in permissions],
        ("operador_financeiro", "finance.write"),
        ("operador_financeiro", "backup.create"),
        ("operador_financeiro", "reports.export"),
        ("gestor_financeiro", "finance.write"),
        ("gestor_financeiro", "reports.export"),
        ("gestor_financeiro", "sensitive_operations.approve"),
        ("auditor", "audit.read"),
        ("auditor", "reports.export"),
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO role_permissions (role_name, permission_code)
        VALUES (?, ?)
        """,
        role_permissions,
    )


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    columns = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _ensure_table(connection: sqlite3.Connection, table_name: str, create_sql: str) -> None:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if row is None:
        connection.execute(create_sql)
