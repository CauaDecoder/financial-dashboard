from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from basilica_financeiro.database import connect, migrate
from basilica_financeiro.services.purchases import (
    advance_purchase_order,
    create_purchase_order,
    create_supplier,
    generate_purchase_payable,
    list_purchase_orders,
    list_suppliers,
    receive_purchase_order,
)


def test_purchase_flow_generates_payable_after_stock_entry(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        supplier_id = create_supplier(
            connection,
            name="Fornecedor Liturgico",
            document="00.000.000/0001-00",
            actor_user_id=None,
        )
        order_id = create_purchase_order(
            connection,
            supplier_id=supplier_id,
            description="Velas votivas",
            total_cents=12_000,
            expected_date=date(2026, 6, 25),
            actor_user_id=None,
        )

        advance_purchase_order(
            connection,
            purchase_order_id=order_id,
            next_status="quoted",
            actor_user_id=None,
        )
        advance_purchase_order(
            connection,
            purchase_order_id=order_id,
            next_status="approved",
            actor_user_id=None,
        )
        advance_purchase_order(
            connection,
            purchase_order_id=order_id,
            next_status="ordered",
            actor_user_id=None,
        )
        receive_purchase_order(
            connection,
            purchase_order_id=order_id,
            amount_cents=5_000,
            received_date=date(2026, 6, 20),
            actor_user_id=None,
        )
        receive_purchase_order(
            connection,
            purchase_order_id=order_id,
            amount_cents=7_000,
            received_date=date(2026, 6, 21),
            actor_user_id=None,
        )
        advance_purchase_order(
            connection,
            purchase_order_id=order_id,
            next_status="checked",
            actor_user_id=None,
        )
        advance_purchase_order(
            connection,
            purchase_order_id=order_id,
            next_status="stock_entered",
            actor_user_id=None,
        )
        payable_id = generate_purchase_payable(
            connection,
            purchase_order_id=order_id,
            due_date=date(2026, 7, 5),
            actor_user_id=None,
        )

        orders = list_purchase_orders(connection)
        payable = connection.execute(
            """
            SELECT entry_type, counterparty, amount_cents, status
            FROM payable_receivable_entries
            WHERE id = ?
            """,
            (payable_id,),
        ).fetchone()
        audit_actions = [
            row["action"]
            for row in connection.execute(
                """
                SELECT action FROM audit_log
                WHERE entity IN ('supplier', 'purchase_order')
                ORDER BY id
                """
            ).fetchall()
        ]

        assert list_suppliers(connection)[0]["name"] == "Fornecedor Liturgico"
        assert orders[0]["status"] == "payable_generated"
        assert orders[0]["received_cents"] == 12_000
        assert orders[0]["payable_entry_id"] == payable_id
        assert payable["entry_type"] == "payable"
        assert payable["counterparty"] == "Fornecedor Liturgico"
        assert payable["amount_cents"] == 12_000
        assert payable["status"] == "open"
        assert "generate_payable" in audit_actions


def test_purchase_flow_rejects_invalid_transitions_and_duplicate_payable(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        supplier_id = create_supplier(
            connection,
            name="Fornecedor Administrativo",
            actor_user_id=None,
        )
        order_id = create_purchase_order(
            connection,
            supplier_id=supplier_id,
            description="Materiais de escritorio",
            total_cents=3_000,
            actor_user_id=None,
        )

        with pytest.raises(ValueError, match="Transicao"):
            advance_purchase_order(
                connection,
                purchase_order_id=order_id,
                next_status="stock_entered",
                actor_user_id=None,
            )

        for status in ["quoted", "approved", "ordered"]:
            advance_purchase_order(
                connection,
                purchase_order_id=order_id,
                next_status=status,
                actor_user_id=None,
            )
        with pytest.raises(ValueError, match="exceder"):
            receive_purchase_order(
                connection,
                purchase_order_id=order_id,
                amount_cents=4_000,
                received_date=date(2026, 6, 20),
                actor_user_id=None,
            )
        receive_purchase_order(
            connection,
            purchase_order_id=order_id,
            amount_cents=3_000,
            received_date=date(2026, 6, 20),
            actor_user_id=None,
        )
        advance_purchase_order(
            connection,
            purchase_order_id=order_id,
            next_status="checked",
            actor_user_id=None,
        )
        advance_purchase_order(
            connection,
            purchase_order_id=order_id,
            next_status="stock_entered",
            actor_user_id=None,
        )
        generate_purchase_payable(
            connection,
            purchase_order_id=order_id,
            due_date=date(2026, 7, 5),
            actor_user_id=None,
        )

        with pytest.raises(ValueError, match="ja possui"):
            generate_purchase_payable(
                connection,
                purchase_order_id=order_id,
                due_date=date(2026, 7, 5),
                actor_user_id=None,
            )
