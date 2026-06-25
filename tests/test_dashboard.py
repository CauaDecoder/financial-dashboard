from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from basilica_financeiro.database import connect, migrate
from basilica_financeiro.repositories.finance import (
    create_category,
    create_cost_center,
    create_financial_account,
    create_payable_receivable_entry,
    record_expense,
    record_revenue,
)
from basilica_financeiro.services.dashboard import (
    get_advanced_dashboard,
    list_custom_dashboards,
    upsert_custom_dashboard,
)


def test_advanced_dashboard_groups_categories_cost_centers_and_alerts(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Caixa",
            account_type="cash",
            opening_balance_cents=0,
            balance_date=date(2026, 6, 1),
            actor_user_id=None,
        )
        revenue_category_id = create_category(
            connection,
            name="Dizimos",
            kind="revenue",
            actor_user_id=None,
        )
        expense_category_id = create_category(
            connection,
            name="Energia",
            kind="expense",
            actor_user_id=None,
        )
        temple_center_id = create_cost_center(
            connection,
            name="Templo",
            actor_user_id=None,
        )
        office_center_id = create_cost_center(
            connection,
            name="Secretaria",
            actor_user_id=None,
        )
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=120_000,
            description="Dizimo domingo",
            effective_date=date(2026, 6, 7),
            category_id=revenue_category_id,
            cost_center_id=temple_center_id,
            actor_user_id=None,
        )
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=30_000,
            description="Dizimo semana",
            effective_date=date(2026, 6, 14),
            category_id=revenue_category_id,
            cost_center_id=office_center_id,
            actor_user_id=None,
        )
        record_expense(
            connection,
            account_id=account_id,
            amount_cents=45_000,
            description="Conta de luz",
            effective_date=date(2026, 6, 15),
            category_id=expense_category_id,
            cost_center_id=temple_center_id,
            actor_user_id=None,
        )
        create_payable_receivable_entry(
            connection,
            entry_type="payable",
            counterparty="Fornecedor",
            description="Energia prevista",
            amount_cents=20_000,
            due_date=date(2026, 6, 18),
            actor_user_id=None,
        )
        create_payable_receivable_entry(
            connection,
            entry_type="receivable",
            counterparty="Fiel",
            description="Promessa",
            amount_cents=15_000,
            due_date=date(2026, 6, 25),
            actor_user_id=None,
        )

        dashboard = get_advanced_dashboard(
            connection,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            today=date(2026, 6, 20),
        )

        assert dashboard.revenue_cents == 150_000
        assert dashboard.expense_cents == 45_000
        assert dashboard.result_cents == 105_000
        assert dashboard.top_revenue_categories[0].category_name == "Dizimos"
        assert dashboard.top_revenue_categories[0].percent == 100
        assert dashboard.top_expense_categories[0].category_name == "Energia"
        assert dashboard.cost_centers[0].cost_center_name == "Templo"
        assert dashboard.cost_centers[0].result_cents == 75_000
        assert dashboard.cost_centers[1].cost_center_name == "Secretaria"
        assert dashboard.cost_centers[1].result_cents == 30_000
        assert len(dashboard.due_alerts) == 2
        assert dashboard.due_alerts[0].effective_status == "overdue"
        assert dashboard.due_alerts[0].days_until_due == -2


def test_advanced_dashboard_validates_period_and_options(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        with pytest.raises(ValueError, match="Data inicial"):
            get_advanced_dashboard(
                connection,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 6, 30),
                today=date(2026, 6, 20),
            )
        with pytest.raises(ValueError, match="Limite"):
            get_advanced_dashboard(
                connection,
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 30),
                today=date(2026, 6, 20),
                limit=0,
            )


def test_custom_dashboard_preferences_are_audited_and_updatable(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        dashboard_id = upsert_custom_dashboard(
            connection,
            name="Gestao mensal",
            period_preset="current_month",
            item_limit=6,
            alert_days=10,
            show_revenue_categories=True,
            show_expense_categories=False,
            show_cost_centers=True,
            show_due_alerts=True,
            actor_user_id=None,
        )
        updated_id = upsert_custom_dashboard(
            connection,
            dashboard_id=dashboard_id,
            name="Gestao mensal revisada",
            period_preset="last_30_days",
            item_limit=4,
            alert_days=5,
            show_revenue_categories=False,
            show_expense_categories=True,
            show_cost_centers=True,
            show_due_alerts=False,
            actor_user_id=None,
        )

        dashboards = list_custom_dashboards(connection)
        audit_actions = [
            row["action"]
            for row in connection.execute(
                "SELECT action FROM audit_log WHERE entity = 'custom_dashboard' ORDER BY id"
            ).fetchall()
        ]

        assert updated_id == dashboard_id
        assert len(dashboards) == 1
        assert dashboards[0].name == "Gestao mensal revisada"
        assert dashboards[0].period_preset == "last_30_days"
        assert dashboards[0].item_limit == 4
        assert dashboards[0].alert_days == 5
        assert dashboards[0].show_revenue_categories is False
        assert dashboards[0].show_expense_categories is True
        assert dashboards[0].show_due_alerts is False
        assert audit_actions == ["create", "update"]


def test_custom_dashboard_validates_required_options(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        with pytest.raises(ValueError, match="Nome"):
            upsert_custom_dashboard(
                connection,
                name=" ",
                period_preset="current_month",
                item_limit=8,
                alert_days=7,
                actor_user_id=None,
            )
        with pytest.raises(ValueError, match="Periodo"):
            upsert_custom_dashboard(
                connection,
                name="Painel",
                period_preset="semana",
                item_limit=8,
                alert_days=7,
                actor_user_id=None,
            )
        with pytest.raises(ValueError, match="Limite"):
            upsert_custom_dashboard(
                connection,
                name="Painel",
                period_preset="current_month",
                item_limit=21,
                alert_days=7,
                actor_user_id=None,
            )
        with pytest.raises(ValueError, match="secao"):
            upsert_custom_dashboard(
                connection,
                name="Painel",
                period_preset="current_month",
                item_limit=8,
                alert_days=7,
                show_revenue_categories=False,
                show_expense_categories=False,
                show_cost_centers=False,
                show_due_alerts=False,
                actor_user_id=None,
            )
