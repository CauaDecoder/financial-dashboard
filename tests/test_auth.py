from pathlib import Path

from basilica_financeiro.config import Settings
from basilica_financeiro.database import connect, migrate
from basilica_financeiro.paths import AppPaths
from basilica_financeiro.repositories.users import authenticate, create_user


def _settings(tmp_path: Path) -> Settings:
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
        google_client_secret_path=None,
        google_token_path=None,
        paths=AppPaths.from_workspace(tmp_path),
    )


def test_authenticate_creates_session(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.paths.ensure_directories()
    with connect(settings.database_path) as connection:
        migrate(connection)
        create_user(
            connection,
            username="operador",
            password="SenhaForte123!",
            role="operador_financeiro",
            actor_user_id=None,
        )

        session_id = authenticate(
            connection,
            username="operador",
            password="SenhaForte123!",
            settings=settings,
        )

        assert session_id is not None
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_authenticate_locks_after_five_failures(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.paths.ensure_directories()
    with connect(settings.database_path) as connection:
        migrate(connection)
        create_user(
            connection,
            username="admin",
            password="SenhaForte123!",
            role="administrador",
            actor_user_id=None,
        )

        for _ in range(5):
            assert (
                authenticate(
                    connection,
                    username="admin",
                    password="senha-errada",
                    settings=settings,
                )
                is None
            )

        row = connection.execute("SELECT failed_attempts, locked_until FROM users").fetchone()
        assert row["failed_attempts"] == 5
        assert row["locked_until"] is not None
