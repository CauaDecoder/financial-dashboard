from datetime import date
from pathlib import Path
from zipfile import ZipFile

import pytest

from basilica_financeiro.database import connect, migrate
from basilica_financeiro.repositories.finance import (
    create_category,
    create_financial_account,
    create_payable_receivable_entry,
    record_revenue,
)
from basilica_financeiro.services.exports import (
    export_financial_report_csv,
    export_financial_report_pdf,
    export_financial_report_xlsx,
)


def test_export_financial_report_xlsx_contains_summary_flow_and_due_entries(
    tmp_path: Path,
) -> None:
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
            name="Oferta",
            kind="revenue",
            actor_user_id=None,
        )
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=2_500,
            description="Oferta dominical",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
            category_id=category_id,
        )
        create_payable_receivable_entry(
            connection,
            entry_type="receivable",
            counterparty="Comunidade",
            description="Doacao prometida",
            amount_cents=5_000,
            due_date=date(2026, 6, 20),
            actor_user_id=None,
            category_id=category_id,
        )

        output_path = export_financial_report_xlsx(
            connection,
            output_path=tmp_path / "relatorio.xlsx",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )

    with ZipFile(output_path) as archive:
        names = set(archive.namelist())
        flow_sheet = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
        due_sheet = archive.read("xl/worksheets/sheet3.xml").decode("utf-8")

    assert "xl/workbook.xml" in names
    assert "Oferta dominical" in flow_sheet
    assert "Doacao prometida" in due_sheet


def test_export_financial_report_rejects_invalid_period(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        with pytest.raises(ValueError, match="Data inicial"):
            export_financial_report_xlsx(
                connection,
                output_path=tmp_path / "relatorio.xlsx",
                start_date=date(2026, 7, 1),
                end_date=date(2026, 6, 30),
            )


def test_export_financial_report_csv_uses_brazilian_formatting(tmp_path: Path) -> None:
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
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=12_345,
            description="Oferta CSV",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
        )

        output_path = export_financial_report_csv(
            connection,
            output_path=tmp_path / "relatorio.csv",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )

    content = output_path.read_text(encoding="utf-8-sig")

    assert "Periodo;2026-06-01 a 2026-06-30" in content
    assert "Oferta CSV" in content
    assert "R$ 123,45" in content


def test_export_financial_report_pdf_has_institutional_header(tmp_path: Path) -> None:
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
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=1_500,
            description="Oferta semanal",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
        )

        output_path = export_financial_report_pdf(
            connection,
            output_path=tmp_path / "relatorio.pdf",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )

    content = output_path.read_bytes()

    assert content.startswith(b"%PDF-1.4")
    assert b"Basilica Menor Nossa Senhora das Dores" in content
    assert b"Oferta semanal" in content
