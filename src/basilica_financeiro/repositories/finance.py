from __future__ import annotations

import sqlite3
from calendar import monthrange
from datetime import date, timedelta
from uuid import uuid4

from basilica_financeiro.repositories.audit import record_audit

ENTRY_TYPES = {"payable", "receivable"}
ENTRY_STATUSES = {"open", "partial", "paid", "overdue", "canceled"}
SERIES_MODES = {"installment", "recurring"}
SERIES_FREQUENCIES = {"weekly", "monthly", "yearly"}


def create_financial_account(
    connection: sqlite3.Connection,
    *,
    name: str,
    account_type: str,
    opening_balance_cents: int,
    balance_date: date,
    actor_user_id: int | None,
    institution: str | None = None,
    masked_number: str | None = None,
    color: str | None = None,
    notes: str | None = None,
) -> int:
    _validate_money(opening_balance_cents, allow_zero=True)
    cursor = connection.execute(
        """
        INSERT INTO financial_accounts (
            name, account_type, institution, masked_number, opening_balance_cents,
            current_balance_cents, balance_date, color, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            account_type,
            institution,
            masked_number,
            opening_balance_cents,
            opening_balance_cents,
            balance_date.isoformat(),
            color,
            notes,
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao criar conta financeira")
    account_id = cursor.lastrowid
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create",
        entity="financial_account",
        entity_id=str(account_id),
        before=None,
        after={"name": name, "opening_balance_cents": opening_balance_cents},
        origin="local",
        result="success",
    )
    return account_id


def create_category(
    connection: sqlite3.Connection,
    *,
    name: str,
    kind: str,
    actor_user_id: int | None,
    parent_id: int | None = None,
) -> int:
    if kind not in {"revenue", "expense"}:
        raise ValueError("Categoria precisa ser revenue ou expense")
    cursor = connection.execute(
        "INSERT INTO categories (name, kind, parent_id) VALUES (?, ?, ?)",
        (name, kind, parent_id),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao criar categoria")
    category_id = cursor.lastrowid
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create",
        entity="category",
        entity_id=str(category_id),
        before=None,
        after={"name": name, "kind": kind},
        origin="local",
        result="success",
    )
    return category_id


def create_cost_center(
    connection: sqlite3.Connection,
    *,
    name: str,
    actor_user_id: int | None,
    description: str | None = None,
) -> int:
    cursor = connection.execute(
        "INSERT INTO cost_centers (name, description) VALUES (?, ?)",
        (name, description),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao criar centro de custo")
    cost_center_id = cursor.lastrowid
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create",
        entity="cost_center",
        entity_id=str(cost_center_id),
        before=None,
        after={"name": name},
        origin="local",
        result="success",
    )
    return cost_center_id


def record_revenue(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    amount_cents: int,
    description: str,
    effective_date: date,
    actor_user_id: int | None,
    category_id: int | None = None,
    cost_center_id: int | None = None,
) -> int:
    return _record_transaction(
        connection,
        account_id=account_id,
        category_id=category_id,
        cost_center_id=cost_center_id,
        transaction_type="revenue",
        amount_cents=amount_cents,
        description=description,
        effective_date=effective_date,
        actor_user_id=actor_user_id,
    )


def record_external_revenue(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    amount_cents: int,
    description: str,
    effective_date: date,
    external_id: str,
    origin: str,
    actor_user_id: int | None,
    category_id: int | None = None,
    cost_center_id: int | None = None,
) -> int:
    if not external_id.strip():
        raise ValueError("Lancamento externo precisa de identificador")
    if not origin.strip():
        raise ValueError("Lancamento externo precisa de origem")
    _validate_money(amount_cents)
    cursor = connection.execute(
        """
        INSERT INTO financial_transactions (
            account_id, category_id, cost_center_id, transaction_type, description,
            amount_cents, effective_date, external_id, origin, created_by
        )
        VALUES (?, ?, ?, 'revenue', ?, ?, ?, ?, ?, ?)
        """,
        (
            account_id,
            category_id,
            cost_center_id,
            description,
            amount_cents,
            effective_date.isoformat(),
            external_id,
            origin,
            actor_user_id,
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao criar receita externa")
    transaction_id = cursor.lastrowid
    _apply_balance_delta(connection, account_id, amount_cents)
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create_external",
        entity="financial_transaction",
        entity_id=str(transaction_id),
        before=None,
        after={
            "transaction_type": "revenue",
            "amount_cents": amount_cents,
            "external_id": external_id,
            "origin": origin,
        },
        origin=origin,
        result="success",
    )
    return transaction_id


def record_expense(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    amount_cents: int,
    description: str,
    effective_date: date,
    actor_user_id: int | None,
    category_id: int | None = None,
    cost_center_id: int | None = None,
) -> int:
    return _record_transaction(
        connection,
        account_id=account_id,
        category_id=category_id,
        cost_center_id=cost_center_id,
        transaction_type="expense",
        amount_cents=amount_cents,
        description=description,
        effective_date=effective_date,
        actor_user_id=actor_user_id,
    )


def record_transaction_series(
    connection: sqlite3.Connection,
    *,
    transaction_type: str,
    account_id: int,
    total_amount_cents: int,
    description: str,
    first_effective_date: date,
    actor_user_id: int | None,
    occurrence_count: int,
    mode: str,
    frequency: str = "monthly",
    category_id: int | None = None,
    cost_center_id: int | None = None,
) -> list[int]:
    if transaction_type not in {"revenue", "expense"}:
        raise ValueError("Serie precisa ser de receita ou despesa")
    _validate_series(mode=mode, frequency=frequency, occurrence_count=occurrence_count)
    amounts = (
        _split_amount(total_amount_cents, occurrence_count)
        if mode == "installment"
        else [total_amount_cents] * occurrence_count
    )
    series_group_id = str(uuid4())
    transaction_ids = []
    for index, amount_cents in enumerate(amounts, start=1):
        effective_date = _add_periods(first_effective_date, frequency=frequency, periods=index - 1)
        transaction_id = _record_transaction(
            connection,
            account_id=account_id,
            category_id=category_id,
            cost_center_id=cost_center_id,
            transaction_type=transaction_type,
            amount_cents=amount_cents,
            description=_series_description(
                description,
                installment_number=index,
                installment_count=occurrence_count,
                mode=mode,
            ),
            effective_date=effective_date,
            actor_user_id=actor_user_id,
            series_group_id=series_group_id,
            installment_number=index,
            installment_count=occurrence_count,
            recurrence_rule=_series_rule(mode=mode, frequency=frequency),
        )
        transaction_ids.append(transaction_id)
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create_series",
        entity="financial_transaction",
        entity_id=series_group_id,
        before=None,
        after={
            "transaction_type": transaction_type,
            "occurrence_count": occurrence_count,
            "mode": mode,
            "frequency": frequency,
        },
        origin="local",
        result="success",
    )
    return transaction_ids


def record_transfer(
    connection: sqlite3.Connection,
    *,
    origin_account_id: int,
    destination_account_id: int,
    amount_cents: int,
    description: str,
    effective_date: date,
    actor_user_id: int | None,
) -> tuple[int, int]:
    if origin_account_id == destination_account_id:
        raise ValueError("Contas de origem e destino precisam ser diferentes")
    _validate_money(amount_cents)
    transfer_group_id = str(uuid4())
    out_id = _insert_transaction(
        connection,
        account_id=origin_account_id,
        category_id=None,
        cost_center_id=None,
        transaction_type="transfer_out",
        amount_cents=amount_cents,
        description=description,
        effective_date=effective_date,
        actor_user_id=actor_user_id,
        transfer_group_id=transfer_group_id,
    )
    in_id = _insert_transaction(
        connection,
        account_id=destination_account_id,
        category_id=None,
        cost_center_id=None,
        transaction_type="transfer_in",
        amount_cents=amount_cents,
        description=description,
        effective_date=effective_date,
        actor_user_id=actor_user_id,
        transfer_group_id=transfer_group_id,
    )
    _apply_balance_delta(connection, origin_account_id, -amount_cents)
    _apply_balance_delta(connection, destination_account_id, amount_cents)
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create",
        entity="transfer",
        entity_id=transfer_group_id,
        before=None,
        after={
            "origin_account_id": origin_account_id,
            "destination_account_id": destination_account_id,
            "amount_cents": amount_cents,
        },
        origin="local",
        result="success",
    )
    return out_id, in_id


def cancel_financial_transaction(
    connection: sqlite3.Connection,
    *,
    transaction_id: int,
    actor_user_id: int | None,
) -> None:
    row = connection.execute(
        """
        SELECT id, account_id, transaction_type, amount_cents, status, transfer_group_id
        FROM financial_transactions
        WHERE id = ?
        """,
        (transaction_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Lancamento financeiro nao encontrado")
    if row["status"] != "posted":
        raise ValueError("Lancamento financeiro ja esta cancelado")
    if row["transfer_group_id"] is None:
        rows = [row]
        entity_id = str(transaction_id)
    else:
        rows = connection.execute(
            """
            SELECT id, account_id, transaction_type, amount_cents, status, transfer_group_id
            FROM financial_transactions
            WHERE transfer_group_id = ? AND status = 'posted'
            """,
            (row["transfer_group_id"],),
        ).fetchall()
        entity_id = str(row["transfer_group_id"])
    for item in rows:
        _apply_balance_delta(
            connection,
            int(item["account_id"]),
            _reversal_delta(str(item["transaction_type"]), int(item["amount_cents"])),
        )
        connection.execute(
            "UPDATE financial_transactions SET status = 'canceled' WHERE id = ?",
            (item["id"],),
        )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="cancel",
        entity="financial_transaction",
        entity_id=entity_id,
        before={"status": "posted"},
        after={"status": "canceled"},
        origin="local",
        result="success",
    )


def create_payable_receivable_entry(
    connection: sqlite3.Connection,
    *,
    entry_type: str,
    counterparty: str,
    description: str,
    amount_cents: int,
    due_date: date,
    actor_user_id: int | None,
    account_id: int | None = None,
    category_id: int | None = None,
    cost_center_id: int | None = None,
    notes: str | None = None,
    series_group_id: str | None = None,
    installment_number: int = 1,
    installment_count: int = 1,
    recurrence_rule: str | None = None,
) -> int:
    if entry_type not in ENTRY_TYPES:
        raise ValueError("Titulo precisa ser payable ou receivable")
    _validate_money(amount_cents)
    cursor = connection.execute(
        """
        INSERT INTO payable_receivable_entries (
            entry_type, account_id, category_id, cost_center_id, counterparty,
            description, amount_cents, due_date, notes, created_by, series_group_id,
            installment_number, installment_count, recurrence_rule
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_type,
            account_id,
            category_id,
            cost_center_id,
            counterparty,
            description,
            amount_cents,
            due_date.isoformat(),
            notes,
            actor_user_id,
            series_group_id,
            installment_number,
            installment_count,
            recurrence_rule,
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao criar titulo financeiro")
    entry_id = cursor.lastrowid
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create",
        entity="payable_receivable_entry",
        entity_id=str(entry_id),
        before=None,
        after={
            "entry_type": entry_type,
            "amount_cents": amount_cents,
            "due_date": due_date.isoformat(),
        },
        origin="local",
        result="success",
    )
    return entry_id


def create_payable_receivable_series(
    connection: sqlite3.Connection,
    *,
    entry_type: str,
    counterparty: str,
    description: str,
    total_amount_cents: int,
    first_due_date: date,
    actor_user_id: int | None,
    occurrence_count: int,
    mode: str,
    frequency: str = "monthly",
    account_id: int | None = None,
    category_id: int | None = None,
    cost_center_id: int | None = None,
    notes: str | None = None,
) -> list[int]:
    if entry_type not in ENTRY_TYPES:
        raise ValueError("Titulo precisa ser payable ou receivable")
    _validate_series(mode=mode, frequency=frequency, occurrence_count=occurrence_count)
    amounts = (
        _split_amount(total_amount_cents, occurrence_count)
        if mode == "installment"
        else [total_amount_cents] * occurrence_count
    )
    series_group_id = str(uuid4())
    entry_ids = []
    for index, amount_cents in enumerate(amounts, start=1):
        due_date = _add_periods(first_due_date, frequency=frequency, periods=index - 1)
        entry_id = create_payable_receivable_entry(
            connection,
            entry_type=entry_type,
            account_id=account_id,
            category_id=category_id,
            cost_center_id=cost_center_id,
            counterparty=counterparty,
            description=_series_description(
                description,
                installment_number=index,
                installment_count=occurrence_count,
                mode=mode,
            ),
            amount_cents=amount_cents,
            due_date=due_date,
            actor_user_id=actor_user_id,
            notes=notes,
            series_group_id=series_group_id,
            installment_number=index,
            installment_count=occurrence_count,
            recurrence_rule=_series_rule(mode=mode, frequency=frequency),
        )
        entry_ids.append(entry_id)
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create_series",
        entity="payable_receivable_entry",
        entity_id=series_group_id,
        before=None,
        after={
            "entry_type": entry_type,
            "occurrence_count": occurrence_count,
            "mode": mode,
            "frequency": frequency,
        },
        origin="local",
        result="success",
    )
    return entry_ids


def cancel_payable_receivable_entry(
    connection: sqlite3.Connection,
    *,
    entry_id: int,
    actor_user_id: int | None,
) -> None:
    row = connection.execute(
        """
        SELECT id, status, paid_amount_cents
        FROM payable_receivable_entries
        WHERE id = ?
        """,
        (entry_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Titulo financeiro nao encontrado")
    if row["status"] in {"paid", "canceled"}:
        raise ValueError("Titulo financeiro nao pode ser cancelado")
    connection.execute(
        """
        UPDATE payable_receivable_entries
        SET status = 'canceled',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (entry_id,),
    )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="cancel",
        entity="payable_receivable_entry",
        entity_id=str(entry_id),
        before={"status": row["status"], "paid_amount_cents": row["paid_amount_cents"]},
        after={"status": "canceled"},
        origin="local",
        result="success",
    )


def settle_payable_receivable_entry(
    connection: sqlite3.Connection,
    *,
    entry_id: int,
    account_id: int,
    amount_cents: int,
    settlement_date: date,
    actor_user_id: int | None,
) -> int:
    _validate_money(amount_cents)
    entry = connection.execute(
        """
        SELECT id, entry_type, category_id, cost_center_id, description,
               amount_cents, paid_amount_cents, status
        FROM payable_receivable_entries
        WHERE id = ?
        """,
        (entry_id,),
    ).fetchone()
    if entry is None:
        raise ValueError("Titulo financeiro nao encontrado")
    if entry["status"] in {"paid", "canceled"}:
        raise ValueError("Titulo financeiro nao aceita nova baixa")
    current_paid = int(entry["paid_amount_cents"])
    total = int(entry["amount_cents"])
    if current_paid + amount_cents > total:
        raise ValueError("Baixa nao pode exceder o valor em aberto")
    if entry["entry_type"] == "receivable":
        transaction_id = record_revenue(
            connection,
            account_id=account_id,
            amount_cents=amount_cents,
            description=f"Baixa: {entry['description']}",
            effective_date=settlement_date,
            actor_user_id=actor_user_id,
            category_id=entry["category_id"],
            cost_center_id=entry["cost_center_id"],
        )
    else:
        transaction_id = record_expense(
            connection,
            account_id=account_id,
            amount_cents=amount_cents,
            description=f"Baixa: {entry['description']}",
            effective_date=settlement_date,
            actor_user_id=actor_user_id,
            category_id=entry["category_id"],
            cost_center_id=entry["cost_center_id"],
        )
    new_paid = current_paid + amount_cents
    new_status = "paid" if new_paid == total else "partial"
    connection.execute(
        """
        UPDATE payable_receivable_entries
        SET account_id = ?,
            paid_amount_cents = ?,
            status = ?,
            paid_at = ?,
            settlement_transaction_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            account_id,
            new_paid,
            new_status,
            settlement_date.isoformat(),
            transaction_id,
            entry_id,
        ),
    )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="settle",
        entity="payable_receivable_entry",
        entity_id=str(entry_id),
        before={"paid_amount_cents": current_paid, "status": entry["status"]},
        after={"paid_amount_cents": new_paid, "status": new_status},
        origin="local",
        result="success",
    )
    return transaction_id


def list_payable_receivable_entries(
    connection: sqlite3.Connection,
    *,
    today: date,
    entry_type: str | None = None,
    category_id: int | None = None,
    cost_center_id: int | None = None,
    status: str | None = None,
) -> list[dict[str, object]]:
    if entry_type is not None and entry_type not in ENTRY_TYPES:
        raise ValueError("Titulo precisa ser payable ou receivable")
    if status is not None and status not in ENTRY_STATUSES:
        raise ValueError("Status de titulo invalido")
    rows = connection.execute(
        """
        SELECT
            e.id,
            e.entry_type,
            e.counterparty,
            e.description,
            e.amount_cents,
            e.paid_amount_cents,
            e.due_date,
            e.status,
            e.paid_at,
            e.series_group_id,
            e.installment_number,
            e.installment_count,
            e.recurrence_rule,
            a.name AS account_name,
            c.name AS category_name,
            cc.name AS cost_center_name
        FROM payable_receivable_entries e
        LEFT JOIN financial_accounts a ON a.id = e.account_id
        LEFT JOIN categories c ON c.id = e.category_id
        LEFT JOIN cost_centers cc ON cc.id = e.cost_center_id
        WHERE (? IS NULL OR e.entry_type = ?)
          AND (? IS NULL OR e.category_id = ?)
          AND (? IS NULL OR e.cost_center_id = ?)
          AND (? IS NULL OR e.status = ?)
        ORDER BY e.due_date ASC, e.id DESC
        LIMIT 300
        """,
        (
            entry_type,
            entry_type,
            category_id,
            category_id,
            cost_center_id,
            cost_center_id,
            status,
            status,
        ),
    ).fetchall()
    return [_entry_row_with_effective_status(row, today=today) for row in rows]


def get_dashboard_summary(connection: sqlite3.Connection, *, today: date) -> dict[str, int]:
    month_start = today.replace(day=1)
    totals = get_cash_flow_totals(connection, start_date=month_start, end_date=today)
    balance_row = connection.execute(
        "SELECT COALESCE(SUM(current_balance_cents), 0) AS total FROM financial_accounts"
    ).fetchone()
    due_rows = list_payable_receivable_entries(connection, today=today)
    open_payables = 0
    open_receivables = 0
    overdue_payables = 0
    overdue_receivables = 0
    for row in due_rows:
        status = str(row["effective_status"])
        if status in {"paid", "canceled"}:
            continue
        open_amount = _dict_int(row, "open_amount_cents")
        if row["entry_type"] == "payable":
            open_payables += open_amount
            if status == "overdue":
                overdue_payables += open_amount
        else:
            open_receivables += open_amount
            if status == "overdue":
                overdue_receivables += open_amount
    return {
        "balance_cents": int(balance_row["total"]) if balance_row is not None else 0,
        "revenue_cents": totals["revenue_cents"],
        "expense_cents": totals["expense_cents"],
        "result_cents": totals["result_cents"],
        "open_payables_cents": open_payables,
        "open_receivables_cents": open_receivables,
        "overdue_payables_cents": overdue_payables,
        "overdue_receivables_cents": overdue_receivables,
    }


def get_account_balance_cents(connection: sqlite3.Connection, account_id: int) -> int:
    row = connection.execute(
        "SELECT current_balance_cents FROM financial_accounts WHERE id = ?",
        (account_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Conta financeira nao encontrada")
    return int(row["current_balance_cents"])


def list_financial_accounts(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT id, name, account_type, current_balance_cents, status, balance_date
            FROM financial_accounts
            ORDER BY name
            """
        ).fetchall()
    )


def list_categories(
    connection: sqlite3.Connection,
    *,
    kind: str | None = None,
) -> list[sqlite3.Row]:
    if kind is not None and kind not in {"revenue", "expense"}:
        raise ValueError("Categoria precisa ser revenue ou expense")
    if kind is None:
        return list(
            connection.execute(
                """
                SELECT id, name, kind, parent_id, is_active
                FROM categories
                WHERE is_active = 1
                ORDER BY kind, name
                """
            ).fetchall()
        )
    return list(
        connection.execute(
            """
            SELECT id, name, kind, parent_id, is_active
            FROM categories
            WHERE is_active = 1 AND kind = ?
            ORDER BY name
            """,
            (kind,),
        ).fetchall()
    )


def list_cost_centers(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT id, name, description, is_active
            FROM cost_centers
            WHERE is_active = 1
            ORDER BY name
            """
        ).fetchall()
    )


def list_financial_transactions(
    connection: sqlite3.Connection,
    *,
    transaction_type: str | None = None,
    category_id: int | None = None,
    cost_center_id: int | None = None,
) -> list[sqlite3.Row]:
    allowed_types = {"revenue", "expense", "transfer_in", "transfer_out"}
    if transaction_type is not None and transaction_type not in allowed_types:
        raise ValueError("Tipo de lancamento invalido")
    return list(
        connection.execute(
            """
            SELECT
                t.id,
                t.effective_date,
                t.transaction_type,
                t.description,
                t.amount_cents,
                t.installment_number,
                t.installment_count,
                t.recurrence_rule,
                a.name AS account_name,
                c.name AS category_name,
                cc.name AS cost_center_name
            FROM financial_transactions t
            JOIN financial_accounts a ON a.id = t.account_id
            LEFT JOIN categories c ON c.id = t.category_id
            LEFT JOIN cost_centers cc ON cc.id = t.cost_center_id
            WHERE t.status = 'posted'
              AND (? IS NULL OR t.transaction_type = ?)
              AND (? IS NULL OR t.category_id = ?)
              AND (? IS NULL OR t.cost_center_id = ?)
            ORDER BY t.effective_date DESC, t.id DESC
            LIMIT 200
            """,
            (
                transaction_type,
                transaction_type,
                category_id,
                category_id,
                cost_center_id,
                cost_center_id,
            ),
        ).fetchall()
    )


def get_cash_flow_totals(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT transaction_type, COALESCE(SUM(amount_cents), 0) AS total_cents
        FROM financial_transactions
        WHERE effective_date BETWEEN ? AND ?
          AND status = 'posted'
        GROUP BY transaction_type
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    totals = {row["transaction_type"]: int(row["total_cents"]) for row in rows}
    revenue = totals.get("revenue", 0)
    expense = totals.get("expense", 0)
    return {"revenue_cents": revenue, "expense_cents": expense, "result_cents": revenue - expense}


def _record_transaction(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    category_id: int | None,
    cost_center_id: int | None,
    transaction_type: str,
    amount_cents: int,
    description: str,
    effective_date: date,
    actor_user_id: int | None,
    series_group_id: str | None = None,
    installment_number: int = 1,
    installment_count: int = 1,
    recurrence_rule: str | None = None,
) -> int:
    _validate_money(amount_cents)
    transaction_id = _insert_transaction(
        connection,
        account_id=account_id,
        category_id=category_id,
        cost_center_id=cost_center_id,
        transaction_type=transaction_type,
        amount_cents=amount_cents,
        description=description,
        effective_date=effective_date,
        actor_user_id=actor_user_id,
        transfer_group_id=None,
        series_group_id=series_group_id,
        installment_number=installment_number,
        installment_count=installment_count,
        recurrence_rule=recurrence_rule,
    )
    balance_delta = amount_cents if transaction_type == "revenue" else -amount_cents
    _apply_balance_delta(connection, account_id, balance_delta)
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create",
        entity="financial_transaction",
        entity_id=str(transaction_id),
        before=None,
        after={"transaction_type": transaction_type, "amount_cents": amount_cents},
        origin="local",
        result="success",
    )
    return transaction_id


def _insert_transaction(
    connection: sqlite3.Connection,
    *,
    account_id: int,
    category_id: int | None,
    cost_center_id: int | None,
    transaction_type: str,
    amount_cents: int,
    description: str,
    effective_date: date,
    actor_user_id: int | None,
    transfer_group_id: str | None,
    series_group_id: str | None = None,
    installment_number: int = 1,
    installment_count: int = 1,
    recurrence_rule: str | None = None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO financial_transactions (
            account_id, category_id, cost_center_id, transaction_type, description,
            amount_cents, effective_date, transfer_group_id, created_by, series_group_id,
            installment_number, installment_count, recurrence_rule
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            account_id,
            category_id,
            cost_center_id,
            transaction_type,
            description,
            amount_cents,
            effective_date.isoformat(),
            transfer_group_id,
            actor_user_id,
            series_group_id,
            installment_number,
            installment_count,
            recurrence_rule,
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao criar movimentacao financeira")
    return cursor.lastrowid


def _apply_balance_delta(
    connection: sqlite3.Connection,
    account_id: int,
    balance_delta_cents: int,
) -> None:
    cursor = connection.execute(
        """
        UPDATE financial_accounts
        SET current_balance_cents = current_balance_cents + ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (balance_delta_cents, account_id),
    )
    if cursor.rowcount != 1:
        raise ValueError("Conta financeira nao encontrada")


def _validate_money(amount_cents: int, *, allow_zero: bool = False) -> None:
    if not isinstance(amount_cents, int):
        raise TypeError("Valores monetarios precisam ser inteiros em centavos")
    if amount_cents < 0 or (amount_cents == 0 and not allow_zero):
        raise ValueError("Valor monetario precisa ser positivo")


def _validate_series(*, mode: str, frequency: str, occurrence_count: int) -> None:
    if mode not in SERIES_MODES:
        raise ValueError("Serie precisa ser installment ou recurring")
    if frequency not in SERIES_FREQUENCIES:
        raise ValueError("Frequencia precisa ser weekly, monthly ou yearly")
    if occurrence_count < 2:
        raise ValueError("Serie precisa ter pelo menos 2 ocorrencias")


def _split_amount(total_amount_cents: int, installment_count: int) -> list[int]:
    _validate_money(total_amount_cents)
    base = total_amount_cents // installment_count
    remainder = total_amount_cents % installment_count
    amounts = [base] * installment_count
    for index in range(remainder):
        amounts[-(index + 1)] += 1
    if any(amount <= 0 for amount in amounts):
        raise ValueError("Valor total nao comporta a quantidade de parcelas")
    return amounts


def _add_periods(start_date: date, *, frequency: str, periods: int) -> date:
    if frequency == "weekly":
        return start_date + timedelta(days=7 * periods)
    if frequency == "monthly":
        return _add_months(start_date, periods)
    if frequency == "yearly":
        return _add_months(start_date, periods * 12)
    raise ValueError("Frequencia precisa ser weekly, monthly ou yearly")


def _add_months(start_date: date, months: int) -> date:
    month_index = start_date.month - 1 + months
    year = start_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _series_rule(*, mode: str, frequency: str) -> str:
    return f"{mode}:{frequency}"


def _series_description(
    description: str,
    *,
    installment_number: int,
    installment_count: int,
    mode: str,
) -> str:
    label = "Parcela" if mode == "installment" else "Recorrencia"
    return f"{description} ({label} {installment_number}/{installment_count})"


def _reversal_delta(transaction_type: str, amount_cents: int) -> int:
    if transaction_type in {"revenue", "transfer_in"}:
        return -amount_cents
    if transaction_type in {"expense", "transfer_out"}:
        return amount_cents
    raise ValueError("Tipo de lancamento invalido")


def _dict_int(row: dict[str, object], key: str) -> int:
    value = row[key]
    if not isinstance(value, int):
        raise TypeError(f"Campo {key} deveria ser inteiro")
    return value


def _entry_row_with_effective_status(
    row: sqlite3.Row,
    *,
    today: date,
) -> dict[str, object]:
    amount = int(row["amount_cents"])
    paid = int(row["paid_amount_cents"])
    stored_status = str(row["status"])
    due = date.fromisoformat(str(row["due_date"]))
    effective_status = stored_status
    if stored_status in {"open", "partial"} and due < today:
        effective_status = "overdue"
    return {
        "id": int(row["id"]),
        "entry_type": str(row["entry_type"]),
        "counterparty": str(row["counterparty"]),
        "description": str(row["description"]),
        "amount_cents": amount,
        "paid_amount_cents": paid,
        "open_amount_cents": amount - paid,
        "due_date": str(row["due_date"]),
        "status": stored_status,
        "effective_status": effective_status,
        "paid_at": row["paid_at"],
        "series_group_id": row["series_group_id"],
        "installment_number": int(row["installment_number"]),
        "installment_count": int(row["installment_count"]),
        "recurrence_rule": row["recurrence_rule"],
        "account_name": row["account_name"],
        "category_name": row["category_name"],
        "cost_center_name": row["cost_center_name"],
    }
