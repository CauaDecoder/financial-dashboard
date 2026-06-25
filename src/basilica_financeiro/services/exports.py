from __future__ import annotations

import csv
import sqlite3
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from basilica_financeiro.repositories.finance import (
    get_cash_flow_totals,
    list_payable_receivable_entries,
)
from basilica_financeiro.services.money import format_brl_cents

CellValue = str | int
PDF_PAGE_LINES = 48


def export_financial_report_xlsx(
    connection: sqlite3.Connection,
    *,
    output_path: Path,
    start_date: date,
    end_date: date,
) -> Path:
    if start_date > end_date:
        raise ValueError("Data inicial nao pode ser maior que a data final")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheets = [
        ("Resumo", _summary_rows(connection, start_date=start_date, end_date=end_date)),
        ("Fluxo", _cash_flow_rows(connection, start_date=start_date, end_date=end_date)),
        ("Titulos", _due_entry_rows(connection, end_date=end_date)),
    ]
    _write_xlsx(output_path, sheets)
    return output_path


def export_financial_report_csv(
    connection: sqlite3.Connection,
    *,
    output_path: Path,
    start_date: date,
    end_date: date,
) -> Path:
    if start_date > end_date:
        raise ValueError("Data inicial nao pode ser maior que a data final")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheets = [
        ("Resumo", _summary_rows(connection, start_date=start_date, end_date=end_date)),
        ("Fluxo de caixa", _cash_flow_rows(connection, start_date=start_date, end_date=end_date)),
        ("Contas a pagar e receber", _due_entry_rows(connection, end_date=end_date)),
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(["Basilica Menor Nossa Senhora das Dores"])
        writer.writerow(["Relatorio financeiro"])
        writer.writerow(["Periodo", f"{start_date.isoformat()} a {end_date.isoformat()}"])
        writer.writerow([])
        for title, rows in sheets:
            writer.writerow([title])
            writer.writerows(rows)
            writer.writerow([])
    return output_path


def export_financial_report_pdf(
    connection: sqlite3.Connection,
    *,
    output_path: Path,
    start_date: date,
    end_date: date,
) -> Path:
    if start_date > end_date:
        raise ValueError("Data inicial nao pode ser maior que a data final")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = _report_lines(connection, start_date=start_date, end_date=end_date)
    _write_pdf(output_path, lines)
    return output_path


def _summary_rows(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
) -> list[list[CellValue]]:
    totals = get_cash_flow_totals(connection, start_date=start_date, end_date=end_date)
    balance_row = connection.execute(
        "SELECT COALESCE(SUM(current_balance_cents), 0) AS total FROM financial_accounts"
    ).fetchone()
    balance = int(balance_row["total"]) if balance_row is not None else 0
    return [
        ["Indicador", "Valor"],
        ["Periodo inicial", start_date.isoformat()],
        ["Periodo final", end_date.isoformat()],
        ["Saldo total em contas", format_brl_cents(balance)],
        ["Receitas no periodo", format_brl_cents(totals["revenue_cents"])],
        ["Despesas no periodo", format_brl_cents(totals["expense_cents"])],
        ["Resultado no periodo", format_brl_cents(totals["result_cents"])],
    ]


def _report_lines(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
) -> list[str]:
    lines = [
        "Basilica Menor Nossa Senhora das Dores",
        "Relatorio financeiro",
        f"Periodo: {start_date.isoformat()} a {end_date.isoformat()}",
        "",
        "Resumo",
    ]
    summary_rows = _summary_rows(connection, start_date=start_date, end_date=end_date)
    lines.extend(_row_to_line(row) for row in summary_rows)
    lines.extend(["", "Fluxo de caixa"])
    cash_flow_rows = _cash_flow_rows(connection, start_date=start_date, end_date=end_date)
    lines.extend(_row_to_line(row) for row in cash_flow_rows)
    lines.extend(["", "Contas a pagar e receber"])
    lines.extend(_row_to_line(row) for row in _due_entry_rows(connection, end_date=end_date))
    return lines


def _cash_flow_rows(
    connection: sqlite3.Connection,
    *,
    start_date: date,
    end_date: date,
) -> list[list[CellValue]]:
    rows = connection.execute(
        """
        SELECT
            t.effective_date,
            t.transaction_type,
            t.description,
            t.amount_cents,
            a.name AS account_name,
            c.name AS category_name,
            cc.name AS cost_center_name
        FROM financial_transactions t
        JOIN financial_accounts a ON a.id = t.account_id
        LEFT JOIN categories c ON c.id = t.category_id
        LEFT JOIN cost_centers cc ON cc.id = t.cost_center_id
        WHERE t.effective_date BETWEEN ? AND ?
          AND t.status = 'posted'
        ORDER BY t.effective_date, t.id
        """,
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    output: list[list[CellValue]] = [
        ["Data", "Tipo", "Descricao", "Valor", "Conta", "Categoria", "Centro de custo"]
    ]
    for row in rows:
        output.append(
            [
                str(row["effective_date"]),
                str(row["transaction_type"]),
                str(row["description"]),
                format_brl_cents(int(row["amount_cents"])),
                str(row["account_name"]),
                "" if row["category_name"] is None else str(row["category_name"]),
                "" if row["cost_center_name"] is None else str(row["cost_center_name"]),
            ]
        )
    return output


def _due_entry_rows(connection: sqlite3.Connection, *, end_date: date) -> list[list[CellValue]]:
    rows = list_payable_receivable_entries(connection, today=end_date)
    output: list[list[CellValue]] = [
        [
            "ID",
            "Tipo",
            "Vencimento",
            "Status",
            "Pessoa",
            "Descricao",
            "Valor",
            "Pago",
            "Aberto",
            "Conta",
        ]
    ]
    for row in rows:
        output.append(
            [
                _dict_int(row, "id"),
                str(row["entry_type"]),
                str(row["due_date"]),
                str(row["effective_status"]),
                str(row["counterparty"]),
                str(row["description"]),
                format_brl_cents(_dict_int(row, "amount_cents")),
                format_brl_cents(_dict_int(row, "paid_amount_cents")),
                format_brl_cents(_dict_int(row, "open_amount_cents")),
                "" if row["account_name"] is None else str(row["account_name"]),
            ]
        )
    return output


def _write_xlsx(output_path: Path, sheets: list[tuple[str, list[list[CellValue]]]]) -> None:
    with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(len(sheets)))
        archive.writestr("_rels/.rels", _root_rels())
        archive.writestr("xl/workbook.xml", _workbook(sheets))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels(len(sheets)))
        archive.writestr("xl/styles.xml", _styles())
        for index, (_, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet(rows))


def _write_pdf(output_path: Path, lines: list[str]) -> None:
    pages = [
        lines[index : index + PDF_PAGE_LINES]
        for index in range(0, max(len(lines), 1), PDF_PAGE_LINES)
    ]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
    ]
    page_object_numbers: list[int] = []
    for page_lines in pages:
        page_object_number = len(objects) + 1
        content_object_number = page_object_number + 1
        page_object_numbers.append(page_object_number)
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {len(pages) * 2 + 3} 0 R >> >> "
                f"/Contents {content_object_number} 0 R >>"
            ).encode("ascii")
        )
        content = _pdf_page_content(page_lines)
        objects.append(
            b"<< /Length "
            + str(len(content)).encode("ascii")
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_numbers)} >>".encode(
        "ascii"
    )
    _write_pdf_objects(output_path, objects)


def _pdf_page_content(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 10 Tf", "13 TL", "50 800 Td"]
    for line in lines:
        commands.append(f"({_pdf_escape(line[:115])}) Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def _write_pdf_objects(output_path: Path, objects: list[bytes]) -> None:
    buffer = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, content in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer.extend(f"{index} 0 obj\n".encode("ascii"))
        buffer.extend(content)
        buffer.extend(b"\nendobj\n")
    xref_offset = len(buffer)
    buffer.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    buffer.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    output_path.write_bytes(bytes(buffer))


def _worksheet(rows: list[list[CellValue]]) -> str:
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            reference = f"{_column_name(column_index)}{row_index}"
            cell_value = escape(str(value))
            cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{cell_value}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )


def _row_to_line(row: list[CellValue]) -> str:
    return " | ".join(str(value) for value in row)


def _pdf_escape(value: str) -> str:
    sanitized = value.encode("latin-1", errors="replace").decode("latin-1")
    return sanitized.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content_types(sheet_count: int) -> str:
    sheet_overrides = "".join(
        (
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.worksheet+xml"/>'
        )
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{sheet_overrides}</Types>"
    )


def _root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook(sheets: list[tuple[str, list[list[CellValue]]]]) -> str:
    sheet_nodes = []
    for index, (name, _) in enumerate(sheets, start=1):
        sheet_nodes.append(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{''.join(sheet_nodes)}</sheets>"
        "</workbook>"
    )


def _workbook_rels(sheet_count: int) -> str:
    relationships = []
    for index in range(1, sheet_count + 1):
        relationships.append(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            f'worksheet" Target="worksheets/sheet{index}.xml"/>'
        )
    relationships.append(
        f'<Relationship Id="rId{sheet_count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(relationships)}</Relationships>"
    )


def _styles() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" '
        'borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" '
        'xfId="0"/></cellXfs>'
        "</styleSheet>"
    )


def _column_name(column_index: int) -> str:
    name = ""
    while column_index:
        column_index, remainder = divmod(column_index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _dict_int(row: dict[str, object], key: str) -> int:
    value = row[key]
    if not isinstance(value, int):
        raise TypeError(f"Campo {key} deveria ser inteiro")
    return value
