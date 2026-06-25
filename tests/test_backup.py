from datetime import date
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken

from basilica_financeiro.config import Settings
from basilica_financeiro.database import connect, migrate
from basilica_financeiro.paths import AppPaths
from basilica_financeiro.repositories.finance import create_financial_account
from basilica_financeiro.services.backup import (
    create_encrypted_backup,
    ensure_daily_encrypted_backup,
    restore_encrypted_backup,
)


def test_create_encrypted_backup_records_history(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with connect(settings.database_path) as connection:
        migrate(connection)
        path = create_encrypted_backup(connection, settings=settings, actor_user_id=None)
        history_count = connection.execute("SELECT COUNT(*) FROM backup_history").fetchone()[0]

    assert path.exists()
    assert path.suffix == ".fernet"
    assert history_count == 1


def test_restore_encrypted_backup_replaces_database_and_keeps_preventive_copy(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    with connect(settings.database_path) as connection:
        migrate(connection)
        create_financial_account(
            connection,
            name="Conta original",
            account_type="cash",
            opening_balance_cents=1_000,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        backup_path = create_encrypted_backup(connection, settings=settings, actor_user_id=None)
        create_financial_account(
            connection,
            name="Conta apos backup",
            account_type="cash",
            opening_balance_cents=2_000,
            balance_date=date(2026, 6, 17),
            actor_user_id=None,
        )

    preventive_path = restore_encrypted_backup(backup_path=backup_path, settings=settings)

    with connect(settings.database_path) as connection:
        account_names = {
            row["name"] for row in connection.execute("SELECT name FROM financial_accounts")
        }

    assert account_names == {"Conta original"}
    assert preventive_path.exists()


def test_restore_rejects_invalid_backup_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    invalid_path = settings.paths.backups_dir / "invalid.sqlite3.fernet"
    invalid_path.write_text("nao e backup", encoding="utf-8")

    with pytest.raises(InvalidToken):
        restore_encrypted_backup(backup_path=invalid_path, settings=settings)


def test_automatic_backup_runs_once_per_day(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with connect(settings.database_path) as connection:
        migrate(connection)
        first_path = ensure_daily_encrypted_backup(
            connection,
            settings=settings,
            actor_user_id=None,
        )
        second_path = ensure_daily_encrypted_backup(
            connection,
            settings=settings,
            actor_user_id=None,
        )
        history_count = connection.execute("SELECT COUNT(*) FROM backup_history").fetchone()[0]

    assert first_path is not None
    assert first_path.exists()
    assert second_path is None
    assert history_count == 1


def test_automatic_backup_is_skipped_without_encryption_key(tmp_path: Path) -> None:
    settings = _settings(tmp_path, backup_encryption_key=None)

    with connect(settings.database_path) as connection:
        migrate(connection)
        backup_path = ensure_daily_encrypted_backup(
            connection,
            settings=settings,
            actor_user_id=None,
        )

    assert backup_path is None


def _settings(
    tmp_path: Path,
    *,
    backup_encryption_key: str | None = "__generate__",
) -> Settings:
    paths = AppPaths.from_workspace(tmp_path)
    paths.ensure_directories()
    encryption_key = (
        Fernet.generate_key().decode("utf-8")
        if backup_encryption_key == "__generate__"
        else backup_encryption_key
    )
    return Settings(
        app_env="test",
        secret_key="test-secret-value",
        database_url="sqlite:///data/test.sqlite3",
        session_timeout_minutes=30,
        log_level="INFO",
        backup_encryption_key=encryption_key,
        backup_auto_daily=True,
        default_admin_username="admin",
        default_admin_password="SenhaForte123!",
        asaas_env="sandbox",
        asaas_api_key=None,
        asaas_enable_write_operations=False,
        pdv_database_url=None,
        google_client_secret_path=None,
        google_token_path=None,
        paths=paths,
    )
