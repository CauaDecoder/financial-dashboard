from __future__ import annotations

import sqlite3
from datetime import date
from typing import cast

from basilica_financeiro.repositories.audit import record_audit
from basilica_financeiro.repositories.finance import create_payable_receivable_entry

PURCHASE_STATUSES = {
    "requested",
    "quoted",
    "approved",
    "ordered",
    "partially_received",
    "received",
    "checked",
    "stock_entered",
    "payable_generated",
    "closed",
    "canceled",
}

PURCHASE_TRANSITIONS = {
    "requested": {"quoted", "canceled"},
    "quoted": {"approved", "canceled"},
    "approved": {"ordered", "canceled"},
    "ordered": {"partially_received", "received", "canceled"},
    "partially_received": {"received", "canceled"},
    "received": {"checked", "canceled"},
    "checked": {"stock_entered", "canceled"},
    "stock_entered": {"payable_generated", "canceled"},
    "payable_generated": {"closed"},
    "closed": set(),
    "canceled": set(),
}


def create_supplier(
    connection: sqlite3.Connection,
    *,
    name: str,
    actor_user_id: int | None,
    document: str | None = None,
    contact_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    notes: str | None = None,
) -> int:
    name = _required_text(name, "Nome do fornecedor")
    cursor = connection.execute(
        """
        INSERT INTO suppliers (name, document, contact_name, email, phone, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            _blank_to_none(document),
            _blank_to_none(contact_name),
            _blank_to_none(email),
            _blank_to_none(phone),
            _blank_to_none(notes),
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao criar fornecedor")
    supplier_id = cursor.lastrowid
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create",
        entity="supplier",
        entity_id=str(supplier_id),
        before=None,
        after={"name": name, "document": _blank_to_none(document)},
        origin="local",
        result="success",
    )
    return supplier_id


def deactivate_supplier(
    connection: sqlite3.Connection,
    *,
    supplier_id: int,
    actor_user_id: int | None,
) -> None:
    supplier = _supplier(connection, supplier_id)
    if int(supplier["is_active"]) == 0:
        raise ValueError("Fornecedor ja esta inativo")
    connection.execute(
        """
        UPDATE suppliers
        SET is_active = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (supplier_id,),
    )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="deactivate",
        entity="supplier",
        entity_id=str(supplier_id),
        before={"is_active": 1},
        after={"is_active": 0},
        origin="local",
        result="success",
    )


def create_purchase_order(
    connection: sqlite3.Connection,
    *,
    supplier_id: int,
    description: str,
    total_cents: int,
    actor_user_id: int | None,
    expected_date: date | None = None,
    notes: str | None = None,
) -> int:
    _supplier(connection, supplier_id)
    _validate_money(total_cents)
    cursor = connection.execute(
        """
        INSERT INTO purchase_orders (
            supplier_id, description, total_cents, expected_date, notes, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            supplier_id,
            _required_text(description, "Descricao da compra"),
            total_cents,
            None if expected_date is None else expected_date.isoformat(),
            _blank_to_none(notes),
            actor_user_id,
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao criar pedido de compra")
    order_id = cursor.lastrowid
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create",
        entity="purchase_order",
        entity_id=str(order_id),
        before=None,
        after={"supplier_id": supplier_id, "total_cents": total_cents},
        origin="local",
        result="success",
    )
    return order_id


def advance_purchase_order(
    connection: sqlite3.Connection,
    *,
    purchase_order_id: int,
    next_status: str,
    actor_user_id: int | None,
) -> None:
    if next_status not in PURCHASE_STATUSES:
        raise ValueError("Status de compra invalido")
    order = _purchase_order(connection, purchase_order_id)
    current_status = str(order["status"])
    if next_status not in PURCHASE_TRANSITIONS[current_status]:
        raise ValueError("Transicao de compra invalida")
    connection.execute(
        """
        UPDATE purchase_orders
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (next_status, purchase_order_id),
    )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="advance",
        entity="purchase_order",
        entity_id=str(purchase_order_id),
        before={"status": current_status},
        after={"status": next_status},
        origin="local",
        result="success",
    )


def receive_purchase_order(
    connection: sqlite3.Connection,
    *,
    purchase_order_id: int,
    amount_cents: int,
    received_date: date,
    actor_user_id: int | None,
    notes: str | None = None,
) -> int:
    _validate_money(amount_cents)
    order = _purchase_order(connection, purchase_order_id)
    if order["status"] not in {"ordered", "partially_received"}:
        raise ValueError("Compra precisa estar em pedido para receber")
    total_cents = int(order["total_cents"])
    received_cents = int(order["received_cents"])
    if received_cents + amount_cents > total_cents:
        raise ValueError("Recebimento nao pode exceder o total da compra")
    cursor = connection.execute(
        """
        INSERT INTO purchase_receipts (
            purchase_order_id, amount_cents, received_date, notes, created_by
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            purchase_order_id,
            amount_cents,
            received_date.isoformat(),
            _blank_to_none(notes),
            actor_user_id,
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao registrar recebimento")
    new_received = received_cents + amount_cents
    new_status = "received" if new_received == total_cents else "partially_received"
    connection.execute(
        """
        UPDATE purchase_orders
        SET received_cents = ?,
            status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_received, new_status, purchase_order_id),
    )
    receipt_id = cursor.lastrowid
    record_audit(
        connection,
        user_id=actor_user_id,
        action="receive",
        entity="purchase_order",
        entity_id=str(purchase_order_id),
        before={"received_cents": received_cents, "status": order["status"]},
        after={"received_cents": new_received, "status": new_status},
        origin="local",
        result="success",
    )
    return receipt_id


def generate_purchase_payable(
    connection: sqlite3.Connection,
    *,
    purchase_order_id: int,
    due_date: date,
    actor_user_id: int | None,
    account_id: int | None = None,
    category_id: int | None = None,
    cost_center_id: int | None = None,
) -> int:
    order = _purchase_order(connection, purchase_order_id)
    if order["payable_entry_id"] is not None:
        raise ValueError("Compra ja possui conta a pagar gerada")
    if order["status"] != "stock_entered":
        raise ValueError("Compra precisa ter entrada no estoque antes de gerar conta a pagar")
    supplier = _supplier(connection, int(order["supplier_id"]))
    entry_id = create_payable_receivable_entry(
        connection,
        entry_type="payable",
        account_id=account_id,
        category_id=category_id,
        cost_center_id=cost_center_id,
        counterparty=str(supplier["name"]),
        description=f"Compra #{purchase_order_id}: {order['description']}",
        amount_cents=int(order["total_cents"]),
        due_date=due_date,
        actor_user_id=actor_user_id,
        notes="Gerado automaticamente pelo modulo de compras.",
    )
    connection.execute(
        """
        UPDATE purchase_orders
        SET payable_entry_id = ?,
            status = 'payable_generated',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (entry_id, purchase_order_id),
    )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="generate_payable",
        entity="purchase_order",
        entity_id=str(purchase_order_id),
        before={"status": order["status"], "payable_entry_id": None},
        after={"status": "payable_generated", "payable_entry_id": entry_id},
        origin="local",
        result="success",
    )
    return entry_id


def list_suppliers(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT id, name, document, contact_name, email, phone, is_active
        FROM suppliers
        ORDER BY is_active DESC, name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def list_purchase_orders(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT
            po.id,
            po.description,
            po.total_cents,
            po.received_cents,
            po.status,
            po.expected_date,
            po.payable_entry_id,
            s.name AS supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON s.id = po.supplier_id
        ORDER BY po.updated_at DESC, po.id DESC
        LIMIT 200
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _supplier(connection: sqlite3.Connection, supplier_id: int) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT id, name, document, is_active
        FROM suppliers
        WHERE id = ?
        """,
        (supplier_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Fornecedor nao encontrado")
    return cast(sqlite3.Row, row)


def _purchase_order(connection: sqlite3.Connection, purchase_order_id: int) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT id, supplier_id, description, total_cents, received_cents, status,
               payable_entry_id
        FROM purchase_orders
        WHERE id = ?
        """,
        (purchase_order_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Pedido de compra nao encontrado")
    return cast(sqlite3.Row, row)


def _validate_money(amount_cents: int) -> None:
    if not isinstance(amount_cents, int):
        raise TypeError("Valores monetarios precisam ser inteiros em centavos")
    if amount_cents <= 0:
        raise ValueError("Valor monetario precisa ser positivo")


def _required_text(value: str, field_label: str) -> str:
    clean = value.strip()
    if not clean:
        raise ValueError(f"{field_label} precisa ser preenchido")
    return clean


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None
