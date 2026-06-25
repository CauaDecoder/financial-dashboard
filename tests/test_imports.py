from datetime import date
from pathlib import Path

import pytest

from basilica_financeiro.database import connect, migrate
from basilica_financeiro.repositories.finance import (
    create_category,
    create_cost_center,
    create_financial_account,
    get_account_balance_cents,
    list_financial_transactions,
    list_payable_receivable_entries,
)
from basilica_financeiro.services.imports import (
    export_due_entries_template_xlsx,
    export_import_categorization_report_csv,
    export_import_error_report_csv,
    export_import_template_xlsx,
    import_due_entries,
    import_financial_transactions,
    preview_due_entries_import,
    preview_financial_import,
    read_import_headers,
)
from basilica_financeiro.services.planning import create_categorization_rule


def test_import_financial_transactions_from_csv_updates_balance(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = _seed_import_catalogs(connection)
        source_path = tmp_path / "importacao.csv"
        source_path.write_text(
            "\n".join(
                [
                    "tipo,data,descricao,valor,conta,categoria,centro_custo",
                    "receita,2026-06-16,Oferta importada,150,00,Caixa,Oferta,Matriz",
                ]
            ).replace("150,00", '"150,00"'),
            encoding="utf-8",
        )

        preview = preview_financial_import(connection, source_path=source_path)
        result = import_financial_transactions(
            connection,
            source_path=source_path,
            actor_user_id=None,
        )

        assert len(preview.valid_rows) == 1
        assert preview.errors == []
        assert result.imported_count == 1
        assert get_account_balance_cents(connection, account_id) == 15_000


def test_import_financial_transactions_skips_duplicate_rows(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        source_path = tmp_path / "importacao.csv"
        row = 'receita,2026-06-16,Oferta repetida,"10,00",Caixa,Oferta,Matriz'
        source_path.write_text(
            "\n".join(["tipo,data,descricao,valor,conta,categoria,centro_custo", row, row]),
            encoding="utf-8",
        )

        result = import_financial_transactions(
            connection,
            source_path=source_path,
            actor_user_id=None,
        )

        assert result.imported_count == 1
        assert result.skipped_duplicates == 1
        assert len(list_financial_transactions(connection)) == 1


def test_import_rejects_errors_without_partial_write(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        source_path = tmp_path / "importacao.csv"
        source_path.write_text(
            "\n".join(
                [
                    "tipo,data,descricao,valor,conta,categoria,centro_custo",
                    'receita,2026-06-16,Oferta importada,"10,00",Caixa,Oferta,Matriz',
                    'despesa,2026-06-17,Despesa invalida,"5,00",Conta inexistente,Oferta,Matriz',
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="validacao"):
            import_financial_transactions(
                connection,
                source_path=source_path,
                actor_user_id=None,
            )

        assert list_financial_transactions(connection) == []


def test_import_template_xlsx_can_be_previewed(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        source_path = export_import_template_xlsx(tmp_path / "template.xlsx")

        preview = preview_financial_import(connection, source_path=source_path)

        assert len(preview.valid_rows) == 1
        assert preview.errors == []


def test_import_accepts_column_mapping_for_non_template_headers(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = _seed_import_catalogs(connection)
        source_path = tmp_path / "importacao-mapeada.csv"
        source_path.write_text(
            "\n".join(
                [
                    "operacao;quando;historico;montante;conta_financeira;plano;centro",
                    "receita;16/06/2026;Oferta mapeada;25,00;Caixa;Oferta;Matriz",
                ]
            ),
            encoding="utf-8",
        )
        mapping = {
            "tipo": "operacao",
            "data": "quando",
            "descricao": "historico",
            "valor": "montante",
            "conta": "conta_financeira",
            "categoria": "plano",
            "centro_custo": "centro",
        }

        preview = preview_financial_import(
            connection,
            source_path=source_path,
            column_mapping=mapping,
        )
        result = import_financial_transactions(
            connection,
            source_path=source_path,
            actor_user_id=None,
            column_mapping=mapping,
        )

        assert len(preview.valid_rows) == 1
        assert preview.errors == []
        assert result.imported_count == 1
        assert get_account_balance_cents(connection, account_id) == 2_500


def test_import_financial_transactions_suggests_blank_category_from_rules(
    tmp_path: Path,
) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        category_id = _category_id(connection, "Oferta", "revenue")
        cost_center_id = _cost_center_id(connection, "Matriz")
        create_categorization_rule(
            connection,
            keyword="campanha",
            transaction_type="revenue",
            category_id=category_id,
            cost_center_id=cost_center_id,
            actor_user_id=None,
        )
        source_path = tmp_path / "importacao-sugerida.csv"
        source_path.write_text(
            "\n".join(
                [
                    "tipo,data,descricao,valor,conta,categoria,centro_custo",
                    'receita,2026-06-16,Campanha de alimentos,"30,00",Caixa,,',
                ]
            ),
            encoding="utf-8",
        )

        preview = preview_financial_import(connection, source_path=source_path)
        result = import_financial_transactions(
            connection,
            source_path=source_path,
            actor_user_id=None,
        )
        transaction = list_financial_transactions(connection)[0]

        assert preview.errors == []
        assert preview.valid_rows[0].category_id == category_id
        assert preview.valid_rows[0].cost_center_id == cost_center_id
        assert preview.valid_rows[0].categorization_source == "sugerida: campanha"
        assert result.imported_count == 1
        assert transaction["category_name"] == "Oferta"
        assert transaction["cost_center_name"] == "Matriz"


def test_read_import_headers_returns_first_row_values(tmp_path: Path) -> None:
    source_path = tmp_path / "cabecalhos.csv"
    source_path.write_text(
        " Operacao ; Quando ; Valor \nreceita;2026-06-16;10,00",
        encoding="utf-8",
    )

    assert read_import_headers(source_path) == ["Operacao", "Quando", "Valor"]


def test_export_import_error_report_csv_contains_line_numbers(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        source_path = tmp_path / "importacao-com-erros.csv"
        source_path.write_text(
            "\n".join(
                [
                    "tipo,data,descricao,valor,conta,categoria,centro_custo",
                    'receita,2026-06-16,Oferta valida,"10,00",Caixa,Oferta,Matriz',
                    'despesa,2026-06-17,Despesa invalida,"5,00",Conta X,Manutencao,Matriz',
                ]
            ),
            encoding="utf-8",
        )

        preview = preview_financial_import(connection, source_path=source_path)
        report_path = export_import_error_report_csv(tmp_path / "erros.csv", preview)

        report_text = report_path.read_text(encoding="utf-8")
        assert "linha,erro" in report_text
        assert "3," in report_text
        assert "Conta nao encontrada: Conta X" in report_text


def test_export_import_categorization_report_csv_marks_suggested_rows(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        category_id = _category_id(connection, "Oferta", "revenue")
        create_categorization_rule(
            connection,
            keyword="campanha",
            transaction_type="revenue",
            category_id=category_id,
            actor_user_id=None,
        )
        source_path = tmp_path / "importacao-sugerida.csv"
        source_path.write_text(
            "\n".join(
                [
                    "tipo,data,descricao,valor,conta,categoria,centro_custo",
                    'receita,2026-06-16,Campanha de alimentos,"30,00",Caixa,,',
                    'receita,2026-06-17,Oferta informada,"20,00",Caixa,Oferta,',
                ]
            ),
            encoding="utf-8",
        )

        preview = preview_financial_import(connection, source_path=source_path)
        report_path = export_import_categorization_report_csv(
            tmp_path / "categorias.csv",
            preview,
        )
        report_text = report_path.read_text(encoding="utf-8")

        assert "linha,tipo,data,descricao,valor_centavos,categoria,centro_custo" in report_text
        suggested_line = (
            "2,revenue,2026-06-16,Campanha de alimentos,3000,Oferta,,sugerida: campanha"
        )
        assert suggested_line in report_text
        assert "3,revenue,2026-06-17,Oferta informada,2000,Oferta,,informada" in report_text


def test_import_due_entries_from_csv_creates_open_titles_without_balance_change(
    tmp_path: Path,
) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = _seed_import_catalogs(connection)
        source_path = tmp_path / "titulos.csv"
        source_path.write_text(
            "\n".join(
                [
                    "tipo,vencimento,contraparte,descricao,valor,categoria,conta,centro_custo,observacoes",
                    'receber,2026-06-20,Comunidade,Doacao prometida,"50,00",'
                    "Oferta,Caixa,Matriz,Promessa",
                    'pagar,21/06/2026,Fornecedor,Manutencao prevista,"30,00",'
                    "Manutencao,Caixa,Matriz,",
                ]
            ),
            encoding="utf-8",
        )

        preview = preview_due_entries_import(connection, source_path=source_path)
        result = import_due_entries(connection, source_path=source_path, actor_user_id=None)
        entries = list_payable_receivable_entries(connection, today=date(2026, 6, 16))

        assert len(preview.valid_rows) == 2
        assert preview.errors == []
        assert result.imported_count == 2
        assert result.skipped_duplicates == 0
        assert len(entries) == 2
        assert {entry["entry_type"] for entry in entries} == {"receivable", "payable"}
        assert get_account_balance_cents(connection, account_id) == 0


def test_import_due_entries_skips_duplicate_rows(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        source_path = tmp_path / "titulos-duplicados.csv"
        row = 'receber,2026-06-20,Comunidade,Doacao prometida,"50,00",Oferta,Caixa,Matriz,'
        source_path.write_text(
            "\n".join(
                [
                    "tipo,vencimento,contraparte,descricao,valor,categoria,conta,centro_custo,observacoes",
                    row,
                    row,
                ]
            ),
            encoding="utf-8",
        )

        result = import_due_entries(connection, source_path=source_path, actor_user_id=None)

        assert result.imported_count == 1
        assert result.skipped_duplicates == 1
        assert len(list_payable_receivable_entries(connection, today=date(2026, 6, 16))) == 1


def test_import_due_entries_suggests_blank_category_from_rules(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        category_id = _category_id(connection, "Manutencao", "expense")
        cost_center_id = _cost_center_id(connection, "Matriz")
        create_categorization_rule(
            connection,
            keyword="eletrica",
            transaction_type="expense",
            category_id=category_id,
            cost_center_id=cost_center_id,
            actor_user_id=None,
        )
        source_path = tmp_path / "titulos-sugeridos.csv"
        source_path.write_text(
            "\n".join(
                [
                    "tipo,vencimento,contraparte,descricao,valor,categoria,conta,centro_custo,observacoes",
                    'pagar,2026-06-21,Fornecedor,Manutencao eletrica,"30,00",,Caixa,,',
                ]
            ),
            encoding="utf-8",
        )

        preview = preview_due_entries_import(connection, source_path=source_path)
        result = import_due_entries(connection, source_path=source_path, actor_user_id=None)
        entry = list_payable_receivable_entries(connection, today=date(2026, 6, 16))[0]

        assert preview.errors == []
        assert preview.valid_rows[0].category_id == category_id
        assert preview.valid_rows[0].cost_center_id == cost_center_id
        assert preview.valid_rows[0].categorization_source == "sugerida: eletrica"
        assert result.imported_count == 1
        assert entry["category_name"] == "Manutencao"
        assert entry["cost_center_name"] == "Matriz"


def test_export_due_entry_categorization_report_csv_marks_suggested_rows(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        category_id = _category_id(connection, "Manutencao", "expense")
        create_categorization_rule(
            connection,
            keyword="eletrica",
            transaction_type="expense",
            category_id=category_id,
            actor_user_id=None,
        )
        source_path = tmp_path / "titulos-sugeridos.csv"
        source_path.write_text(
            "\n".join(
                [
                    "tipo,vencimento,contraparte,descricao,valor,categoria,conta,centro_custo,observacoes",
                    'pagar,2026-06-21,Fornecedor,Manutencao eletrica,"30,00",,Caixa,,',
                ]
            ),
            encoding="utf-8",
        )

        preview = preview_due_entries_import(connection, source_path=source_path)
        report_path = export_import_categorization_report_csv(
            tmp_path / "categorias-titulos.csv",
            preview,
        )
        report_text = report_path.read_text(encoding="utf-8")

        suggested_line = (
            "2,payable,2026-06-21,Manutencao eletrica,3000,Manutencao,,sugerida: eletrica"
        )
        assert suggested_line in report_text


def test_import_due_entries_rejects_errors_without_partial_write(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        source_path = tmp_path / "titulos-com-erros.csv"
        source_path.write_text(
            "\n".join(
                [
                    "tipo,vencimento,contraparte,descricao,valor,categoria,conta,centro_custo,observacoes",
                    'receber,2026-06-20,Comunidade,Doacao prometida,"50,00",Oferta,Caixa,Matriz,',
                    'pagar,2026-06-21,Fornecedor,Despesa invalida,"30,00",'
                    "Categoria X,Caixa,Matriz,",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="validacao"):
            import_due_entries(connection, source_path=source_path, actor_user_id=None)

        assert list_payable_receivable_entries(connection, today=date(2026, 6, 16)) == []


def test_due_entry_template_xlsx_can_be_previewed(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        _seed_import_catalogs(connection)
        source_path = export_due_entries_template_xlsx(tmp_path / "template-titulos.xlsx")

        preview = preview_due_entries_import(connection, source_path=source_path)

        assert len(preview.valid_rows) == 1
        assert preview.errors == []


def _seed_import_catalogs(connection) -> int:
    account_id = create_financial_account(
        connection,
        name="Caixa",
        account_type="cash",
        opening_balance_cents=0,
        balance_date=date(2026, 6, 16),
        actor_user_id=None,
    )
    create_category(
        connection,
        name="Oferta",
        kind="revenue",
        actor_user_id=None,
    )
    create_category(
        connection,
        name="Manutencao",
        kind="expense",
        actor_user_id=None,
    )
    create_cost_center(
        connection,
        name="Matriz",
        actor_user_id=None,
    )
    return account_id


def _category_id(connection, name: str, kind: str) -> int:
    row = connection.execute(
        "SELECT id FROM categories WHERE name = ? AND kind = ?",
        (name, kind),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def _cost_center_id(connection, name: str) -> int:
    row = connection.execute("SELECT id FROM cost_centers WHERE name = ?", (name,)).fetchone()
    assert row is not None
    return int(row["id"])
