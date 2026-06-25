from pathlib import Path

from basilica_financeiro.database import connect, migrate


def test_migrate_creates_foundation_tables(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {
        "users",
        "sessions",
        "audit_log",
        "backup_history",
        "schema_version",
        "roles",
        "permissions",
        "role_permissions",
        "financial_accounts",
        "categories",
        "cost_centers",
        "financial_transactions",
        "payable_receivable_entries",
        "asaas_payments",
        "asaas_reconciliations",
        "pdv_categories",
        "pdv_products",
        "pdv_sales",
        "suppliers",
        "purchase_orders",
        "purchase_receipts",
        "documents",
        "document_links",
        "google_sheet_imports",
        "budgets",
        "categorization_rules",
        "custom_dashboards",
        "sensitive_operation_requests",
        "sensitive_operation_approvals",
        "sensitive_operation_executions",
    } <= tables


def test_migrate_seeds_foundation_roles(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        roles = {
            row["name"]
            for row in connection.execute("SELECT name FROM roles ORDER BY name").fetchall()
        }
        permissions = {
            row["permission_code"]
            for row in connection.execute(
                "SELECT permission_code FROM role_permissions WHERE role_name = 'administrador'"
            ).fetchall()
        }

    assert {"administrador", "operador_financeiro", "auditor"} <= roles
    assert {
        "users.manage",
        "audit.read",
        "backup.create",
        "sensitive_operations.approve",
    } <= permissions


def test_migrate_creates_due_entry_external_id(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(payable_receivable_entries)")
        }

    assert "external_id" in columns
