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
from basilica_financeiro.services.planning import (
    create_categorization_rule,
    distribute_annual_budget,
    get_annual_goal_comparison,
    get_budget_comparison,
    get_cash_flow_projection,
    list_budgets,
    list_categorization_rules,
    suggest_category_for_description,
    upsert_budget,
)


def test_budget_comparison_includes_budgeted_and_actual_values(tmp_path: Path) -> None:
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
            name="Manutencao",
            kind="expense",
            actor_user_id=None,
        )
        cost_center_id = create_cost_center(
            connection,
            name="Basilica",
            actor_user_id=None,
        )

        upsert_budget(
            connection,
            year=2026,
            month=6,
            category_id=revenue_category_id,
            cost_center_id=cost_center_id,
            amount_cents=100_000,
            actor_user_id=None,
        )
        upsert_budget(
            connection,
            year=2026,
            month=6,
            category_id=expense_category_id,
            cost_center_id=cost_center_id,
            amount_cents=30_000,
            actor_user_id=None,
        )
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=120_000,
            description="Dizimo dominical",
            effective_date=date(2026, 6, 7),
            category_id=revenue_category_id,
            cost_center_id=cost_center_id,
            actor_user_id=None,
        )
        record_expense(
            connection,
            account_id=account_id,
            amount_cents=25_000,
            description="Reparo eletrico",
            effective_date=date(2026, 6, 8),
            category_id=expense_category_id,
            cost_center_id=cost_center_id,
            actor_user_id=None,
        )

        budgets = list_budgets(connection, year=2026, month=6)
        comparison = {
            item.category_name: item
            for item in get_budget_comparison(connection, year=2026, month=6)
        }

        assert len(budgets) == 2
        assert comparison["Dizimos"].budgeted_cents == 100_000
        assert comparison["Dizimos"].actual_cents == 120_000
        assert comparison["Dizimos"].variance_cents == 20_000
        assert comparison["Manutencao"].budgeted_cents == 30_000
        assert comparison["Manutencao"].actual_cents == 25_000
        assert comparison["Manutencao"].variance_cents == -5_000


def test_annual_goal_comparison_groups_budget_and_actuals(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Caixa",
            account_type="cash",
            opening_balance_cents=0,
            balance_date=date(2026, 1, 1),
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
            name="Eventos",
            kind="expense",
            actor_user_id=None,
        )
        extra_category_id = create_category(
            connection,
            name="Doacoes espontaneas",
            kind="revenue",
            actor_user_id=None,
        )
        cost_center_id = create_cost_center(
            connection,
            name="Basilica",
            actor_user_id=None,
        )

        distribute_annual_budget(
            connection,
            year=2026,
            category_id=revenue_category_id,
            cost_center_id=cost_center_id,
            total_amount_cents=1_200_000,
            actor_user_id=None,
        )
        distribute_annual_budget(
            connection,
            year=2026,
            category_id=expense_category_id,
            cost_center_id=cost_center_id,
            total_amount_cents=240_000,
            monthly_weights=[1, 1, 4, 1, 1, 2, 1, 1, 5, 1, 1, 1],
            actor_user_id=None,
        )
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=900_000,
            description="Dizimos acumulados",
            effective_date=date(2026, 9, 30),
            category_id=revenue_category_id,
            cost_center_id=cost_center_id,
            actor_user_id=None,
        )
        record_expense(
            connection,
            account_id=account_id,
            amount_cents=260_000,
            description="Eventos acumulados",
            effective_date=date(2026, 9, 30),
            category_id=expense_category_id,
            cost_center_id=cost_center_id,
            actor_user_id=None,
        )
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=15_000,
            description="Doacao avulsa",
            effective_date=date(2026, 5, 10),
            category_id=extra_category_id,
            actor_user_id=None,
        )

        comparison = {
            item.category_name: item for item in get_annual_goal_comparison(connection, year=2026)
        }

        assert comparison["Dizimos"].target_cents == 1_200_000
        assert comparison["Dizimos"].actual_cents == 900_000
        assert comparison["Dizimos"].variance_cents == -300_000
        assert comparison["Dizimos"].progress_percent == 75
        assert comparison["Eventos"].target_cents == 240_000
        assert comparison["Eventos"].actual_cents == 260_000
        assert comparison["Eventos"].progress_percent == 108
        assert comparison["Doacoes espontaneas"].target_cents == 0
        assert comparison["Doacoes espontaneas"].actual_cents == 15_000
        assert comparison["Doacoes espontaneas"].progress_percent == 0


def test_budget_upsert_updates_existing_month_category_center(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        category_id = create_category(
            connection,
            name="Eventos",
            kind="revenue",
            actor_user_id=None,
        )

        first_id = upsert_budget(
            connection,
            year=2026,
            month=7,
            category_id=category_id,
            amount_cents=50_000,
            actor_user_id=None,
        )
        second_id = upsert_budget(
            connection,
            year=2026,
            month=7,
            category_id=category_id,
            amount_cents=75_000,
            actor_user_id=None,
        )
        budgets = list_budgets(connection, year=2026, month=7)

        assert second_id == first_id
        assert len(budgets) == 1
        assert budgets[0]["amount_cents"] == 75_000


def test_distribute_annual_budget_splits_exact_total_across_months(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        category_id = create_category(
            connection,
            name="Campanhas",
            kind="revenue",
            actor_user_id=None,
        )

        budget_ids = distribute_annual_budget(
            connection,
            year=2026,
            category_id=category_id,
            total_amount_cents=120_005,
            actor_user_id=None,
        )
        budgets = list_budgets(connection, year=2026)
        audit = connection.execute(
            """
            SELECT action, entity
            FROM audit_log
            WHERE entity = 'budget'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        assert len(budget_ids) == 12
        assert len(budgets) == 12
        assert sum(int(row["amount_cents"]) for row in budgets) == 120_005
        amounts_by_month = {int(row["month"]): int(row["amount_cents"]) for row in budgets}
        assert [amounts_by_month[month] for month in range(1, 6)] == [10_001] * 5
        assert [amounts_by_month[month] for month in range(6, 13)] == [10_000] * 7
        assert audit["action"] == "distribute_annual"


def test_distribute_annual_budget_accepts_seasonal_weights(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        category_id = create_category(
            connection,
            name="Eventos",
            kind="expense",
            actor_user_id=None,
        )

        distribute_annual_budget(
            connection,
            year=2026,
            category_id=category_id,
            total_amount_cents=120_000,
            monthly_weights=[1, 1, 4, 1, 1, 2, 1, 1, 5, 1, 1, 1],
            actor_user_id=None,
        )
        budgets = list_budgets(connection, year=2026)
        audit = connection.execute(
            """
            SELECT after_json
            FROM audit_log
            WHERE entity = 'budget' AND action = 'distribute_annual'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        amounts_by_month = {int(row["month"]): int(row["amount_cents"]) for row in budgets}
        assert sum(amounts_by_month.values()) == 120_000
        assert amounts_by_month[3] == 24_000
        assert amounts_by_month[6] == 12_000
        assert amounts_by_month[9] == 30_000
        assert amounts_by_month[1] == 6_000
        assert '"distribution": "seasonal"' in audit["after_json"]


def test_distribute_annual_budget_validates_seasonal_weights(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        category_id = create_category(
            connection,
            name="Campanhas",
            kind="revenue",
            actor_user_id=None,
        )

        with pytest.raises(ValueError, match="12 pesos"):
            distribute_annual_budget(
                connection,
                year=2026,
                category_id=category_id,
                total_amount_cents=120_000,
                monthly_weights=[1, 2, 3],
                actor_user_id=None,
            )
        with pytest.raises(ValueError, match="positivos"):
            distribute_annual_budget(
                connection,
                year=2026,
                category_id=category_id,
                total_amount_cents=120_000,
                monthly_weights=[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1],
                actor_user_id=None,
            )
        with pytest.raises(ValueError, match="positivos"):
            distribute_annual_budget(
                connection,
                year=2026,
                category_id=category_id,
                total_amount_cents=120_000,
                monthly_weights=[0] * 12,
                actor_user_id=None,
            )


def test_cash_flow_projection_uses_open_due_entries(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        create_payable_receivable_entry(
            connection,
            entry_type="receivable",
            counterparty="Festeiro",
            description="Aluguel do salao",
            amount_cents=80_000,
            due_date=date(2026, 6, 20),
            actor_user_id=None,
        )
        create_payable_receivable_entry(
            connection,
            entry_type="payable",
            counterparty="Fornecedor",
            description="Som",
            amount_cents=35_000,
            due_date=date(2026, 6, 21),
            actor_user_id=None,
        )
        paid_id = create_payable_receivable_entry(
            connection,
            entry_type="payable",
            counterparty="Ignorado",
            description="Ja pago",
            amount_cents=10_000,
            due_date=date(2026, 6, 21),
            actor_user_id=None,
        )
        connection.execute(
            "UPDATE payable_receivable_entries SET status = 'paid', paid_amount_cents = 10000 "
            "WHERE id = ?",
            (paid_id,),
        )

        projection = get_cash_flow_projection(
            connection,
            start_date=date(2026, 6, 20),
            end_date=date(2026, 6, 22),
        )

        assert [row.projected_date for row in projection] == [
            date(2026, 6, 20),
            date(2026, 6, 21),
            date(2026, 6, 22),
        ]
        assert projection[0].expected_revenue_cents == 80_000
        assert projection[0].accumulated_cents == 80_000
        assert projection[1].expected_expense_cents == 35_000
        assert projection[1].accumulated_cents == 45_000
        assert projection[2].accumulated_cents == 45_000


def test_categorization_rules_suggest_by_keyword_and_type(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        revenue_category_id = create_category(
            connection,
            name="Ofertas",
            kind="revenue",
            actor_user_id=None,
        )
        expense_category_id = create_category(
            connection,
            name="Energia",
            kind="expense",
            actor_user_id=None,
        )
        cost_center_id = create_cost_center(
            connection,
            name="Templo",
            actor_user_id=None,
        )
        create_categorization_rule(
            connection,
            keyword="enel",
            transaction_type="expense",
            category_id=expense_category_id,
            cost_center_id=cost_center_id,
            priority=200,
            actor_user_id=None,
        )
        create_categorization_rule(
            connection,
            keyword="oferta",
            transaction_type=None,
            category_id=revenue_category_id,
            priority=100,
            actor_user_id=None,
        )

        expense_suggestion = suggest_category_for_description(
            connection,
            description="Pagamento ENEL junho",
            transaction_type="expense",
        )
        revenue_suggestion = suggest_category_for_description(
            connection,
            description="Oferta missa domingo",
            transaction_type="revenue",
        )
        rules = list_categorization_rules(connection)

        assert expense_suggestion is not None
        assert expense_suggestion.category_id == expense_category_id
        assert expense_suggestion.cost_center_id == cost_center_id
        assert revenue_suggestion is not None
        assert revenue_suggestion.category_id == revenue_category_id
        assert [rule["keyword"] for rule in rules] == ["enel", "oferta"]


def test_planning_validates_dates_money_and_category_type(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        expense_category_id = create_category(
            connection,
            name="Material",
            kind="expense",
            actor_user_id=None,
        )

        with pytest.raises(ValueError, match="Mes"):
            upsert_budget(
                connection,
                year=2026,
                month=13,
                category_id=expense_category_id,
                amount_cents=10_000,
                actor_user_id=None,
            )
        with pytest.raises(ValueError, match="positivo"):
            upsert_budget(
                connection,
                year=2026,
                month=6,
                category_id=expense_category_id,
                amount_cents=0,
                actor_user_id=None,
            )
        with pytest.raises(ValueError, match="compativel"):
            create_categorization_rule(
                connection,
                keyword="doacao",
                transaction_type="revenue",
                category_id=expense_category_id,
                actor_user_id=None,
            )
