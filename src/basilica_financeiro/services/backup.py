from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from cryptography.fernet import Fernet

from basilica_financeiro.config import Settings
from basilica_financeiro.repositories.audit import record_audit


def create_encrypted_backup(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    actor_user_id: int | None,
) -> Path:
    """Create an encrypted backup for the current SQLite database."""
    if not settings.backup_encryption_key:
        raise ValueError("BACKUP_ENCRYPTION_KEY precisa estar configurada para gerar backups")

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    snapshot_path = settings.paths.backups_dir / f"basilica-financeiro-{timestamp}.sqlite3"
    encrypted_path = snapshot_path.with_suffix(".sqlite3.fernet")
    connection.execute("PRAGMA wal_checkpoint(FULL)")
    shutil.copy2(settings.database_path, snapshot_path)

    encrypted = Fernet(settings.backup_encryption_key.encode("utf-8")).encrypt(
        snapshot_path.read_bytes()
    )
    encrypted_path.write_bytes(encrypted)
    snapshot_path.unlink()

    digest = sha256(encrypted).hexdigest()
    connection.execute(
        "INSERT INTO backup_history (path, sha256, created_by) VALUES (?, ?, ?)",
        (str(encrypted_path), digest, actor_user_id),
    )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="backup",
        entity="database",
        entity_id=None,
        before=None,
        after={"path": str(encrypted_path), "sha256": digest},
        origin="local",
        result="success",
    )
    return encrypted_path


def ensure_daily_encrypted_backup(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    actor_user_id: int | None,
) -> Path | None:
    """Create one automatic encrypted backup per UTC day when configured."""
    if not settings.backup_auto_daily or not settings.backup_encryption_key:
        return None
    today = datetime.now(UTC).date().isoformat()
    existing = connection.execute(
        """
        SELECT id
        FROM backup_history
        WHERE DATE(created_at) = ?
        LIMIT 1
        """,
        (today,),
    ).fetchone()
    if existing is not None:
        return None
    return create_encrypted_backup(
        connection,
        settings=settings,
        actor_user_id=actor_user_id,
    )


def restore_encrypted_backup(
    *,
    backup_path: Path,
    settings: Settings,
) -> Path:
    """Restore an encrypted backup after integrity validation."""
    if not settings.backup_encryption_key:
        raise ValueError("BACKUP_ENCRYPTION_KEY precisa estar configurada para restaurar backups")
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup nao encontrado: {backup_path}")

    settings.paths.backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    preventive_path = settings.paths.backups_dir / (
        f"pre-restore-basilica-financeiro-{timestamp}.sqlite3"
    )
    decrypted_path = settings.paths.backups_dir / f"restore-check-{timestamp}.sqlite3"

    decrypted = Fernet(settings.backup_encryption_key.encode("utf-8")).decrypt(
        backup_path.read_bytes()
    )
    decrypted_path.write_bytes(decrypted)
    try:
        _validate_sqlite_integrity(decrypted_path)
        if settings.database_path.exists():
            _checkpoint_database(settings.database_path)
            shutil.copy2(settings.database_path, preventive_path)
            _remove_sqlite_sidecars(settings.database_path)
        shutil.copy2(decrypted_path, settings.database_path)
    finally:
        decrypted_path.unlink(missing_ok=True)

    return preventive_path


def _validate_sqlite_integrity(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise ValueError("Backup falhou na verificacao de integridade")
        required_tables = {"users", "audit_log", "backup_history", "schema_version"}
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing = required_tables - tables
        if missing:
            raise ValueError(f"Backup sem tabelas obrigatorias: {', '.join(sorted(missing))}")
    finally:
        connection.close()


def _checkpoint_database(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA wal_checkpoint(FULL)")
    finally:
        connection.close()


def _remove_sqlite_sidecars(database_path: Path) -> None:
    for suffix in ["-wal", "-shm"]:
        database_path.with_name(f"{database_path.name}{suffix}").unlink(missing_ok=True)
