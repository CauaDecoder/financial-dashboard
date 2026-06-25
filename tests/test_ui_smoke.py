from pathlib import Path

from basilica_financeiro.config import Settings
from basilica_financeiro.paths import AppPaths
from basilica_financeiro.ui.qt_app import run_qt_app


def test_qt_login_window_renders_offscreen(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    settings = Settings(
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

    screenshot_path = tmp_path / "login-smoke.png"

    assert run_qt_app(settings, auto_quit_ms=75, screenshot_path=screenshot_path) == 0
    assert screenshot_path.exists()
    assert screenshot_path.stat().st_size > 0
