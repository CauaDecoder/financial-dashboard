import sqlite3
from pathlib import Path

import pytest

from basilica_financeiro.config import load_settings
from basilica_financeiro.database import connect, migrate
from basilica_financeiro.repositories.audit import audited_action
from basilica_financeiro.repositories.bootstrap import ensure_default_admin
from basilica_financeiro.security.passwords import hash_password
from basilica_financeiro.services.backup import create_encrypted_backup

TEST_PASSWORD = "SenhaForte123!"


def test_load_settings_reads_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "APP_SECRET_KEY=local-secret",
                "DATABASE_URL=sqlite:///data/local.sqlite3",
                "DEFAULT_ADMIN_USERNAME=admin",
                "DEFAULT_ADMIN_" + f"PASSWORD={TEST_PASSWORD}",
                "SESSION_TIMEOUT_MINUTES=45",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings()

    assert settings.secret_key == "local-secret"
    assert settings.default_admin_username == "admin"
    assert settings.session_timeout_minutes == 45
    assert settings.database_path == tmp_path / "data" / "local.sqlite3"


def test_bootstrap_requires_default_admin_password(tmp_path: Path) -> None:
    settings = load_settings_for_test(tmp_path, default_admin_password=None)
    settings.paths.ensure_directories()
    with connect(settings.database_path) as connection:
        migrate(connection)

        with pytest.raises(ValueError):
            ensure_default_admin(connection, settings)


def test_bootstrap_creates_default_admin_once(tmp_path: Path) -> None:
    settings = load_settings_for_test(tmp_path)
    settings.paths.ensure_directories()
    with connect(settings.database_path) as connection:
        migrate(connection)
        ensure_default_admin(connection, settings)
        ensure_default_admin(connection, settings)
        count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    assert count == 1


def test_audited_action_records_failure(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        @audited_action(action="explode", entity="test")
        def fail(connection: sqlite3.Connection, *, actor_user_id: int | None) -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError):
            fail(connection, actor_user_id=None)

        row = connection.execute("SELECT result FROM audit_log ORDER BY id DESC").fetchone()

    assert row["result"] == "failed"


def test_backup_requires_encryption_key(tmp_path: Path) -> None:
    settings = load_settings_for_test(tmp_path, backup_encryption_key=None)
    settings.paths.ensure_directories()
    with connect(settings.database_path) as connection:
        migrate(connection)

        with pytest.raises(ValueError):
            create_encrypted_backup(connection, settings=settings, actor_user_id=None)


def test_short_password_is_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("curta")


def load_settings_for_test(
    tmp_path: Path,
    *,
    default_admin_password: str | None = TEST_PASSWORD,
    backup_encryption_key: str | None = "not-a-real-fernet-key",
):
    from basilica_financeiro.config import Settings
    from basilica_financeiro.paths import AppPaths

    return Settings(
        app_env="test",
        secret_key="test-secret-value",
        database_url="sqlite:///data/test.sqlite3",
        session_timeout_minutes=30,
        log_level="INFO",
        backup_encryption_key=backup_encryption_key,
        backup_auto_daily=True,
        default_admin_username="admin",
        default_admin_password=default_admin_password,
        asaas_env="sandbox",
        asaas_api_key=None,
        asaas_enable_write_operations=False,
        pdv_database_url=None,
        google_client_secret_path=None,
        google_token_path=None,
        paths=AppPaths.from_workspace(tmp_path),
    )
