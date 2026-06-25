from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from basilica_financeiro.repositories.audit import record_audit
from basilica_financeiro.services.exports import CellValue, _write_xlsx
from basilica_financeiro.services.money import parse_brl_to_cents
from basilica_financeiro.services.planning import suggest_category_for_description

REQUIRED_HEADERS = ["tipo", "data", "descricao", "valor", "conta", "categoria"]
OPTIONAL_HEADERS = ["centro_custo"]
TEMPLATE_HEADERS = [*REQUIRED_HEADERS, *OPTIONAL_HEADERS]
DUE_REQUIRED_HEADERS = ["tipo", "vencimento", "contraparte", "descricao", "valor", "categoria"]
DUE_OPTIONAL_HEADERS = ["conta", "centro_custo", "observacoes"]
DUE_TEMPLATE_HEADERS = [*DUE_REQUIRED_HEADERS, *DUE_OPTIONAL_HEADERS]


@dataclass(frozen=True)
class ImportRow:
    line_number: int
    transaction_type: str
    effective_date: date
    description: str
    amount_cents: int
    account_id: int
    category_id: int
    category_name: str
    cost_center_id: int | None
    cost_center_name: str | None
    categorization_source: str
    external_id: str


@dataclass(frozen=True)
class DueEntryImportRow:
    line_number: int
    entry_type: str
    due_date: date
    counterparty: str
    description: str
    amount_cents: int
    account_id: int | None
    category_id: int
    category_name: str
    cost_center_id: int | None
    cost_center_name: str | None
    categorization_source: str
    notes: str | None
    external_id: str


@dataclass(frozen=True)
class ImportErrorItem:
    line_number: int
    message: str


@dataclass(frozen=True)
class ImportPreview:
    valid_rows: list[ImportRow]
    errors: list[ImportErrorItem]
    duplicate_count: int


@dataclass(frozen=True)
class DueEntryImportPreview:
    valid_rows: list[DueEntryImportRow]
    errors: list[ImportErrorItem]
    duplicate_count: int


@dataclass(frozen=True)
class ImportResult:
    imported_count: int
    skipped_duplicates: int


def preview_financial_import(
    connection: sqlite3.Connection,
    *,
    source_path: Path,
    column_mapping: dict[str, str] | None = None,
) -> ImportPreview:
    raw_rows = _read_rows(source_path)
    if not raw_rows:
        return ImportPreview(
            valid_rows=[],
            errors=[ImportErrorItem(1, "Arquivo vazio")],
            duplicate_count=0,
        )
    headers = _apply_column_mapping(_normalize_headers(raw_rows[0]), column_mapping)
    missing = [header for header in REQUIRED_HEADERS if header not in headers]
    if missing:
        return ImportPreview(
            valid_rows=[],
            errors=[ImportErrorItem(1, f"Colunas obrigatorias ausentes: {', '.join(missing)}")],
            duplicate_count=0,
        )
    valid_rows = []
    errors = []
    seen_external_ids: set[str] = set()
    duplicate_count = 0
    existing_external_ids = _existing_external_ids(connection)
    for line_number, raw_row in enumerate(raw_rows[1:], start=2):
        if _row_is_empty(raw_row):
            continue
        row = _row_dict(headers, raw_row)
        try:
            import_row = _parse_import_row(connection, row=row, line_number=line_number)
        except ValueError as exc:
            errors.append(ImportErrorItem(line_number, str(exc)))
            continue
        if (
            import_row.external_id in existing_external_ids
            or import_row.external_id in seen_external_ids
        ):
            duplicate_count += 1
            continue
        seen_external_ids.add(import_row.external_id)
        valid_rows.append(import_row)
    return ImportPreview(valid_rows=valid_rows, errors=errors, duplicate_count=duplicate_count)


def import_financial_transactions(
    connection: sqlite3.Connection,
    *,
    source_path: Path,
    actor_user_id: int | None,
    column_mapping: dict[str, str] | None = None,
) -> ImportResult:
    preview = preview_financial_import(
        connection,
        source_path=source_path,
        column_mapping=column_mapping,
    )
    if preview.errors:
        raise ValueError(f"Importacao contem {len(preview.errors)} erro(s) de validacao")
    imported_count = 0
    connection.execute("BEGIN")
    try:
        for row in preview.valid_rows:
            _insert_imported_transaction(
                connection,
                row=row,
                actor_user_id=actor_user_id,
            )
            imported_count += 1
    except Exception:
        connection.rollback()
        raise
    record_audit(
        connection,
        user_id=actor_user_id,
        action="import",
        entity="financial_transaction",
        entity_id=str(source_path.name),
        before=None,
        after={"imported_count": imported_count, "duplicate_count": preview.duplicate_count},
        origin="local",
        result="success",
    )
    return ImportResult(
        imported_count=imported_count,
        skipped_duplicates=preview.duplicate_count,
    )


def preview_due_entries_import(
    connection: sqlite3.Connection,
    *,
    source_path: Path,
    column_mapping: dict[str, str] | None = None,
) -> DueEntryImportPreview:
    raw_rows = _read_rows(source_path)
    if not raw_rows:
        return DueEntryImportPreview(
            valid_rows=[],
            errors=[ImportErrorItem(1, "Arquivo vazio")],
            duplicate_count=0,
        )
    headers = _apply_column_mapping(_normalize_headers(raw_rows[0]), column_mapping)
    missing = [header for header in DUE_REQUIRED_HEADERS if header not in headers]
    if missing:
        return DueEntryImportPreview(
            valid_rows=[],
            errors=[ImportErrorItem(1, f"Colunas obrigatorias ausentes: {', '.join(missing)}")],
            duplicate_count=0,
        )
    valid_rows = []
    errors = []
    seen_external_ids: set[str] = set()
    duplicate_count = 0
    existing_external_ids = _existing_due_entry_external_ids(connection)
    for line_number, raw_row in enumerate(raw_rows[1:], start=2):
        if _row_is_empty(raw_row):
            continue
        row = _row_dict(headers, raw_row)
        try:
            import_row = _parse_due_entry_import_row(
                connection,
                row=row,
                line_number=line_number,
            )
        except ValueError as exc:
            errors.append(ImportErrorItem(line_number, str(exc)))
            continue
        if (
            import_row.external_id in existing_external_ids
            or import_row.external_id in seen_external_ids
        ):
            duplicate_count += 1
            continue
        seen_external_ids.add(import_row.external_id)
        valid_rows.append(import_row)
    return DueEntryImportPreview(
        valid_rows=valid_rows,
        errors=errors,
        duplicate_count=duplicate_count,
    )


def import_due_entries(
    connection: sqlite3.Connection,
    *,
    source_path: Path,
    actor_user_id: int | None,
    column_mapping: dict[str, str] | None = None,
) -> ImportResult:
    preview = preview_due_entries_import(
        connection,
        source_path=source_path,
        column_mapping=column_mapping,
    )
    if preview.errors:
        raise ValueError(f"Importacao contem {len(preview.errors)} erro(s) de validacao")
    imported_count = 0
    connection.execute("BEGIN")
    try:
        for row in preview.valid_rows:
            _insert_imported_due_entry(connection, row=row, actor_user_id=actor_user_id)
            imported_count += 1
    except Exception:
        connection.rollback()
        raise
    record_audit(
        connection,
        user_id=actor_user_id,
        action="import",
        entity="payable_receivable_entry",
        entity_id=str(source_path.name),
        before=None,
        after={"imported_count": imported_count, "duplicate_count": preview.duplicate_count},
        origin="local",
        result="success",
    )
    return ImportResult(
        imported_count=imported_count,
        skipped_duplicates=preview.duplicate_count,
    )


def read_import_headers(source_path: Path) -> list[str]:
    raw_rows = _read_rows(source_path)
    if not raw_rows:
        raise ValueError("Arquivo vazio")
    return [header.strip() for header in raw_rows[0]]


def export_import_template_csv(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(TEMPLATE_HEADERS)
        writer.writerow(
            ["receita", "2026-06-16", "Exemplo de oferta", "100,00", "Caixa", "Oferta", "Matriz"]
        )
    return output_path


def export_import_template_xlsx(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    template_headers: list[CellValue] = list(TEMPLATE_HEADERS)
    _write_xlsx(
        output_path,
        [
            (
                "Importacao",
                [
                    template_headers,
                    [
                        "receita",
                        "2026-06-16",
                        "Exemplo de oferta",
                        "100,00",
                        "Caixa",
                        "Oferta",
                        "Matriz",
                    ],
                ],
            )
        ],
    )
    return output_path


def export_due_entries_template_csv(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(DUE_TEMPLATE_HEADERS)
        writer.writerow(
            [
                "receivable",
                "2026-06-20",
                "Comunidade",
                "Doacao prometida",
                "250,00",
                "Oferta",
                "Caixa",
                "Matriz",
                "Importacao inicial",
            ]
        )
    return output_path


def export_due_entries_template_xlsx(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    template_headers: list[CellValue] = list(DUE_TEMPLATE_HEADERS)
    _write_xlsx(
        output_path,
        [
            (
                "Titulos",
                [
                    template_headers,
                    [
                        "receivable",
                        "2026-06-20",
                        "Comunidade",
                        "Doacao prometida",
                        "250,00",
                        "Oferta",
                        "Caixa",
                        "Matriz",
                        "Importacao inicial",
                    ],
                ],
            )
        ],
    )
    return output_path


def export_import_error_report_csv(
    output_path: Path,
    preview: ImportPreview | DueEntryImportPreview,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["linha", "erro"])
        for error in preview.errors:
            writer.writerow([error.line_number, error.message])
        if preview.duplicate_count:
            writer.writerow(["", f"Duplicatas ignoradas: {preview.duplicate_count}"])
    return output_path


def export_import_categorization_report_csv(
    output_path: Path,
    preview: ImportPreview | DueEntryImportPreview,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "linha",
                "tipo",
                "data",
                "descricao",
                "valor_centavos",
                "categoria",
                "centro_custo",
                "origem_categorizacao",
            ]
        )
        for row in preview.valid_rows:
            if isinstance(row, ImportRow):
                row_type = row.transaction_type
                row_date = row.effective_date.isoformat()
            else:
                row_type = row.entry_type
                row_date = row.due_date.isoformat()
            writer.writerow(
                [
                    row.line_number,
                    row_type,
                    row_date,
                    row.description,
                    row.amount_cents,
                    row.category_name,
                    row.cost_center_name or "",
                    row.categorization_source,
                ]
            )
        if preview.duplicate_count:
            writer.writerow(
                ["", "", "", "", "", "", "", f"Duplicatas ignoradas: {preview.duplicate_count}"]
            )
    return output_path


def _read_rows(source_path: Path) -> list[list[str]]:
    suffix = source_path.suffix.lower()
    if suffix == ".csv":
        return _read_csv_rows(source_path)
    if suffix == ".xlsx":
        return _read_xlsx_rows(source_path)
    raise ValueError("Formato de importacao precisa ser .csv ou .xlsx")


def _read_csv_rows(source_path: Path) -> list[list[str]]:
    text = source_path.read_text(encoding="utf-8-sig")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    return [list(row) for row in csv.reader(text.splitlines(), dialect)]


def _read_xlsx_rows(source_path: Path) -> list[list[str]]:
    with ZipFile(source_path) as archive:
        sheet_name = _first_sheet_name(archive)
        shared_strings = _shared_strings(archive)
        xml = archive.read(sheet_name)
    root = _safe_xml_root(xml)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    output = []
    for row in root.findall(".//x:sheetData/x:row", namespace):
        values = []
        for cell in row.findall("x:c", namespace):
            values.append(_cell_text(cell, shared_strings))
        output.append(values)
    return output


def _first_sheet_name(archive: ZipFile) -> str:
    workbook_rels = _safe_xml_root(archive.read("xl/_rels/workbook.xml.rels"))
    namespace = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    relationship = workbook_rels.find("r:Relationship", namespace)
    if relationship is None:
        raise ValueError("Planilha sem aba importavel")
    target = relationship.attrib["Target"]
    return f"xl/{target}" if not target.startswith("/") else target.lstrip("/")


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _safe_xml_root(archive.read("xl/sharedStrings.xml"))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return ["".join(text.itertext()) for text in root.findall(".//x:si", namespace)]


def _cell_text(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find("x:is", namespace)
        return "" if inline is None else "".join(inline.itertext())
    value = cell.find("x:v", namespace)
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        return shared_strings[int(value.text)]
    return value.text


def _normalize_headers(row: list[str]) -> list[str]:
    return [_normalize_header(value) for value in row]


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _apply_column_mapping(
    headers: list[str],
    column_mapping: dict[str, str] | None,
) -> list[str]:
    if not column_mapping:
        return headers
    mapped_by_source = {
        _normalize_header(source): _normalize_header(canonical)
        for canonical, source in column_mapping.items()
        if canonical.strip() and source.strip()
    }
    return [mapped_by_source.get(header, header) for header in headers]


def _row_dict(headers: list[str], row: list[str]) -> dict[str, str]:
    return {
        header: row[index].strip() if index < len(row) else ""
        for index, header in enumerate(headers)
    }


def _row_is_empty(row: list[str]) -> bool:
    return all(not value.strip() for value in row)


def _parse_import_row(
    connection: sqlite3.Connection,
    *,
    row: dict[str, str],
    line_number: int,
) -> ImportRow:
    transaction_type = _parse_transaction_type(row["tipo"])
    effective_date = _parse_date(row["data"])
    description = _required_value(row["descricao"], "descricao")
    amount_cents = parse_brl_to_cents(row["valor"])
    if amount_cents <= 0:
        raise ValueError("Valor precisa ser positivo")
    account_id = _find_account_id(connection, row["conta"])
    category_id, category_name, categorization_source = _resolve_category(
        connection,
        name=row["categoria"],
        transaction_type=transaction_type,
        description=description,
    )
    cost_center_id, cost_center_name = _resolve_cost_center(
        connection,
        name=row.get("centro_custo", ""),
        transaction_type=transaction_type,
        description=description,
        use_suggestion=not row.get("centro_custo"),
    )
    external_id = _external_id(row)
    return ImportRow(
        line_number=line_number,
        transaction_type=transaction_type,
        effective_date=effective_date,
        description=description,
        amount_cents=amount_cents,
        account_id=account_id,
        category_id=category_id,
        category_name=category_name,
        cost_center_id=cost_center_id,
        cost_center_name=cost_center_name,
        categorization_source=categorization_source,
        external_id=external_id,
    )


def _parse_due_entry_import_row(
    connection: sqlite3.Connection,
    *,
    row: dict[str, str],
    line_number: int,
) -> DueEntryImportRow:
    entry_type = _parse_due_entry_type(row["tipo"])
    due_date = _parse_date(row["vencimento"])
    counterparty = _required_value(row["contraparte"], "contraparte")
    description = _required_value(row["descricao"], "descricao")
    amount_cents = parse_brl_to_cents(row["valor"])
    if amount_cents <= 0:
        raise ValueError("Valor precisa ser positivo")
    account_id = _find_account_id(connection, row["conta"]) if row.get("conta") else None
    category_kind = "expense" if entry_type == "payable" else "revenue"
    category_id, category_name, categorization_source = _resolve_category(
        connection,
        name=row["categoria"],
        transaction_type=category_kind,
        description=description,
    )
    cost_center_id, cost_center_name = _resolve_cost_center(
        connection,
        name=row.get("centro_custo", ""),
        transaction_type=category_kind,
        description=description,
        use_suggestion=not row.get("centro_custo"),
    )
    notes = row.get("observacoes", "").strip() or None
    external_id = _due_entry_external_id(row)
    return DueEntryImportRow(
        line_number=line_number,
        entry_type=entry_type,
        due_date=due_date,
        counterparty=counterparty,
        description=description,
        amount_cents=amount_cents,
        account_id=account_id,
        category_id=category_id,
        category_name=category_name,
        cost_center_id=cost_center_id,
        cost_center_name=cost_center_name,
        categorization_source=categorization_source,
        notes=notes,
        external_id=external_id,
    )


def _parse_transaction_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"receita", "revenue"}:
        return "revenue"
    if normalized in {"despesa", "expense"}:
        return "expense"
    raise ValueError("Tipo precisa ser receita ou despesa")


def _parse_due_entry_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"pagar", "payable", "despesa"}:
        return "payable"
    if normalized in {"receber", "receivable", "receita"}:
        return "receivable"
    raise ValueError("Tipo precisa ser pagar ou receber")


def _parse_date(value: str) -> date:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Data precisa ser preenchida")
    if "/" in stripped:
        day, month, year = stripped.split("/")
        return date(int(year), int(month), int(day))
    return date.fromisoformat(stripped)


def _required_value(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} precisa ser preenchido")
    return stripped


def _find_account_id(connection: sqlite3.Connection, name: str) -> int:
    clean_name = _required_value(name, "conta")
    row = connection.execute(
        "SELECT id FROM financial_accounts WHERE name = ?",
        (clean_name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Conta nao encontrada: {clean_name}")
    return int(row["id"])


def _find_cost_center_id(connection: sqlite3.Connection, name: str) -> int:
    cost_center_id, _ = _find_cost_center(connection, name)
    return cost_center_id


def _resolve_category(
    connection: sqlite3.Connection,
    *,
    name: str,
    transaction_type: str,
    description: str,
) -> tuple[int, str, str]:
    if name.strip():
        category_id, category_name = _find_category(connection, name, transaction_type)
        return category_id, category_name, "informada"
    suggestion = suggest_category_for_description(
        connection,
        description=description,
        transaction_type=transaction_type,
    )
    if suggestion is None:
        raise ValueError("categoria precisa ser preenchido ou sugerida por regra local")
    return suggestion.category_id, suggestion.category_name, f"sugerida: {suggestion.keyword}"


def _resolve_cost_center(
    connection: sqlite3.Connection,
    *,
    name: str,
    transaction_type: str,
    description: str,
    use_suggestion: bool,
) -> tuple[int | None, str | None]:
    if name.strip():
        cost_center_id, cost_center_name = _find_cost_center(connection, name)
        return cost_center_id, cost_center_name
    if not use_suggestion:
        return None, None
    suggestion = suggest_category_for_description(
        connection,
        description=description,
        transaction_type=transaction_type,
    )
    if suggestion is None:
        return None, None
    return suggestion.cost_center_id, suggestion.cost_center_name


def _insert_imported_transaction(
    connection: sqlite3.Connection,
    *,
    row: ImportRow,
    actor_user_id: int | None,
) -> None:
    connection.execute(
        """
        INSERT INTO financial_transactions (
            account_id, category_id, cost_center_id, transaction_type, description,
            amount_cents, effective_date, external_id, origin, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'import', ?)
        """,
        (
            row.account_id,
            row.category_id,
            row.cost_center_id,
            row.transaction_type,
            row.description,
            row.amount_cents,
            row.effective_date.isoformat(),
            row.external_id,
            actor_user_id,
        ),
    )
    balance_delta = row.amount_cents if row.transaction_type == "revenue" else -row.amount_cents
    connection.execute(
        """
        UPDATE financial_accounts
        SET current_balance_cents = current_balance_cents + ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (balance_delta, row.account_id),
    )


def _insert_imported_due_entry(
    connection: sqlite3.Connection,
    *,
    row: DueEntryImportRow,
    actor_user_id: int | None,
) -> None:
    connection.execute(
        """
        INSERT INTO payable_receivable_entries (
            entry_type, account_id, category_id, cost_center_id, counterparty,
            description, amount_cents, due_date, notes, external_id, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.entry_type,
            row.account_id,
            row.category_id,
            row.cost_center_id,
            row.counterparty,
            row.description,
            row.amount_cents,
            row.due_date.isoformat(),
            row.notes,
            row.external_id,
            actor_user_id,
        ),
    )


def _find_category_id(
    connection: sqlite3.Connection,
    name: str,
    transaction_type: str,
) -> int:
    category_id, _ = _find_category(connection, name, transaction_type)
    return category_id


def _find_category(
    connection: sqlite3.Connection,
    name: str,
    transaction_type: str,
) -> tuple[int, str]:
    clean_name = _required_value(name, "categoria")
    row = connection.execute(
        "SELECT id, name FROM categories WHERE name = ? AND kind = ?",
        (clean_name, transaction_type),
    ).fetchone()
    if row is None:
        raise ValueError(f"Categoria nao encontrada para o tipo informado: {clean_name}")
    return int(row["id"]), str(row["name"])


def _find_cost_center(connection: sqlite3.Connection, name: str) -> tuple[int, str]:
    clean_name = _required_value(name, "centro_custo")
    row = connection.execute(
        "SELECT id, name FROM cost_centers WHERE name = ?",
        (clean_name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Centro nao encontrado: {clean_name}")
    return int(row["id"]), str(row["name"])


def _existing_external_ids(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["external_id"])
        for row in connection.execute(
            """
            SELECT external_id
            FROM financial_transactions
            WHERE external_id IS NOT NULL
            """
        ).fetchall()
    }


def _existing_due_entry_external_ids(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row["external_id"])
        for row in connection.execute(
            """
            SELECT external_id
            FROM payable_receivable_entries
            WHERE external_id IS NOT NULL
            """
        ).fetchall()
    }


def _external_id(row: dict[str, str]) -> str:
    return _row_external_id(prefix="import", headers=TEMPLATE_HEADERS, row=row)


def _due_entry_external_id(row: dict[str, str]) -> str:
    return _row_external_id(prefix="due-import", headers=DUE_TEMPLATE_HEADERS, row=row)


def _row_external_id(*, prefix: str, headers: list[str], row: dict[str, str]) -> str:
    normalized = "|".join(row.get(header, "").strip().lower() for header in headers)
    return f"{prefix}:{sha256(normalized.encode('utf-8')).hexdigest()}"


def _safe_xml_root(xml: bytes) -> ElementTree.Element:
    lowered = xml[:1024].lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("XML de planilha contem declaracao insegura")
    return ElementTree.fromstring(xml)  # noqa: S314
