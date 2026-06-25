from datetime import date
from pathlib import Path

import pytest

from basilica_financeiro.database import connect, migrate
from basilica_financeiro.repositories.finance import (
    cancel_financial_transaction,
    cancel_payable_receivable_entry,
    create_category,
    create_cost_center,
    create_financial_account,
    create_payable_receivable_entry,
    create_payable_receivable_series,
    get_account_balance_cents,
    get_cash_flow_totals,
    get_dashboard_summary,
    list_categories,
    list_cost_centers,
    list_financial_accounts,
    list_financial_transactions,
    list_payable_receivable_entries,
    record_expense,
    record_revenue,
    record_transaction_series,
    record_transfer,
    settle_payable_receivable_entry,
)
from basilica_financeiro.services.money import format_brl_cents, parse_brl_to_cents


def test_revenue_and_expense_update_balance_and_cash_flow(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Caixa Secretaria",
            account_type="cash",
            opening_balance_cents=10_000,
            balance_date=date(2026, 6, 16),
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
            name="Material de escritorio",
            kind="expense",
            actor_user_id=None,
        )
        cost_center_id = create_cost_center(
            connection,
            name="Secretaria",
            actor_user_id=None,
        )

        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=2_500,
            description="Recebimento de dizimo",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
            category_id=revenue_category_id,
            cost_center_id=cost_center_id,
        )
        record_expense(
            connection,
            account_id=account_id,
            amount_cents=750,
            description="Compra de papel",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
            category_id=expense_category_id,
            cost_center_id=cost_center_id,
        )

        totals = get_cash_flow_totals(
            connection,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )

        assert get_account_balance_cents(connection, account_id) == 11_750
        assert totals == {
            "revenue_cents": 2_500,
            "expense_cents": 750,
            "result_cents": 1_750,
        }


def test_transfer_changes_accounts_but_not_cash_flow_result(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        origin_id = create_financial_account(
            connection,
            name="Conta Corrente",
            account_type="checking",
            opening_balance_cents=20_000,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        destination_id = create_financial_account(
            connection,
            name="Caixa Fisico",
            account_type="cash",
            opening_balance_cents=1_000,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )

        transfer_ids = record_transfer(
            connection,
            origin_account_id=origin_id,
            destination_account_id=destination_id,
            amount_cents=5_000,
            description="Saque para caixa",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        totals = get_cash_flow_totals(
            connection,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )

        assert transfer_ids[0] != transfer_ids[1]
        assert get_account_balance_cents(connection, origin_id) == 15_000
        assert get_account_balance_cents(connection, destination_id) == 6_000
        assert totals == {"revenue_cents": 0, "expense_cents": 0, "result_cents": 0}


def test_cancel_financial_transaction_reverses_balance(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Caixa",
            account_type="cash",
            opening_balance_cents=1_000,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        transaction_id = record_revenue(
            connection,
            account_id=account_id,
            amount_cents=2_000,
            description="Oferta duplicada",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
        )

        cancel_financial_transaction(
            connection,
            transaction_id=transaction_id,
            actor_user_id=None,
        )
        totals = get_cash_flow_totals(
            connection,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )

        assert get_account_balance_cents(connection, account_id) == 1_000
        assert totals == {"revenue_cents": 0, "expense_cents": 0, "result_cents": 0}


def test_cancel_transfer_reverses_both_accounts(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        origin_id = create_financial_account(
            connection,
            name="Banco",
            account_type="checking",
            opening_balance_cents=5_000,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        destination_id = create_financial_account(
            connection,
            name="Caixa",
            account_type="cash",
            opening_balance_cents=500,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        transfer_ids = record_transfer(
            connection,
            origin_account_id=origin_id,
            destination_account_id=destination_id,
            amount_cents=1_500,
            description="Saque",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
        )

        cancel_financial_transaction(
            connection,
            transaction_id=transfer_ids[0],
            actor_user_id=None,
        )

        assert get_account_balance_cents(connection, origin_id) == 5_000
        assert get_account_balance_cents(connection, destination_id) == 500


def test_money_values_must_be_integer_cents(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        with pytest.raises(TypeError):
            create_financial_account(
                connection,
                name="Conta invalida",
                account_type="cash",
                opening_balance_cents=10.5,  # type: ignore[arg-type]
                balance_date=date(2026, 6, 16),
                actor_user_id=None,
            )


def test_finance_lists_feed_operational_forms(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Banco Principal",
            account_type="checking",
            opening_balance_cents=0,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        category_id = create_category(
            connection,
            name="Oferta",
            kind="revenue",
            actor_user_id=None,
        )
        cost_center_id = create_cost_center(
            connection,
            name="Matriz",
            actor_user_id=None,
        )
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=123_45,
            description="Oferta dominical",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
            category_id=category_id,
            cost_center_id=cost_center_id,
        )

        assert [row["name"] for row in list_financial_accounts(connection)] == ["Banco Principal"]
        assert [row["name"] for row in list_categories(connection, kind="revenue")] == ["Oferta"]
        assert [row["name"] for row in list_cost_centers(connection)] == ["Matriz"]
        assert [row["description"] for row in list_financial_transactions(connection)] == [
            "Oferta dominical"
        ]


def test_transaction_filters_by_type_category_and_cost_center(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Banco",
            account_type="checking",
            opening_balance_cents=0,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        revenue_category_id = create_category(
            connection,
            name="Doacoes",
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
            name="Matriz",
            actor_user_id=None,
        )
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=10_000,
            description="Doacao",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
            category_id=revenue_category_id,
            cost_center_id=cost_center_id,
        )
        record_expense(
            connection,
            account_id=account_id,
            amount_cents=2_000,
            description="Reparo",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
            category_id=expense_category_id,
        )

        rows = list_financial_transactions(
            connection,
            transaction_type="revenue",
            category_id=revenue_category_id,
            cost_center_id=cost_center_id,
        )

        assert [row["description"] for row in rows] == ["Doacao"]


def test_payable_settlement_creates_expense_and_updates_status(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Banco Principal",
            account_type="checking",
            opening_balance_cents=50_000,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        category_id = create_category(
            connection,
            name="Energia",
            kind="expense",
            actor_user_id=None,
        )
        entry_id = create_payable_receivable_entry(
            connection,
            entry_type="payable",
            counterparty="Concessionaria",
            description="Conta de energia",
            amount_cents=12_000,
            due_date=date(2026, 6, 20),
            actor_user_id=None,
            category_id=category_id,
        )

        settle_payable_receivable_entry(
            connection,
            entry_id=entry_id,
            account_id=account_id,
            amount_cents=5_000,
            settlement_date=date(2026, 6, 18),
            actor_user_id=None,
        )
        rows = list_payable_receivable_entries(connection, today=date(2026, 6, 18))

        assert get_account_balance_cents(connection, account_id) == 45_000
        assert rows[0]["status"] == "partial"
        assert rows[0]["open_amount_cents"] == 7_000


def test_receivable_settlement_creates_revenue_and_dashboard_summary(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Caixa",
            account_type="cash",
            opening_balance_cents=1_000,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        category_id = create_category(
            connection,
            name="Aluguel de sala",
            kind="revenue",
            actor_user_id=None,
        )
        receivable_id = create_payable_receivable_entry(
            connection,
            entry_type="receivable",
            counterparty="Grupo local",
            description="Uso do salao",
            amount_cents=8_000,
            due_date=date(2026, 6, 10),
            actor_user_id=None,
            category_id=category_id,
        )
        create_payable_receivable_entry(
            connection,
            entry_type="payable",
            counterparty="Fornecedor",
            description="Material pendente",
            amount_cents=3_500,
            due_date=date(2026, 6, 1),
            actor_user_id=None,
        )

        settle_payable_receivable_entry(
            connection,
            entry_id=receivable_id,
            account_id=account_id,
            amount_cents=8_000,
            settlement_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        summary = get_dashboard_summary(connection, today=date(2026, 6, 16))
        rows = list_payable_receivable_entries(connection, today=date(2026, 6, 16))

        assert get_account_balance_cents(connection, account_id) == 9_000
        assert summary["balance_cents"] == 9_000
        assert summary["revenue_cents"] == 8_000
        assert summary["open_payables_cents"] == 3_500
        assert summary["overdue_payables_cents"] == 3_500
        assert rows[0]["effective_status"] == "overdue"
        assert rows[1]["status"] == "paid"


def test_cancel_due_entry_removes_open_amount_from_dashboard(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        entry_id = create_payable_receivable_entry(
            connection,
            entry_type="payable",
            counterparty="Fornecedor",
            description="Material",
            amount_cents=3_500,
            due_date=date(2026, 6, 1),
            actor_user_id=None,
        )

        cancel_payable_receivable_entry(
            connection,
            entry_id=entry_id,
            actor_user_id=None,
        )
        summary = get_dashboard_summary(connection, today=date(2026, 6, 16))
        rows = list_payable_receivable_entries(connection, today=date(2026, 6, 16))

        assert summary["open_payables_cents"] == 0
        assert rows[0]["status"] == "canceled"


def test_installment_due_entry_series_splits_cents_and_month_end_dates(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        entry_ids = create_payable_receivable_series(
            connection,
            entry_type="payable",
            counterparty="Fornecedor",
            description="Compra parcelada",
            total_amount_cents=10_000,
            first_due_date=date(2026, 1, 31),
            actor_user_id=None,
            occurrence_count=3,
            mode="installment",
        )
        rows = list_payable_receivable_entries(connection, today=date(2026, 1, 31))

        assert len(entry_ids) == 3
        assert [row["amount_cents"] for row in rows] == [3_333, 3_333, 3_334]
        assert [row["due_date"] for row in rows] == ["2026-01-31", "2026-02-28", "2026-03-31"]
        assert {row["installment_count"] for row in rows} == {3}
        assert {row["recurrence_rule"] for row in rows} == {"installment:monthly"}


def test_due_entry_filters_by_type_category_cost_center_and_status(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        category_id = create_category(
            connection,
            name="Energia",
            kind="expense",
            actor_user_id=None,
        )
        cost_center_id = create_cost_center(
            connection,
            name="Secretaria",
            actor_user_id=None,
        )
        create_payable_receivable_entry(
            connection,
            entry_type="payable",
            counterparty="Concessionaria",
            description="Energia",
            amount_cents=3_000,
            due_date=date(2026, 6, 20),
            actor_user_id=None,
            category_id=category_id,
            cost_center_id=cost_center_id,
        )
        create_payable_receivable_entry(
            connection,
            entry_type="receivable",
            counterparty="Pessoa",
            description="Doacao",
            amount_cents=5_000,
            due_date=date(2026, 6, 20),
            actor_user_id=None,
        )

        rows = list_payable_receivable_entries(
            connection,
            today=date(2026, 6, 16),
            entry_type="payable",
            category_id=category_id,
            cost_center_id=cost_center_id,
            status="open",
        )

        assert [row["description"] for row in rows] == ["Energia"]


def test_recurring_receivable_series_keeps_amount_for_each_occurrence(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        create_payable_receivable_series(
            connection,
            entry_type="receivable",
            counterparty="Locatario",
            description="Aluguel mensal",
            total_amount_cents=4_500,
            first_due_date=date(2026, 6, 10),
            actor_user_id=None,
            occurrence_count=2,
            mode="recurring",
        )
        rows = list_payable_receivable_entries(connection, today=date(2026, 6, 1))

        assert [row["amount_cents"] for row in rows] == [4_500, 4_500]
        assert [row["due_date"] for row in rows] == ["2026-06-10", "2026-07-10"]
        assert {row["recurrence_rule"] for row in rows} == {"recurring:monthly"}


def test_realized_transaction_series_updates_balance_and_cash_flow(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Caixa",
            account_type="cash",
            opening_balance_cents=20_000,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )

        transaction_ids = record_transaction_series(
            connection,
            transaction_type="expense",
            account_id=account_id,
            total_amount_cents=9_999,
            description="Contrato parcelado",
            first_effective_date=date(2026, 6, 16),
            actor_user_id=None,
            occurrence_count=3,
            mode="installment",
        )
        totals = get_cash_flow_totals(
            connection,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
        )

        assert len(transaction_ids) == 3
        assert get_account_balance_cents(connection, account_id) == 10_001
        assert totals["expense_cents"] == 9_999


def test_settlement_cannot_exceed_open_amount(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Caixa",
            account_type="cash",
            opening_balance_cents=0,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        entry_id = create_payable_receivable_entry(
            connection,
            entry_type="receivable",
            counterparty="Pessoa",
            description="Promessa",
            amount_cents=1_000,
            due_date=date(2026, 6, 20),
            actor_user_id=None,
        )

        with pytest.raises(ValueError, match="exceder"):
            settle_payable_receivable_entry(
                connection,
                entry_id=entry_id,
                account_id=account_id,
                amount_cents=1_001,
                settlement_date=date(2026, 6, 16),
                actor_user_id=None,
            )


def test_parse_and_format_brl_cents() -> None:
    assert parse_brl_to_cents("R$ 1.234,56") == 123_456
    assert parse_brl_to_cents("10") == 1_000
    assert parse_brl_to_cents("-1,25") == -125
    assert format_brl_cents(123_456) == "R$ 1.234,56"
