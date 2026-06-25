from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from basilica_financeiro.config import Settings
from basilica_financeiro.repositories.audit import record_audit
from basilica_financeiro.security.passwords import hash_password, verify_password

MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15


def create_user(
    connection: sqlite3.Connection,
    *,
    username: str,
    password: str,
    role: str,
    actor_user_id: int | None,
) -> int:
    cursor = connection.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, hash_password(password), role),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao criar usuario")
    user_id = cursor.lastrowid
    record_audit(
        connection,
        user_id=actor_user_id,
        action="create",
        entity="user",
        entity_id=str(user_id),
        before=None,
        after={"username": username, "role": role},
        origin="local",
        result="success",
    )
    return user_id


def list_users(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT id, username, role, is_active, failed_attempts, locked_until, created_at
            FROM users
            ORDER BY username
            """
        ).fetchall()
    )


def list_roles(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(connection.execute("SELECT name, description FROM roles ORDER BY name").fetchall())


def authenticate(
    connection: sqlite3.Connection,
    *,
    username: str,
    password: str,
    settings: Settings,
) -> str | None:
    row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None or not row["is_active"]:
        record_audit(
            connection,
            user_id=None,
            action="login",
            entity="user",
            entity_id=None,
            before=None,
            after={"username": username},
            origin="local",
            result="denied",
        )
        return None

    now = datetime.now(UTC)
    if row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > now:
        _audit_login(connection, int(row["id"]), "locked")
        return None

    if not verify_password(str(row["password_hash"]), password):
        failed_attempts = int(row["failed_attempts"]) + 1
        locked_until = (
            (now + timedelta(minutes=LOCK_MINUTES)).isoformat()
            if failed_attempts >= MAX_FAILED_ATTEMPTS
            else None
        )
        connection.execute(
            "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
            (failed_attempts, locked_until, row["id"]),
        )
        connection.commit()
        _audit_login(connection, int(row["id"]), "denied")
        return None

    session_id = str(uuid4())
    expires_at = now + timedelta(minutes=settings.session_timeout_minutes)
    connection.execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (row["id"],),
    )
    connection.execute(
        "INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)",
        (session_id, row["id"], expires_at.isoformat()),
    )
    connection.commit()
    _audit_login(connection, int(row["id"]), "success")
    return session_id


def get_session_user_id(connection: sqlite3.Connection, session_id: str) -> int | None:
    row = connection.execute(
        "SELECT user_id, expires_at FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if row is None or datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC):
        return None
    return int(row["user_id"])


def _audit_login(connection: sqlite3.Connection, user_id: int, result: str) -> None:
    record_audit(
        connection,
        user_id=user_id,
        action="login",
        entity="session",
        entity_id=None,
        before=None,
        after=None,
        origin="local",
        result=result,
    )
