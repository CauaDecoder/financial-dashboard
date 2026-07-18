from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import keyring

from basilica_financeiro.paths import AppPaths


@dataclass(frozen=True)
class Settings:
    app_env: str
    secret_key: str
    database_url: str
    session_timeout_minutes: int
    log_level: str
    backup_encryption_key: str | None
    backup_auto_daily: bool
    default_admin_username: str
    default_admin_password: str | None
    asaas_env: str
    asaas_api_key: str | None
    asaas_enable_write_operations: bool
    pdv_database_url: str | None
    google_client_secret_path: str | None
    google_token_path: str | None
    paths: AppPaths
    postgres_rehearsal_database_url: str | None = None
    postgres_rehearsal_enable_execution: bool = False

    @property
    def database_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("A Fase 1 aceita apenas DATABASE_URL sqlite:///")
        return self.paths.resolve_app_path(self.database_url.removeprefix("sqlite:///"))


def load_settings() -> Settings:
    """Load application settings from environment and optional .env file."""
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

    paths = AppPaths.from_workspace(Path.cwd())
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        secret_key=_get_secret("APP_SECRET_KEY"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/basilica_financeiro.sqlite3"),
        session_timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "30")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        backup_encryption_key=_get_secret("BACKUP_ENCRYPTION_KEY", required=False),
        backup_auto_daily=_env_bool("BACKUP_AUTO_DAILY", default=True),
        default_admin_username=os.getenv("DEFAULT_ADMIN_USERNAME", "admin"),
        default_admin_password=_get_secret("DEFAULT_ADMIN_PASSWORD", required=False),
        asaas_env=os.getenv("ASAAS_ENV", "sandbox"),
        asaas_api_key=_get_secret("ASAAS_API_KEY", required=False),
        asaas_enable_write_operations=_env_bool("ASAAS_ENABLE_WRITE_OPERATIONS", default=False),
        pdv_database_url=os.getenv("PDV_DATABASE_URL") or None,
        google_client_secret_path=os.getenv("GOOGLE_CLIENT_SECRET_PATH") or None,
        google_token_path=os.getenv("GOOGLE_TOKEN_PATH") or None,
        paths=paths,
        postgres_rehearsal_database_url=os.getenv("POSTGRES_REHEARSAL_DATABASE_URL") or None,
        postgres_rehearsal_enable_execution=_env_bool(
            "POSTGRES_REHEARSAL_ENABLE_EXECUTION",
            default=False,
        ),
    )


import structlog

logger = structlog.get_logger()

def _get_secret(name: str, *, required: bool = True) -> str | None:
    key = keyring.get_password("basilica_financeiro", name)
    if key:
        return key

    # Fallback temporário — remover após todas as máquinas da secretaria migrarem para keyring.
    legacy_key = os.getenv(name)
    if legacy_key:
        logger.warning(
            f"{name} lida via variável de ambiente (.env). "
            "Migre para keyring o quanto antes — este fallback será removido."
        )
        return legacy_key
    
    if required:
        raise ValueError(f"{name} precisa estar configurado no keyring")
    return None


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}
