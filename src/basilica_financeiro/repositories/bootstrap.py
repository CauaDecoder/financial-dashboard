from __future__ import annotations

import sqlite3

from basilica_financeiro.config import Settings
from basilica_financeiro.repositories.users import create_user


def ensure_default_admin(connection: sqlite3.Connection, settings: Settings) -> None:
    existing = connection.execute("SELECT id FROM users LIMIT 1").fetchone()
    if existing is not None:
        return

    if not settings.default_admin_password:
        raise ValueError("DEFAULT_ADMIN_PASSWORD precisa estar configurada no primeiro boot")

    create_user(
        connection,
        username=settings.default_admin_username,
        password=settings.default_admin_password,
        role="administrador",
        actor_user_id=None,
    )
