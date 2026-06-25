from __future__ import annotations

from datetime import date
from pathlib import Path

from basilica_financeiro.config import Settings
from basilica_financeiro.database import connect, migrate
from basilica_financeiro.paths import AppPaths
from basilica_financeiro.services.documents import (
    attach_document,
    list_document_links,
    list_documents,
)
from basilica_financeiro.services.google_sheets import (
    get_google_sheets_status,
    list_google_sheet_imports,
    record_google_sheet_import,
)
from basilica_financeiro.services.purchases import create_purchase_order, create_supplier


def test_attach_document_copies_hashes_and_reuses_existing_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.paths.ensure_directories()
    source = tmp_path / "nota-fiscal.pdf"
    source.write_bytes(b"%PDF-1.4\nfake pdf\n")

    with connect(settings.database_path) as connection:
        migrate(connection)
        supplier_id = create_supplier(
            connection,
            name="Fornecedor NF",
            actor_user_id=None,
        )
        order_id = create_purchase_order(
            connection,
            supplier_id=supplier_id,
            description="Compra com NF",
            total_cents=10_000,
            expected_date=date(2026, 6, 30),
            actor_user_id=None,
        )

        first = attach_document(
            connection,
            settings=settings,
            source_path=source,
            entity_type="purchase_order",
            entity_id=order_id,
            actor_user_id=None,
        )
        second = attach_document(
            connection,
            settings=settings,
            source_path=source,
            entity_type="purchase_order",
            entity_id=order_id,
            actor_user_id=None,
        )

        documents = list_documents(connection)
        links = list_document_links(
            connection,
            entity_type="purchase_order",
            entity_id=order_id,
        )
        audit = connection.execute(
            "SELECT COUNT(*) AS total FROM audit_log WHERE entity = 'document'"
        ).fetchone()

    assert first.document_id == second.document_id
    assert first.link_id == second.link_id
    assert len(documents) == 1
    assert len(links) == 1
    assert first.stored_path.suffix == ".pdf"
    assert (settings.paths.root / first.stored_path).is_file()
    assert documents[0]["sha256"] == first.sha256
    assert audit["total"] == 2


def test_google_sheets_status_and_import_tracking(tmp_path: Path) -> None:
    client_secret = tmp_path / "client_secret.json"
    token = tmp_path / "token.json"
    client_secret.write_text("{}", encoding="utf-8")
    token.write_text("{}", encoding="utf-8")
    settings = _settings(
        tmp_path,
        google_client_secret_path=str(client_secret),
        google_token_path=str(token),
    )

    with connect(settings.database_path) as connection:
        migrate(connection)
        import_id = record_google_sheet_import(
            connection,
            spreadsheet_id="sheet-123",
            sheet_name="Financeiro",
            rows_count=12,
            actor_user_id=None,
        )
        imports = list_google_sheet_imports(connection)

    status = get_google_sheets_status(settings)
    missing = get_google_sheets_status(_settings(tmp_path))

    assert status.configured is True
    assert status.client_secret_exists is True
    assert status.token_exists is True
    assert missing.configured is False
    assert "GOOGLE_CLIENT_SECRET_PATH" in missing.message
    assert imports[0]["id"] == import_id
    assert imports[0]["rows_count"] == 12


def _settings(
    tmp_path: Path,
    *,
    google_client_secret_path: str | None = None,
    google_token_path: str | None = None,
) -> Settings:
    return Settings(
        app_env="test",
        secret_key="test-secret-value",
        database_url="sqlite:///data/test.sqlite3",
        session_timeout_minutes=30,
        log_level="INFO",
        backup_encryption_key=None,
        backup_auto_daily=True,
        default_admin_username="admin",
        default_admin_password="SenhaForte123!",
        asaas_env="sandbox",
        asaas_api_key=None,
        asaas_enable_write_operations=False,
        pdv_database_url=None,
        google_client_secret_path=google_client_secret_path,
        google_token_path=google_token_path,
        paths=AppPaths.from_workspace(tmp_path),
    )
