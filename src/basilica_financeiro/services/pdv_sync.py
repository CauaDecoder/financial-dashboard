from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from basilica_financeiro.config import Settings
from basilica_financeiro.repositories.audit import record_audit
from basilica_financeiro.repositories.finance import record_external_revenue

PAID_SALE_STATUSES = {"paid", "completed", "closed", "finalizada", "concluida"}


@dataclass(frozen=True)
class PdvCategory:
    pdv_id: str
    name: str
    raw: dict[str, object]


@dataclass(frozen=True)
class PdvProduct:
    pdv_id: str
    name: str
    category_pdv_id: str | None
    sku: str | None
    price_cents: int
    stock_quantity: float
    stock_value_cents: int
    is_active: bool
    raw: dict[str, object]


@dataclass(frozen=True)
class PdvSale:
    pdv_id: str
    sold_at: str
    total_cents: int
    payment_method: str | None
    status: str
    raw: dict[str, object]


@dataclass(frozen=True)
class PdvSyncResult:
    categories_count: int
    products_count: int
    sales_count: int


@dataclass(frozen=True)
class PdvImportResult:
    imported_count: int
    skipped_count: int


def sync_pdv_snapshots(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    actor_user_id: int | None,
    pdv_database_path: Path | None = None,
) -> PdvSyncResult:
    source_path = pdv_database_path or _pdv_database_path(settings)
    if not source_path.exists():
        raise ValueError("Banco do PDV nao encontrado. Configure PDV_DATABASE_URL no .env")
    categories, products, sales = _read_pdv_database(source_path)
    connection.execute("BEGIN")
    try:
        for category in categories:
            _upsert_pdv_category(connection, category)
        for product in products:
            _upsert_pdv_product(connection, product)
        for sale in sales:
            _upsert_pdv_sale(connection, sale)
    except Exception:
        connection.rollback()
        raise
    record_audit(
        connection,
        user_id=actor_user_id,
        action="sync",
        entity="pdv_snapshot",
        entity_id=None,
        before=None,
        after={
            "categories_count": len(categories),
            "products_count": len(products),
            "sales_count": len(sales),
        },
        origin="pdv",
        result="success",
    )
    return PdvSyncResult(
        categories_count=len(categories),
        products_count=len(products),
        sales_count=len(sales),
    )


def import_pdv_sales_as_revenue(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    actor_user_id: int | None,
    category_id: int | None = None,
    cost_center_id: int | None = None,
) -> PdvImportResult:
    rows = connection.execute(
        """
        SELECT pdv_id, sold_at, total_cents, payment_method, status
        FROM pdv_sales
        WHERE imported_transaction_id IS NULL
        ORDER BY sold_at ASC, pdv_id
        """
    ).fetchall()
    imported_count = 0
    skipped_count = 0
    for row in rows:
        if str(row["status"]).strip().lower() not in PAID_SALE_STATUSES:
            skipped_count += 1
            continue
        external_id = _sale_external_id(str(row["pdv_id"]))
        existing = connection.execute(
            """
            SELECT id FROM financial_transactions
            WHERE external_id = ? AND origin = 'pdv'
            """,
            (external_id,),
        ).fetchone()
        if existing is None:
            transaction_id = record_external_revenue(
                connection,
                account_id=account_id,
                amount_cents=int(row["total_cents"]),
                description=_sale_description(str(row["pdv_id"]), row["payment_method"]),
                effective_date=_date_from_timestamp(str(row["sold_at"])),
                external_id=external_id,
                origin="pdv",
                actor_user_id=actor_user_id,
                category_id=category_id,
                cost_center_id=cost_center_id,
            )
        else:
            transaction_id = int(existing["id"])
            skipped_count += 1
        connection.execute(
            """
            UPDATE pdv_sales
            SET imported_transaction_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE pdv_id = ?
            """,
            (transaction_id, row["pdv_id"]),
        )
        if existing is None:
            imported_count += 1
    record_audit(
        connection,
        user_id=actor_user_id,
        action="import_sales",
        entity="pdv_sale",
        entity_id=None,
        before=None,
        after={"imported_count": imported_count, "skipped_count": skipped_count},
        origin="pdv",
        result="success",
    )
    return PdvImportResult(imported_count=imported_count, skipped_count=skipped_count)


def list_pdv_products(
    connection: sqlite3.Connection,
    *,
    limit: int = 50,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT p.pdv_id, p.sku, p.name, c.name AS category_name,
               p.price_cents, p.stock_quantity, p.stock_value_cents, p.is_active,
               p.synced_at
        FROM pdv_products p
        LEFT JOIN pdv_categories c ON c.pdv_id = p.category_pdv_id
        ORDER BY p.name
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_pdv_sales(connection: sqlite3.Connection, *, limit: int = 50) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT pdv_id, sold_at, total_cents, payment_method, status,
               imported_transaction_id, synced_at
        FROM pdv_sales
        ORDER BY sold_at DESC, pdv_id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_pdv_stock_summary(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT COUNT(*) AS product_count,
               COALESCE(SUM(stock_value_cents), 0) AS stock_value_cents
        FROM pdv_products
        WHERE is_active = 1
        """
    ).fetchone()
    if row is None:
        return {"product_count": 0, "stock_value_cents": 0}
    return {
        "product_count": int(row["product_count"]),
        "stock_value_cents": int(row["stock_value_cents"]),
    }


def _pdv_database_path(settings: Settings) -> Path:
    database_url = settings.pdv_database_url
    if not database_url:
        raise ValueError("PDV_DATABASE_URL precisa estar configurado no .env")
    if not database_url.startswith("sqlite:///"):
        raise ValueError("PDV_DATABASE_URL aceita apenas sqlite:///")
    return settings.paths.resolve_app_path(database_url.removeprefix("sqlite:///"))


def _read_pdv_database(
    source_path: Path,
) -> tuple[list[PdvCategory], list[PdvProduct], list[PdvSale]]:
    source_uri = f"file:{source_path.as_posix()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source:
        source.row_factory = sqlite3.Row
        categories = [_category_from_row(row) for row in _select_all(source, "pdv_categories")]
        products = [_product_from_row(row) for row in _select_all(source, "pdv_products")]
        sales = [_sale_from_row(row) for row in _select_all(source, "pdv_sales")]
    return categories, products, sales


def _select_all(source: sqlite3.Connection, table_name: str) -> list[sqlite3.Row]:
    queries = {
        "pdv_categories": "SELECT * FROM pdv_categories",
        "pdv_products": "SELECT * FROM pdv_products",
        "pdv_sales": "SELECT * FROM pdv_sales",
    }
    query = queries[table_name]
    row = source.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table_name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Contrato PDV invalido: tabela ou view ausente {table_name}")
    return list(source.execute(query).fetchall())


def _category_from_row(row: sqlite3.Row) -> PdvCategory:
    raw = dict(row)
    return PdvCategory(
        pdv_id=str(raw["id"]),
        name=str(raw["name"]),
        raw=raw,
    )


def _product_from_row(row: sqlite3.Row) -> PdvProduct:
    raw = dict(row)
    price_cents = _money_to_cents(raw.get("price_cents", raw.get("price", 0)))
    stock_quantity = float(raw.get("stock_quantity", 0) or 0)
    stock_value = raw.get("stock_value_cents")
    stock_value_cents = (
        _money_to_cents(stock_value)
        if stock_value is not None
        else int((Decimal(str(stock_quantity)) * Decimal(price_cents)).quantize(Decimal("1")))
    )
    return PdvProduct(
        pdv_id=str(raw["id"]),
        name=str(raw["name"]),
        category_pdv_id=None if raw.get("category_id") is None else str(raw["category_id"]),
        sku=None if raw.get("sku") is None else str(raw["sku"]),
        price_cents=price_cents,
        stock_quantity=stock_quantity,
        stock_value_cents=stock_value_cents,
        is_active=bool(raw.get("is_active", 1)),
        raw=raw,
    )


def _sale_from_row(row: sqlite3.Row) -> PdvSale:
    raw = dict(row)
    return PdvSale(
        pdv_id=str(raw["id"]),
        sold_at=str(raw["sold_at"]),
        total_cents=_money_to_cents(raw.get("total_cents", raw.get("total", 0))),
        payment_method=None if raw.get("payment_method") is None else str(raw["payment_method"]),
        status=str(raw.get("status", "paid")),
        raw=raw,
    )


def _upsert_pdv_category(connection: sqlite3.Connection, category: PdvCategory) -> None:
    connection.execute(
        """
        INSERT INTO pdv_categories (pdv_id, name, raw_json)
        VALUES (?, ?, ?)
        ON CONFLICT(pdv_id) DO UPDATE SET
            name = excluded.name,
            raw_json = excluded.raw_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (category.pdv_id, category.name, _raw_json(category.raw)),
    )


def _upsert_pdv_product(connection: sqlite3.Connection, product: PdvProduct) -> None:
    connection.execute(
        """
        INSERT INTO pdv_products (
            pdv_id, category_pdv_id, sku, name, price_cents, stock_quantity,
            stock_value_cents, is_active, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pdv_id) DO UPDATE SET
            category_pdv_id = excluded.category_pdv_id,
            sku = excluded.sku,
            name = excluded.name,
            price_cents = excluded.price_cents,
            stock_quantity = excluded.stock_quantity,
            stock_value_cents = excluded.stock_value_cents,
            is_active = excluded.is_active,
            raw_json = excluded.raw_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            product.pdv_id,
            product.category_pdv_id,
            product.sku,
            product.name,
            product.price_cents,
            product.stock_quantity,
            product.stock_value_cents,
            1 if product.is_active else 0,
            _raw_json(product.raw),
        ),
    )


def _upsert_pdv_sale(connection: sqlite3.Connection, sale: PdvSale) -> None:
    connection.execute(
        """
        INSERT INTO pdv_sales (
            pdv_id, sold_at, total_cents, payment_method, status, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(pdv_id) DO UPDATE SET
            sold_at = excluded.sold_at,
            total_cents = excluded.total_cents,
            payment_method = excluded.payment_method,
            status = excluded.status,
            raw_json = excluded.raw_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            sale.pdv_id,
            sale.sold_at,
            sale.total_cents,
            sale.payment_method,
            sale.status,
            _raw_json(sale.raw),
        ),
    )


def _money_to_cents(value: object) -> int:
    try:
        decimal = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Valor monetario do PDV invalido") from exc
    if decimal < 0:
        raise ValueError("Valor monetario do PDV nao pode ser negativo")
    if decimal == decimal.to_integral_value():
        return int(decimal)
    return int((decimal * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _date_from_timestamp(value: str) -> date:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return date.fromisoformat(value[:10])


def _sale_external_id(pdv_id: str) -> str:
    return f"pdv:sale:{pdv_id}"


def _sale_description(pdv_id: str, payment_method: object) -> str:
    method = "" if payment_method is None else f" - {payment_method}"
    return f"Venda PDV {pdv_id}{method}"


def _raw_json(raw: dict[str, object]) -> str:
    return json.dumps(raw, ensure_ascii=True, sort_keys=True)
