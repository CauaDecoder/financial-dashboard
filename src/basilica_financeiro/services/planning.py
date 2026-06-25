from __future__ import annotations

import sqlite3
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import cast

from basilica_financeiro.repositories.audit import record_audit

TRANSACTION_TYPES = {"revenue", "expense"}


@dataclass(frozen=True)
class BudgetComparison:
    year: int
    month: int
    category_id: int | None
    category_name: str
    category_kind: str
    cost_center_id: int | None
    cost_center_name: str
    budgeted_cents: int
    actual_cents: int
    variance_cents: int


@dataclass(frozen=True)
class AnnualGoalComparison:
    year: int
    category_id: int | None
    category_name: str
    category_kind: str
    cost_center_id: int | None
    cost_center_name: str
    target_cents: int
    actual_cents: int
    variance_cents: int
    progress_percent: int


@dataclass(frozen=True)
class CashFlowProjectionRow:
    projected_date: date
    expected_revenue_cents: int
    expected_expense_cents: int
    net_cents: int
    accumulated_cents: int


@dataclass(frozen=True)
class CategorizationSuggestion:
    rule_id: int
    keyword: str
    transaction_type: str | None
    category_id: int
    category_name: str
    cost_center_id: int | None
    cost_center_name: str | None
    priority: int


def upsert_budget(
    connection: sqlite3.Connection,
    *,
    year: int,
    month: int,
    category_id: int,
    amount_cents: int,
    actor_user_id: int | None,
    cost_center_id: int | None = None,
    notes: str | None = None,
) -> int:
    _validate_year_month(year=year, month=month)
    _validate_money(amount_cents)
    category = _get_category(connection, category_id)
    _ensure_cost_center(connection, cost_center_id)
    existing = connection.execute(
        """
        SELECT id, amount_cents
        FROM budgets
        WHERE year = ?
          AND month = ?
          AND category_id = ?
          AND (cost_center_id IS ? OR cost_center_id = ?)
        """,
        (year, month, category_id, cost_center_id, cost_center_id),
    ).fetchone()
    if existing is None:
        cursor = connection.execute(
            """
            INSERT INTO budgets (
                year, month, category_id, cost_center_id, amount_cents, notes, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (year, month, category_id, cost_center_id, amount_cents, notes, actor_user_id),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Falha ao criar orcamento")
        budget_id = cursor.lastrowid
        action = "create"
        before = None
    else:
        budget_id = int(existing["id"])
        before = {"amount_cents": int(existing["amount_cents"])}
        connection.execute(
            """
            UPDATE budgets
            SET amount_cents = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (amount_cents, notes, budget_id),
        )
        action = "update"
    record_audit(
        connection,
        user_id=actor_user_id,
        action=action,
        entity="budget",
        entity_id=str(budget_id),
        before=before,
        after={
            "year": year,
            "month": month,
            "category_id": category_id,
            "category_kind": str(category["kind"]),
            "cost_center_id": cost_center_id,
            "amount_cents": amount_cents,
        },
        origin="local",
        result="success",
    )
    return budget_id


def distribute_annual_budget(
    connection: sqlite3.Connection,
    *,
    year: int,
    category_id: int,
    total_amount_cents: int,
    actor_user_id: int | None,
    cost_center_id: int | None = None,
    monthly_weights: list[int] | None = None,
    notes: str | None = None,
) -> list[int]:
    _validate_year(year)
    _validate_money(total_amount_cents)
    monthly_amounts = _split_annual_amount(total_amount_cents, monthly_weights=monthly_weights)
    budget_ids = [
        upsert_budget(
            connection,
            year=year,
            month=month,
            category_id=category_id,
            cost_center_id=cost_center_id,
            amount_cents=amount_cents,
            notes=notes,
            actor_user_id=actor_user_id,
        )
        for month, amount_cents in enumerate(monthly_amounts, start=1)
    ]
    record_audit(
        connection,
        user_id=actor_user_id,
        action="distribute_annual",
        entity="budget",
        entity_id=f"{year}:{category_id}:{cost_center_id or 'all'}",
        before=None,
        after={
            "year": year,
            "category_id": category_id,
            "cost_center_id": cost_center_id,
            "total_amount_cents": total_amount_cents,
            "months": 12,
            "distribution": "seasonal" if monthly_weights is not None else "linear",
            "monthly_weights": monthly_weights,
        },
        origin="local",
        result="success",
    )
    return budget_ids


def list_budgets(
    connection: sqlite3.Connection,
    *,
    year: int | None = None,
    month: int | None = None,
) -> list[sqlite3.Row]:
    if year is not None and month is not None:
        _validate_year_month(year=year, month=month)
    rows = connection.execute(
        """
        SELECT
            b.id,
            b.year,
            b.month,
            b.amount_cents,
            b.notes,
            c.id AS category_id,
            c.name AS category_name,
            c.kind AS category_kind,
            cc.id AS cost_center_id,
            cc.name AS cost_center_name
        FROM budgets b
        JOIN categories c ON c.id = b.category_id
        LEFT JOIN cost_centers cc ON cc.id = b.cost_center_id
        WHERE (? IS NULL OR b.year = ?)
          AND (? IS NULL OR b.month = ?)
        ORDER BY b.year DESC, b.month DESC, c.kind, c.name, cc.name
        """,
        (year, year, month, month),
    ).fetchall()
    return list(rows)


def get_budget_comparison(
    connection: sqlite3.Connection,
    *,
    year: int,
    month: int,
) -> list[BudgetComparison]:
    _validate_year_month(year=year, month=month)
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    budget_rows = connection.execute(
        """
        SELECT
            b.category_id,
            c.name AS category_name,
            c.kind AS category_kind,
            b.cost_center_id,
            cc.name AS cost_center_name,
            SUM(b.amount_cents) AS budgeted_cents
        FROM budgets b
        JOIN categories c ON c.id = b.category_id
        LEFT JOIN cost_centers cc ON cc.id = b.cost_center_id
        WHERE b.year = ? AND b.month = ?
        GROUP BY b.category_id, b.cost_center_id
        """,
        (year, month),
    ).fetchall()
    actual_rows = connection.execute(
        """
        SELECT
            t.category_id,
            COALESCE(c.name, 'Sem categoria') AS category_name,
            COALESCE(c.kind, t.transaction_type) AS category_kind,
            t.cost_center_id,
            COALESCE(cc.name, 'Sem centro') AS cost_center_name,
            SUM(t.amount_cents) AS actual_cents
        FROM financial_transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        LEFT JOIN cost_centers cc ON cc.id = t.cost_center_id
        WHERE t.status = 'posted'
          AND t.transaction_type IN ('revenue', 'expense')
          AND t.effective_date BETWEEN ? AND ?
        GROUP BY t.category_id, t.cost_center_id, t.transaction_type
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    comparisons: dict[tuple[int | None, int | None, str], BudgetComparison] = {}
    for row in budget_rows:
        key = _comparison_key(row)
        comparisons[key] = BudgetComparison(
            year=year,
            month=month,
            category_id=_optional_row_int(row, "category_id"),
            category_name=str(row["category_name"]),
            category_kind=str(row["category_kind"]),
            cost_center_id=_optional_row_int(row, "cost_center_id"),
            cost_center_name=_cost_center_label(row["cost_center_name"]),
            budgeted_cents=int(row["budgeted_cents"]),
            actual_cents=0,
            variance_cents=0 - int(row["budgeted_cents"]),
        )
    for row in actual_rows:
        key = _comparison_key(row)
        current = comparisons.get(key)
        actual_cents = int(row["actual_cents"])
        if current is None:
            comparisons[key] = BudgetComparison(
                year=year,
                month=month,
                category_id=_optional_row_int(row, "category_id"),
                category_name=str(row["category_name"]),
                category_kind=str(row["category_kind"]),
                cost_center_id=_optional_row_int(row, "cost_center_id"),
                cost_center_name=_cost_center_label(row["cost_center_name"]),
                budgeted_cents=0,
                actual_cents=actual_cents,
                variance_cents=actual_cents,
            )
        else:
            comparisons[key] = BudgetComparison(
                year=current.year,
                month=current.month,
                category_id=current.category_id,
                category_name=current.category_name,
                category_kind=current.category_kind,
                cost_center_id=current.cost_center_id,
                cost_center_name=current.cost_center_name,
                budgeted_cents=current.budgeted_cents,
                actual_cents=actual_cents,
                variance_cents=actual_cents - current.budgeted_cents,
            )
    return sorted(
        comparisons.values(),
        key=lambda item: (item.category_kind, item.category_name, item.cost_center_name),
    )


def get_annual_goal_comparison(
    connection: sqlite3.Connection,
    *,
    year: int,
) -> list[AnnualGoalComparison]:
    _validate_year(year)
    budget_rows = connection.execute(
        """
        SELECT
            b.category_id,
            c.name AS category_name,
            c.kind AS category_kind,
            b.cost_center_id,
            cc.name AS cost_center_name,
            SUM(b.amount_cents) AS target_cents
        FROM budgets b
        JOIN categories c ON c.id = b.category_id
        LEFT JOIN cost_centers cc ON cc.id = b.cost_center_id
        WHERE b.year = ?
        GROUP BY b.category_id, b.cost_center_id
        """,
        (year,),
    ).fetchall()
    actual_rows = connection.execute(
        """
        SELECT
            t.category_id,
            COALESCE(c.name, 'Sem categoria') AS category_name,
            COALESCE(c.kind, t.transaction_type) AS category_kind,
            t.cost_center_id,
            COALESCE(cc.name, 'Sem centro') AS cost_center_name,
            SUM(t.amount_cents) AS actual_cents
        FROM financial_transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        LEFT JOIN cost_centers cc ON cc.id = t.cost_center_id
        WHERE t.status = 'posted'
          AND t.transaction_type IN ('revenue', 'expense')
          AND t.effective_date BETWEEN ? AND ?
        GROUP BY t.category_id, t.cost_center_id, t.transaction_type
        """,
        (date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat()),
    ).fetchall()
    comparisons: dict[tuple[int | None, int | None, str], AnnualGoalComparison] = {}
    for row in budget_rows:
        key = _comparison_key(row)
        target_cents = int(row["target_cents"])
        comparisons[key] = AnnualGoalComparison(
            year=year,
            category_id=_optional_row_int(row, "category_id"),
            category_name=str(row["category_name"]),
            category_kind=str(row["category_kind"]),
            cost_center_id=_optional_row_int(row, "cost_center_id"),
            cost_center_name=_cost_center_label(row["cost_center_name"]),
            target_cents=target_cents,
            actual_cents=0,
            variance_cents=0 - target_cents,
            progress_percent=0,
        )
    for row in actual_rows:
        key = _comparison_key(row)
        actual_cents = int(row["actual_cents"])
        current = comparisons.get(key)
        if current is None:
            comparisons[key] = AnnualGoalComparison(
                year=year,
                category_id=_optional_row_int(row, "category_id"),
                category_name=str(row["category_name"]),
                category_kind=str(row["category_kind"]),
                cost_center_id=_optional_row_int(row, "cost_center_id"),
                cost_center_name=_cost_center_label(row["cost_center_name"]),
                target_cents=0,
                actual_cents=actual_cents,
                variance_cents=actual_cents,
                progress_percent=0,
            )
        else:
            comparisons[key] = AnnualGoalComparison(
                year=current.year,
                category_id=current.category_id,
                category_name=current.category_name,
                category_kind=current.category_kind,
                cost_center_id=current.cost_center_id,
                cost_center_name=current.cost_center_name,
                target_cents=current.target_cents,
                actual_cents=actual_cents,
                variance_cents=actual_cents - current.target_cents,
                progress_percent=_percent(actual_cents, current.target_cents),
            )
    return sorted(
        comparisons.values(),
        key=lambda item: (item.category_kind, item.category_name, item.cost_center_name),
    )


def get_cash_flow_projection(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
) -> list[CashFlowProjectionRow]:
    if start_date > end_date:
        raise ValueError("Data inicial nao pode ser maior que a final")
    rows = connection.execute(
        """
        SELECT
            due_date,
            entry_type,
            SUM(amount_cents - paid_amount_cents) AS open_cents
        FROM payable_receivable_entries
        WHERE status IN ('open', 'partial', 'overdue')
          AND due_date BETWEEN ? AND ?
          AND amount_cents > paid_amount_cents
        GROUP BY due_date, entry_type
        ORDER BY due_date
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    by_date: dict[date, dict[str, int]] = {}
    for row in rows:
        projected_date = date.fromisoformat(str(row["due_date"]))
        totals = by_date.setdefault(projected_date, {"revenue": 0, "expense": 0})
        if row["entry_type"] == "receivable":
            totals["revenue"] += int(row["open_cents"])
        else:
            totals["expense"] += int(row["open_cents"])
    projection = []
    accumulated = 0
    current = start_date
    while current <= end_date:
        totals = by_date.get(current, {"revenue": 0, "expense": 0})
        net = totals["revenue"] - totals["expense"]
        accumulated += net
        projection.append(
            CashFlowProjectionRow(
                projected_date=current,
                expected_revenue_cents=totals["revenue"],
                expected_expense_cents=totals["expense"],
                net_cents=net,
                accumulated_cents=accumulated,
            )
        )
        current += timedelta(days=1)
    return projection


def create_categorization_rule(
    connection: sqlite3.Connection,
    *,
    keyword: str,
    category_id: int,
    actor_user_id: int | None,
    transaction_type: str | None = None,
    cost_center_id: int | None = None,
    priority: int = 100,
) -> int:
    normalized_keyword = keyword.strip().lower()
    if not normalized_keyword:
        raise ValueError("Palavra-chave precisa ser preenchida")
    if transaction_type is not None and transaction_type not in TRANSACTION_TYPES:
        raise ValueError("Tipo de lancamento invalido")
    category = _get_category(connection, category_id)
    if transaction_type is not None and str(category["kind"]) != transaction_type:
        raise ValueError("Categoria precisa ser compativel com o tipo da regra")
    _ensure_cost_center(connection, cost_center_id)
    existing = connection.execute(
        """
        SELECT id
        FROM categorization_rules
        WHERE keyword = ?
          AND (transaction_type IS ? OR transaction_type = ?)
        """,
        (normalized_keyword, transaction_type, transaction_type),
    ).fetchone()
    if existing is None:
        cursor = connection.execute(
            """
            INSERT INTO categorization_rules (
                keyword, transaction_type, category_id, cost_center_id, priority, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_keyword,
                transaction_type,
                category_id,
                cost_center_id,
                priority,
                actor_user_id,
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Falha ao criar regra de categorizacao")
        rule_id = cursor.lastrowid
    else:
        rule_id = int(existing["id"])
        connection.execute(
            """
            UPDATE categorization_rules
            SET category_id = ?,
                cost_center_id = ?,
                priority = ?,
                is_active = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (category_id, cost_center_id, priority, rule_id),
        )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="upsert",
        entity="categorization_rule",
        entity_id=str(rule_id),
        before=None,
        after={
            "keyword": normalized_keyword,
            "transaction_type": transaction_type,
            "category_id": category_id,
            "cost_center_id": cost_center_id,
            "priority": priority,
        },
        origin="local",
        result="success",
    )
    return int(rule_id)


def list_categorization_rules(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT
                r.id,
                r.keyword,
                r.transaction_type,
                r.priority,
                r.is_active,
                c.id AS category_id,
                c.name AS category_name,
                c.kind AS category_kind,
                cc.id AS cost_center_id,
                cc.name AS cost_center_name
            FROM categorization_rules r
            JOIN categories c ON c.id = r.category_id
            LEFT JOIN cost_centers cc ON cc.id = r.cost_center_id
            ORDER BY r.priority DESC, r.keyword
            """
        ).fetchall()
    )


def suggest_category_for_description(
    connection: sqlite3.Connection,
    *,
    description: str,
    transaction_type: str,
) -> CategorizationSuggestion | None:
    if transaction_type not in TRANSACTION_TYPES:
        raise ValueError("Tipo de lancamento invalido")
    normalized_description = description.lower()
    rows = connection.execute(
        """
        SELECT
            r.id,
            r.keyword,
            r.transaction_type,
            r.category_id,
            r.cost_center_id,
            r.priority,
            c.name AS category_name,
            cc.name AS cost_center_name
        FROM categorization_rules r
        JOIN categories c ON c.id = r.category_id
        LEFT JOIN cost_centers cc ON cc.id = r.cost_center_id
        WHERE r.is_active = 1
          AND (r.transaction_type IS NULL OR r.transaction_type = ?)
          AND c.kind = ?
        ORDER BY r.priority DESC, LENGTH(r.keyword) DESC, r.id
        """,
        (transaction_type, transaction_type),
    ).fetchall()
    for row in rows:
        keyword = str(row["keyword"])
        if keyword in normalized_description:
            return CategorizationSuggestion(
                rule_id=int(row["id"]),
                keyword=keyword,
                transaction_type=None
                if row["transaction_type"] is None
                else str(row["transaction_type"]),
                category_id=int(row["category_id"]),
                category_name=str(row["category_name"]),
                cost_center_id=_optional_row_int(row, "cost_center_id"),
                cost_center_name=None
                if row["cost_center_name"] is None
                else str(row["cost_center_name"]),
                priority=int(row["priority"]),
            )
    return None


def _get_category(connection: sqlite3.Connection, category_id: int) -> sqlite3.Row:
    row = connection.execute(
        "SELECT id, name, kind FROM categories WHERE id = ? AND is_active = 1",
        (category_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Categoria nao encontrada")
    return cast(sqlite3.Row, row)


def _ensure_cost_center(connection: sqlite3.Connection, cost_center_id: int | None) -> None:
    if cost_center_id is None:
        return
    row = connection.execute(
        "SELECT id FROM cost_centers WHERE id = ? AND is_active = 1",
        (cost_center_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Centro de custo nao encontrado")


def _validate_year_month(*, year: int, month: int) -> None:
    _validate_year(year)
    if month < 1 or month > 12:
        raise ValueError("Mes precisa estar entre 1 e 12")


def _validate_year(year: int) -> None:
    if year < 2000 or year > 2100:
        raise ValueError("Ano precisa estar entre 2000 e 2100")


def _validate_money(amount_cents: int) -> None:
    if not isinstance(amount_cents, int):
        raise TypeError("Valores monetarios precisam ser inteiros em centavos")
    if amount_cents <= 0:
        raise ValueError("Valor monetario precisa ser positivo")


def _comparison_key(row: sqlite3.Row) -> tuple[int | None, int | None, str]:
    return (
        _optional_row_int(row, "category_id"),
        _optional_row_int(row, "cost_center_id"),
        str(row["category_kind"]),
    )


def _optional_row_int(row: sqlite3.Row, key: str) -> int | None:
    value = row[key]
    return None if value is None else int(value)


def _cost_center_label(value: object) -> str:
    return "Sem centro" if value is None else str(value)


def _percent(value_cents: int, total_cents: int) -> int:
    if total_cents <= 0:
        return 0
    return round((value_cents / total_cents) * 100)


def _split_annual_amount(
    total_amount_cents: int,
    *,
    monthly_weights: list[int] | None = None,
) -> list[int]:
    if monthly_weights is not None:
        return _split_annual_amount_by_weights(total_amount_cents, monthly_weights)
    base = total_amount_cents // 12
    remainder = total_amount_cents % 12
    return [base + (1 if month <= remainder else 0) for month in range(1, 13)]


def _split_annual_amount_by_weights(
    total_amount_cents: int,
    monthly_weights: list[int],
) -> list[int]:
    if len(monthly_weights) != 12:
        raise ValueError("Distribuicao sazonal precisa informar 12 pesos mensais")
    if any(weight <= 0 for weight in monthly_weights):
        raise ValueError("Pesos mensais precisam ser positivos")
    total_weight = sum(monthly_weights)
    raw_values = [total_amount_cents * weight for weight in monthly_weights]
    amounts = [raw_value // total_weight for raw_value in raw_values]
    remainder = total_amount_cents - sum(amounts)
    residual_order = sorted(
        range(12),
        key=lambda index: (raw_values[index] % total_weight, -index),
        reverse=True,
    )
    for index in residual_order[:remainder]:
        amounts[index] += 1
    return amounts
