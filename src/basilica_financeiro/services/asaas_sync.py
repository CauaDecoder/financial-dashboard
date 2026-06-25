from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date

from basilica_financeiro.config import Settings
from basilica_financeiro.repositories.audit import record_audit
from basilica_financeiro.services.asaas import AsaasClient, AsaasPayment

RECEIVED_STATUSES = {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}


@dataclass(frozen=True)
class AsaasSyncResult:
    fetched_count: int
    stored_count: int


def sync_asaas_payments(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    actor_user_id: int | None,
    due_date_start: date | None = None,
    due_date_end: date | None = None,
    client: AsaasClient | None = None,
) -> AsaasSyncResult:
    api_key = settings.asaas_api_key
    if not api_key:
        raise ValueError("ASAAS_API_KEY precisa estar configurada no .env")
    asaas_client = client or AsaasClient(api_key=api_key, environment=settings.asaas_env)
    payments = asaas_client.list_payments(
        due_date_start=due_date_start,
        due_date_end=due_date_end,
    )
    stored_count = 0
    connection.execute("BEGIN")
    try:
        for payment in payments:
            _upsert_asaas_payment(connection, payment)
            stored_count += 1
    except Exception:
        connection.rollback()
        raise
    record_audit(
        connection,
        user_id=actor_user_id,
        action="sync",
        entity="asaas_payment",
        entity_id=None,
        before=None,
        after={
            "fetched_count": len(payments),
            "stored_count": stored_count,
            "environment": settings.asaas_env,
        },
        origin="asaas",
        result="success",
    )
    return AsaasSyncResult(fetched_count=len(payments), stored_count=stored_count)


def list_asaas_payments(
    connection: sqlite3.Connection,
    *,
    limit: int = 50,
    status: str | None = None,
    search: str | None = None,
) -> list[dict[str, object]]:
    pattern = None if search is None else f"%{search}%"
    rows = connection.execute(
        """
        SELECT asaas_id, customer_name, description, billing_type, status,
               value_cents, net_value_cents, due_date, payment_date,
               external_reference, synced_at
        FROM asaas_payments
        WHERE (? IS NULL OR status = ?)
          AND (
              ? IS NULL
              OR customer_name LIKE ?
              OR description LIKE ?
              OR asaas_id LIKE ?
          )
        ORDER BY COALESCE(payment_date, due_date, synced_at) DESC, id DESC
        LIMIT ?
        """,
        (status, status, pattern, pattern, pattern, pattern, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def suggest_asaas_matches(
    connection: sqlite3.Connection,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, object]]:
    filters = [
        "p.status IN ('RECEIVED', 'CONFIRMED', 'RECEIVED_IN_CASH')",
        "r.id IS NULL",
    ]
    params: list[object] = []
    if start_date is not None:
        filters.append("p.payment_date >= ?")
        params.append(start_date.isoformat())
    if end_date is not None:
        filters.append("p.payment_date <= ?")
        params.append(end_date.isoformat())
    where_clause = " AND ".join(filters)
    query = (
        """
        SELECT
            p.asaas_id,
            p.customer_name,
            p.description AS asaas_description,
            p.value_cents,
            p.payment_date,
            t.id AS transaction_id,
            t.description AS transaction_description,
            t.effective_date
        FROM asaas_payments p
        JOIN financial_transactions t
          ON t.transaction_type = 'revenue'
         AND t.status = 'posted'
         AND t.amount_cents = p.value_cents
         AND t.effective_date = p.payment_date
        LEFT JOIN asaas_reconciliations r
          ON r.asaas_id = p.asaas_id
         AND r.transaction_id = t.id
         AND r.status = 'accepted'
        WHERE
        """
        + where_clause
        + """
        ORDER BY p.payment_date DESC, p.asaas_id
        """
    )
    rows = connection.execute(
        query,
        params,
    ).fetchall()
    return [
        {
            **dict(row),
            "confidence": 100,
            "reason": "Mesmo valor e mesma data de recebimento",
        }
        for row in rows
    ]


def list_asaas_reconciliations(
    connection: sqlite3.Connection,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, object]]:
    filters = ["r.status = 'accepted'"]
    params: list[object] = []
    if start_date is not None:
        filters.append("p.payment_date >= ?")
        params.append(start_date.isoformat())
    if end_date is not None:
        filters.append("p.payment_date <= ?")
        params.append(end_date.isoformat())
    where_clause = " AND ".join(filters)
    query = (
        """
        SELECT
            r.id,
            r.asaas_id,
            r.transaction_id,
            r.confidence,
            r.reason,
            r.created_at,
            p.customer_name,
            p.value_cents,
            p.payment_date,
            t.description AS transaction_description
        FROM asaas_reconciliations r
        JOIN asaas_payments p ON p.asaas_id = r.asaas_id
        JOIN financial_transactions t ON t.id = r.transaction_id
        WHERE
        """
        + where_clause
        + """
        ORDER BY r.created_at DESC, r.id DESC
        """
    )
    rows = connection.execute(
        query,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def accept_asaas_match(
    connection: sqlite3.Connection,
    *,
    asaas_id: str,
    transaction_id: int,
    actor_user_id: int | None,
    confidence: int,
    reason: str,
) -> int:
    payment, transaction = _matching_payment_and_transaction(
        connection,
        asaas_id=asaas_id,
        transaction_id=transaction_id,
    )
    if payment["status"] not in RECEIVED_STATUSES:
        raise ValueError("Cobranca Asaas ainda nao esta recebida")
    if int(payment["value_cents"]) != int(transaction["amount_cents"]):
        raise ValueError("Conciliacao exige mesmo valor")
    if payment["payment_date"] != transaction["effective_date"]:
        raise ValueError("Conciliacao exige mesma data")
    connection.execute(
        """
        INSERT INTO asaas_reconciliations (
            asaas_id, transaction_id, confidence, reason, created_by
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(asaas_id, transaction_id) DO UPDATE SET
            status = 'accepted',
            confidence = excluded.confidence,
            reason = excluded.reason,
            created_by = excluded.created_by,
            created_at = CURRENT_TIMESTAMP
        """,
        (asaas_id, transaction_id, confidence, reason, actor_user_id),
    )
    reconciliation_id = _reconciliation_id(
        connection,
        asaas_id=asaas_id,
        transaction_id=transaction_id,
    )
    if reconciliation_id is None:
        raise RuntimeError("Falha ao registrar conciliacao Asaas")
    record_audit(
        connection,
        user_id=actor_user_id,
        action="accept_match",
        entity="asaas_reconciliation",
        entity_id=str(reconciliation_id),
        before=None,
        after={
            "asaas_id": asaas_id,
            "transaction_id": transaction_id,
            "confidence": confidence,
        },
        origin="asaas",
        result="success",
    )
    return reconciliation_id


def cancel_asaas_reconciliation(
    connection: sqlite3.Connection,
    *,
    reconciliation_id: int,
    actor_user_id: int | None,
) -> None:
    row = connection.execute(
        """
        SELECT id, asaas_id, transaction_id, status
        FROM asaas_reconciliations
        WHERE id = ?
        """,
        (reconciliation_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Conciliacao Asaas nao encontrada")
    if row["status"] != "accepted":
        raise ValueError("Conciliacao Asaas ja esta cancelada")
    connection.execute(
        """
        UPDATE asaas_reconciliations
        SET status = 'canceled'
        WHERE id = ?
        """,
        (reconciliation_id,),
    )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="cancel_match",
        entity="asaas_reconciliation",
        entity_id=str(reconciliation_id),
        before={
            "status": "accepted",
            "asaas_id": row["asaas_id"],
            "transaction_id": row["transaction_id"],
        },
        after={"status": "canceled"},
        origin="asaas",
        result="success",
    )


def _upsert_asaas_payment(connection: sqlite3.Connection, payment: AsaasPayment) -> None:
    connection.execute(
        """
        INSERT INTO asaas_payments (
            asaas_id, customer_name, description, billing_type, status,
            value_cents, net_value_cents, due_date, payment_date,
            external_reference, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asaas_id) DO UPDATE SET
            customer_name = excluded.customer_name,
            description = excluded.description,
            billing_type = excluded.billing_type,
            status = excluded.status,
            value_cents = excluded.value_cents,
            net_value_cents = excluded.net_value_cents,
            due_date = excluded.due_date,
            payment_date = excluded.payment_date,
            external_reference = excluded.external_reference,
            raw_json = excluded.raw_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            payment.asaas_id,
            payment.customer_name,
            payment.description,
            payment.billing_type,
            payment.status,
            payment.value_cents,
            payment.net_value_cents,
            None if payment.due_date is None else payment.due_date.isoformat(),
            None if payment.payment_date is None else payment.payment_date.isoformat(),
            payment.external_reference,
            json.dumps(payment.raw, ensure_ascii=True, sort_keys=True),
        ),
    )


def _matching_payment_and_transaction(
    connection: sqlite3.Connection,
    *,
    asaas_id: str,
    transaction_id: int,
) -> tuple[sqlite3.Row, sqlite3.Row]:
    payment = connection.execute(
        """
        SELECT asaas_id, status, value_cents, payment_date
        FROM asaas_payments
        WHERE asaas_id = ?
        """,
        (asaas_id,),
    ).fetchone()
    if payment is None:
        raise ValueError("Cobranca Asaas nao encontrada")
    transaction = connection.execute(
        """
        SELECT id, transaction_type, status, amount_cents, effective_date
        FROM financial_transactions
        WHERE id = ?
        """,
        (transaction_id,),
    ).fetchone()
    if transaction is None:
        raise ValueError("Lancamento financeiro nao encontrado")
    if transaction["transaction_type"] != "revenue" or transaction["status"] != "posted":
        raise ValueError("Conciliacao Asaas aceita apenas receitas realizadas")
    return payment, transaction


def _reconciliation_id(
    connection: sqlite3.Connection,
    *,
    asaas_id: str,
    transaction_id: int,
) -> int | None:
    row = connection.execute(
        """
        SELECT id
        FROM asaas_reconciliations
        WHERE asaas_id = ? AND transaction_id = ?
        """,
        (asaas_id, transaction_id),
    ).fetchone()
    return None if row is None else int(row["id"])
