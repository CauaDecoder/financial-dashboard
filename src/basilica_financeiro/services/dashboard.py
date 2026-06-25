from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from basilica_financeiro.repositories.audit import record_audit

PERIOD_PRESETS = {"current_month", "last_30_days", "current_year", "custom"}


@dataclass(frozen=True)
class CategoryBreakdown:
    category_name: str
    transaction_type: str
    total_cents: int
    percent: int


@dataclass(frozen=True)
class CostCenterBreakdown:
    cost_center_name: str
    revenue_cents: int
    expense_cents: int
    result_cents: int


@dataclass(frozen=True)
class DueAlert:
    entry_type: str
    counterparty: str
    description: str
    due_date: date
    effective_status: str
    open_amount_cents: int
    days_until_due: int


@dataclass(frozen=True)
class AdvancedDashboard:
    revenue_cents: int
    expense_cents: int
    result_cents: int
    top_revenue_categories: list[CategoryBreakdown]
    top_expense_categories: list[CategoryBreakdown]
    cost_centers: list[CostCenterBreakdown]
    due_alerts: list[DueAlert]


@dataclass(frozen=True)
class CustomDashboard:
    id: int
    name: str
    period_preset: str
    item_limit: int
    alert_days: int
    show_revenue_categories: bool
    show_expense_categories: bool
    show_cost_centers: bool
    show_due_alerts: bool


def get_advanced_dashboard(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
    today: date,
    limit: int = 8,
    alert_days: int = 7,
) -> AdvancedDashboard:
    if start_date > end_date:
        raise ValueError("Data inicial nao pode ser maior que a final")
    if limit < 1:
        raise ValueError("Limite precisa ser positivo")
    if alert_days < 0:
        raise ValueError("Dias de alerta nao pode ser negativo")
    totals = _period_totals(connection, start_date=start_date, end_date=end_date)
    revenue_total = totals.get("revenue", 0)
    expense_total = totals.get("expense", 0)
    return AdvancedDashboard(
        revenue_cents=revenue_total,
        expense_cents=expense_total,
        result_cents=revenue_total - expense_total,
        top_revenue_categories=_category_breakdown(
            connection,
            start_date=start_date,
            end_date=end_date,
            transaction_type="revenue",
            period_total_cents=revenue_total,
            limit=limit,
        ),
        top_expense_categories=_category_breakdown(
            connection,
            start_date=start_date,
            end_date=end_date,
            transaction_type="expense",
            period_total_cents=expense_total,
            limit=limit,
        ),
        cost_centers=_cost_center_breakdown(
            connection,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        ),
        due_alerts=_due_alerts(
            connection,
            today=today,
            alert_days=alert_days,
            limit=limit,
        ),
    )


def list_custom_dashboards(connection: sqlite3.Connection) -> list[CustomDashboard]:
    rows = connection.execute(
        """
        SELECT
            id,
            name,
            period_preset,
            item_limit,
            alert_days,
            show_revenue_categories,
            show_expense_categories,
            show_cost_centers,
            show_due_alerts
        FROM custom_dashboards
        ORDER BY name
        """
    ).fetchall()
    return [_custom_dashboard_from_row(row) for row in rows]


def get_custom_dashboard(
    connection: sqlite3.Connection,
    dashboard_id: int,
) -> CustomDashboard | None:
    row = connection.execute(
        """
        SELECT
            id,
            name,
            period_preset,
            item_limit,
            alert_days,
            show_revenue_categories,
            show_expense_categories,
            show_cost_centers,
            show_due_alerts
        FROM custom_dashboards
        WHERE id = ?
        """,
        (dashboard_id,),
    ).fetchone()
    return None if row is None else _custom_dashboard_from_row(row)


def upsert_custom_dashboard(
    connection: sqlite3.Connection,
    *,
    name: str,
    period_preset: str,
    item_limit: int,
    alert_days: int,
    actor_user_id: int | None,
    dashboard_id: int | None = None,
    show_revenue_categories: bool = True,
    show_expense_categories: bool = True,
    show_cost_centers: bool = True,
    show_due_alerts: bool = True,
) -> int:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Nome do dashboard precisa ser preenchido")
    if period_preset not in PERIOD_PRESETS:
        raise ValueError("Periodo do dashboard invalido")
    if item_limit < 1 or item_limit > 20:
        raise ValueError("Limite de itens precisa estar entre 1 e 20")
    if alert_days < 0 or alert_days > 90:
        raise ValueError("Dias de alerta precisa estar entre 0 e 90")
    visible_sections = [
        show_revenue_categories,
        show_expense_categories,
        show_cost_centers,
        show_due_alerts,
    ]
    if not any(visible_sections):
        raise ValueError("Ao menos uma secao do dashboard precisa estar visivel")

    if dashboard_id is None:
        cursor = connection.execute(
            """
            INSERT INTO custom_dashboards (
                name,
                period_preset,
                item_limit,
                alert_days,
                show_revenue_categories,
                show_expense_categories,
                show_cost_centers,
                show_due_alerts,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_name,
                period_preset,
                item_limit,
                alert_days,
                int(show_revenue_categories),
                int(show_expense_categories),
                int(show_cost_centers),
                int(show_due_alerts),
                actor_user_id,
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Falha ao criar dashboard personalizado")
        saved_id = cursor.lastrowid
        action = "create"
        before = None
    else:
        current = get_custom_dashboard(connection, dashboard_id)
        if current is None:
            raise ValueError("Dashboard personalizado nao encontrado")
        before = {
            "name": current.name,
            "period_preset": current.period_preset,
            "item_limit": current.item_limit,
            "alert_days": current.alert_days,
            "show_revenue_categories": current.show_revenue_categories,
            "show_expense_categories": current.show_expense_categories,
            "show_cost_centers": current.show_cost_centers,
            "show_due_alerts": current.show_due_alerts,
        }
        connection.execute(
            """
            UPDATE custom_dashboards
            SET name = ?,
                period_preset = ?,
                item_limit = ?,
                alert_days = ?,
                show_revenue_categories = ?,
                show_expense_categories = ?,
                show_cost_centers = ?,
                show_due_alerts = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                normalized_name,
                period_preset,
                item_limit,
                alert_days,
                int(show_revenue_categories),
                int(show_expense_categories),
                int(show_cost_centers),
                int(show_due_alerts),
                dashboard_id,
            ),
        )
        saved_id = dashboard_id
        action = "update"

    record_audit(
        connection,
        user_id=actor_user_id,
        action=action,
        entity="custom_dashboard",
        entity_id=str(saved_id),
        before=before,
        after={
            "name": normalized_name,
            "period_preset": period_preset,
            "item_limit": item_limit,
            "alert_days": alert_days,
            "show_revenue_categories": show_revenue_categories,
            "show_expense_categories": show_expense_categories,
            "show_cost_centers": show_cost_centers,
            "show_due_alerts": show_due_alerts,
        },
        origin="local",
        result="success",
    )
    return int(saved_id)


def _period_totals(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT transaction_type, COALESCE(SUM(amount_cents), 0) AS total_cents
        FROM financial_transactions
        WHERE status = 'posted'
          AND transaction_type IN ('revenue', 'expense')
          AND effective_date BETWEEN ? AND ?
        GROUP BY transaction_type
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    return {str(row["transaction_type"]): int(row["total_cents"]) for row in rows}


def _category_breakdown(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
    transaction_type: str,
    period_total_cents: int,
    limit: int,
) -> list[CategoryBreakdown]:
    rows = connection.execute(
        """
        SELECT
            COALESCE(c.name, 'Sem categoria') AS category_name,
            SUM(t.amount_cents) AS total_cents
        FROM financial_transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        WHERE t.status = 'posted'
          AND t.transaction_type = ?
          AND t.effective_date BETWEEN ? AND ?
        GROUP BY COALESCE(c.name, 'Sem categoria')
        ORDER BY total_cents DESC, category_name
        LIMIT ?
        """,
        (transaction_type, start_date.isoformat(), end_date.isoformat(), limit),
    ).fetchall()
    return [
        CategoryBreakdown(
            category_name=str(row["category_name"]),
            transaction_type=transaction_type,
            total_cents=int(row["total_cents"]),
            percent=_percent(int(row["total_cents"]), period_total_cents),
        )
        for row in rows
    ]


def _cost_center_breakdown(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
    limit: int,
) -> list[CostCenterBreakdown]:
    rows = connection.execute(
        """
        SELECT
            COALESCE(cc.name, 'Sem centro') AS cost_center_name,
            SUM(CASE WHEN t.transaction_type = 'revenue' THEN t.amount_cents ELSE 0 END)
                AS revenue_cents,
            SUM(CASE WHEN t.transaction_type = 'expense' THEN t.amount_cents ELSE 0 END)
                AS expense_cents
        FROM financial_transactions t
        LEFT JOIN cost_centers cc ON cc.id = t.cost_center_id
        WHERE t.status = 'posted'
          AND t.transaction_type IN ('revenue', 'expense')
          AND t.effective_date BETWEEN ? AND ?
        GROUP BY COALESCE(cc.name, 'Sem centro')
        ORDER BY (revenue_cents - expense_cents) DESC, cost_center_name
        LIMIT ?
        """,
        (start_date.isoformat(), end_date.isoformat(), limit),
    ).fetchall()
    return [
        CostCenterBreakdown(
            cost_center_name=str(row["cost_center_name"]),
            revenue_cents=int(row["revenue_cents"]),
            expense_cents=int(row["expense_cents"]),
            result_cents=int(row["revenue_cents"]) - int(row["expense_cents"]),
        )
        for row in rows
    ]


def _due_alerts(
    connection: sqlite3.Connection,
    *,
    today: date,
    alert_days: int,
    limit: int,
) -> list[DueAlert]:
    end_date = today + timedelta(days=alert_days)
    rows = connection.execute(
        """
        SELECT
            entry_type,
            counterparty,
            description,
            amount_cents,
            paid_amount_cents,
            due_date,
            status
        FROM payable_receivable_entries
        WHERE status IN ('open', 'partial', 'overdue')
          AND amount_cents > paid_amount_cents
          AND due_date <= ?
        ORDER BY due_date ASC, id ASC
        LIMIT ?
        """,
        (end_date.isoformat(), limit),
    ).fetchall()
    alerts = []
    for row in rows:
        due_date = date.fromisoformat(str(row["due_date"]))
        effective_status = "overdue" if due_date < today else str(row["status"])
        alerts.append(
            DueAlert(
                entry_type=str(row["entry_type"]),
                counterparty=str(row["counterparty"]),
                description=str(row["description"]),
                due_date=due_date,
                effective_status=effective_status,
                open_amount_cents=int(row["amount_cents"]) - int(row["paid_amount_cents"]),
                days_until_due=(due_date - today).days,
            )
        )
    return alerts


def _percent(value_cents: int, total_cents: int) -> int:
    if total_cents <= 0:
        return 0
    return round((value_cents / total_cents) * 100)


def _custom_dashboard_from_row(row: sqlite3.Row) -> CustomDashboard:
    return CustomDashboard(
        id=int(row["id"]),
        name=str(row["name"]),
        period_preset=str(row["period_preset"]),
        item_limit=int(row["item_limit"]),
        alert_days=int(row["alert_days"]),
        show_revenue_categories=bool(row["show_revenue_categories"]),
        show_expense_categories=bool(row["show_expense_categories"]),
        show_cost_centers=bool(row["show_cost_centers"]),
        show_due_alerts=bool(row["show_due_alerts"]),
    )
