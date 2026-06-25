from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from basilica_financeiro.config import Settings
from basilica_financeiro.database import connect, migrate
from basilica_financeiro.paths import AppPaths
from basilica_financeiro.repositories.finance import (
    create_financial_account,
    get_account_balance_cents,
)
from basilica_financeiro.services.pdv_sync import (
    get_pdv_stock_summary,
    import_pdv_sales_as_revenue,
    list_pdv_products,
    list_pdv_sales,
    sync_pdv_snapshots,
)


def test_sync_pdv_requires_configured_database(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        with pytest.raises(ValueError, match="PDV_DATABASE_URL"):
            sync_pdv_snapshots(
                connection,
                settings=_settings(tmp_path, pdv_database_url=None),
                actor_user_id=None,
            )


def test_sync_pdv_snapshots_reads_products_stock_and_sales(tmp_path: Path) -> None:
    pdv_path = tmp_path / "pdv.sqlite3"
    _create_pdv_database(pdv_path)

    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        result = sync_pdv_snapshots(
            connection,
            settings=_settings(tmp_path, pdv_database_url=f"sqlite:///{pdv_path}"),
            actor_user_id=None,
        )

        summary = get_pdv_stock_summary(connection)
        products = list_pdv_products(connection)
        sales = list_pdv_sales(connection)
        audit = connection.execute(
            "SELECT action, entity FROM audit_log WHERE entity = 'pdv_snapshot'"
        ).fetchone()

        assert result.categories_count == 1
        assert result.products_count == 2
        assert result.sales_count == 2
        assert summary == {"product_count": 2, "stock_value_cents": 12_500}
        assert products[0]["category_name"] == "Loja"
        assert sales[0]["pdv_id"] == "sale_2"
        assert audit["action"] == "sync"


def test_import_pdv_sales_as_revenue_is_idempotent(tmp_path: Path) -> None:
    pdv_path = tmp_path / "pdv.sqlite3"
    _create_pdv_database(pdv_path)

    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Caixa loja",
            account_type="cash",
            opening_balance_cents=0,
            balance_date=date(2026, 6, 17),
            actor_user_id=None,
        )
        sync_pdv_snapshots(
            connection,
            settings=_settings(tmp_path, pdv_database_url=f"sqlite:///{pdv_path}"),
            actor_user_id=None,
        )

        first = import_pdv_sales_as_revenue(
            connection,
            account_id=account_id,
            actor_user_id=None,
        )
        second = import_pdv_sales_as_revenue(
            connection,
            account_id=account_id,
            actor_user_id=None,
        )

        transactions = connection.execute(
            """
            SELECT external_id, origin, amount_cents
            FROM financial_transactions
            WHERE origin = 'pdv'
            """
        ).fetchall()
        imported_sales = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM pdv_sales
            WHERE imported_transaction_id IS NOT NULL
            """
        ).fetchone()

        assert first.imported_count == 1
        assert first.skipped_count == 1
        assert second.imported_count == 0
        assert second.skipped_count == 1
        assert get_account_balance_cents(connection, account_id) == 7_500
        assert transactions[0]["external_id"] == "pdv:sale:sale_1"
        assert transactions[0]["origin"] == "pdv"
        assert imported_sales["total"] == 1


def _settings(tmp_path: Path, *, pdv_database_url: str | None) -> Settings:
    return Settings(
        app_env="test",
        secret_key="test-secret-value",
        database_url="sqlite:///data/test.sqlite3",
        session_timeout_minutes=30,
        log_level="INFO",
        backup_encryption_key=None,
        backup_auto_daily=True,
        default_admin_username="admin",
        default_admin_password="SenhaForte123!",
        asaas_env="sandbox",
        asaas_api_key=None,
        asaas_enable_write_operations=False,
        pdv_database_url=pdv_database_url,
        google_client_secret_path=None,
        google_token_path=None,
        paths=AppPaths.from_workspace(tmp_path),
    )


def _create_pdv_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE pdv_categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE pdv_products (
                id TEXT PRIMARY KEY,
                category_id TEXT,
                sku TEXT,
                name TEXT NOT NULL,
                price_cents INTEGER NOT NULL,
                stock_quantity REAL NOT NULL,
                stock_value_cents INTEGER NOT NULL,
                is_active INTEGER NOT NULL
            );
            CREATE TABLE pdv_sales (
                id TEXT PRIMARY KEY,
                sold_at TEXT NOT NULL,
                total_cents INTEGER NOT NULL,
                payment_method TEXT,
                status TEXT NOT NULL
            );
            INSERT INTO pdv_categories (id, name) VALUES ('cat_1', 'Loja');
            INSERT INTO pdv_products (
                id, category_id, sku, name, price_cents, stock_quantity,
                stock_value_cents, is_active
            )
            VALUES
                ('prod_1', 'cat_1', 'VELA', 'Vela votiva', 500, 10, 5000, 1),
                ('prod_2', 'cat_1', 'LIVRO', 'Livro pastoral', 2500, 3, 7500, 1);
            INSERT INTO pdv_sales (id, sold_at, total_cents, payment_method, status)
            VALUES
                ('sale_1', '2026-06-17T10:30:00', 7500, 'PIX', 'paid'),
                ('sale_2', '2026-06-17T11:00:00', 2000, 'DINHEIRO', 'canceled');
            """
        )
