from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from basilica_financeiro.config import Settings
from basilica_financeiro.repositories.audit import record_audit


@dataclass(frozen=True)
class GoogleSheetsStatus:
    configured: bool
    client_secret_exists: bool
    token_exists: bool
    message: str


def get_google_sheets_status(settings: Settings) -> GoogleSheetsStatus:
    client_secret = _optional_config_path(settings, settings.google_client_secret_path)
    token = _optional_config_path(settings, settings.google_token_path)
    client_secret_exists = client_secret is not None and client_secret.is_file()
    token_exists = token is not None and token.is_file()
    if client_secret_exists and token_exists:
        return GoogleSheetsStatus(
            configured=True,
            client_secret_exists=True,
            token_exists=True,
            message="Google Sheets configurado localmente",
        )
    if client_secret is None:
        message = "GOOGLE_CLIENT_SECRET_PATH nao configurado no .env"
    elif not client_secret_exists:
        message = "Arquivo de credencial Google nao encontrado"
    elif token is None:
        message = "GOOGLE_TOKEN_PATH nao configurado no .env"
    else:
        message = "Arquivo de token Google nao encontrado"
    return GoogleSheetsStatus(
        configured=False,
        client_secret_exists=client_secret_exists,
        token_exists=token_exists,
        message=message,
    )


def record_google_sheet_import(
    connection: sqlite3.Connection,
    *,
    spreadsheet_id: str,
    sheet_name: str,
    rows_count: int,
    actor_user_id: int | None,
) -> int:
    spreadsheet_id = _required_text(spreadsheet_id, "ID da planilha")
    sheet_name = _required_text(sheet_name, "Nome da aba")
    if rows_count < 0:
        raise ValueError("Quantidade de linhas importadas nao pode ser negativa")
    cursor = connection.execute(
        """
        INSERT INTO google_sheet_imports (
            spreadsheet_id, sheet_name, rows_count, imported_by
        )
        VALUES (?, ?, ?, ?)
        """,
        (spreadsheet_id, sheet_name, rows_count, actor_user_id),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao registrar importacao Google Sheets")
    import_id = cursor.lastrowid
    record_audit(
        connection,
        user_id=actor_user_id,
        action="record_import",
        entity="google_sheet_import",
        entity_id=str(import_id),
        before=None,
        after={
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "rows_count": rows_count,
        },
        origin="google_sheets",
        result="success",
    )
    return import_id


def list_google_sheet_imports(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT id, spreadsheet_id, sheet_name, rows_count, imported_by, created_at
        FROM google_sheet_imports
        ORDER BY created_at DESC, id DESC
        LIMIT 100
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _optional_config_path(settings: Settings, value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return settings.paths.resolve_app_path(value)


def _required_text(value: str, field_label: str) -> str:
    clean = value.strip()
    if not clean:
        raise ValueError(f"{field_label} precisa ser preenchido")
    return clean
