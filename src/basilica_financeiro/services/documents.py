from __future__ import annotations

import hashlib
import mimetypes
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from basilica_financeiro.config import Settings
from basilica_financeiro.repositories.audit import record_audit

ATTACHMENT_ENTITY_TYPES = {
    "financial_transaction",
    "payable_receivable_entry",
    "supplier",
    "purchase_order",
}


@dataclass(frozen=True)
class AttachmentResult:
    document_id: int
    link_id: int
    sha256: str
    stored_path: Path


def attach_document(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    source_path: Path,
    entity_type: str,
    entity_id: int,
    actor_user_id: int | None,
) -> AttachmentResult:
    if entity_type not in ATTACHMENT_ENTITY_TYPES:
        raise ValueError("Tipo de vinculo de documento invalido")
    if entity_id <= 0:
        raise ValueError("Identificador do vinculo precisa ser positivo")
    if not source_path.is_file():
        raise ValueError("Arquivo de documento nao encontrado")
    _ensure_entity_exists(connection, entity_type=entity_type, entity_id=entity_id)
    sha256 = _sha256(source_path)
    existing = connection.execute(
        "SELECT id, stored_path FROM documents WHERE sha256 = ?",
        (sha256,),
    ).fetchone()
    if existing is None:
        stored_path = _copy_to_documents(settings, source_path=source_path, sha256=sha256)
        document_id = _insert_document(
            connection,
            source_path=source_path,
            stored_path=stored_path,
            sha256=sha256,
            actor_user_id=actor_user_id,
        )
    else:
        document_id = int(existing["id"])
        stored_path = settings.paths.resolve_app_path(str(existing["stored_path"]))
    link_id = _link_document(
        connection,
        document_id=document_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
    )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="attach",
        entity="document",
        entity_id=str(document_id),
        before=None,
        after={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "sha256": sha256,
        },
        origin="local",
        result="success",
    )
    return AttachmentResult(
        document_id=document_id,
        link_id=link_id,
        sha256=sha256,
        stored_path=stored_path,
    )


def list_documents(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT
            d.id,
            d.original_name,
            d.stored_path,
            d.sha256,
            d.size_bytes,
            d.mime_type,
            d.created_at,
            GROUP_CONCAT(l.entity_type || ':' || l.entity_id, ', ') AS links
        FROM documents d
        LEFT JOIN document_links l ON l.document_id = d.id
        GROUP BY d.id
        ORDER BY d.created_at DESC, d.id DESC
        LIMIT 300
        """
    ).fetchall()
    return [dict(row) for row in rows]


def list_document_links(
    connection: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: int,
) -> list[dict[str, object]]:
    if entity_type not in ATTACHMENT_ENTITY_TYPES:
        raise ValueError("Tipo de vinculo de documento invalido")
    rows = connection.execute(
        """
        SELECT
            d.id,
            d.original_name,
            d.stored_path,
            d.sha256,
            d.size_bytes,
            d.mime_type,
            d.created_at
        FROM document_links l
        JOIN documents d ON d.id = l.document_id
        WHERE l.entity_type = ? AND l.entity_id = ?
        ORDER BY d.created_at DESC, d.id DESC
        """,
        (entity_type, entity_id),
    ).fetchall()
    return [dict(row) for row in rows]


def _insert_document(
    connection: sqlite3.Connection,
    *,
    source_path: Path,
    stored_path: Path,
    sha256: str,
    actor_user_id: int | None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO documents (
            original_name, stored_path, sha256, size_bytes, mime_type, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            source_path.name,
            str(stored_path),
            sha256,
            source_path.stat().st_size,
            mimetypes.guess_type(source_path.name)[0],
            actor_user_id,
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao registrar documento")
    return cursor.lastrowid


def _link_document(
    connection: sqlite3.Connection,
    *,
    document_id: int,
    entity_type: str,
    entity_id: int,
    actor_user_id: int | None,
) -> int:
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO document_links (
            document_id, entity_type, entity_id, created_by
        )
        VALUES (?, ?, ?, ?)
        """,
        (document_id, entity_type, entity_id, actor_user_id),
    )
    row = connection.execute(
        """
        SELECT id FROM document_links
        WHERE document_id = ? AND entity_type = ? AND entity_id = ?
        """,
        (document_id, entity_type, entity_id),
    ).fetchone()
    if row is None:
        raise RuntimeError("Falha ao vincular documento")
    return int(row["id"] if cursor.lastrowid is None else row["id"])


def _copy_to_documents(settings: Settings, *, source_path: Path, sha256: str) -> Path:
    target_dir = settings.paths.documents_dir / sha256[:2] / sha256[2:4]
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(source_path.name)
    target_path = target_dir / f"{sha256[:12]}_{safe_name}"
    if not target_path.exists():
        shutil.copy2(source_path, target_path)
    return target_path.relative_to(settings.paths.root)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_filename(filename: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", filename.strip())
    return clean or "documento"


def _ensure_entity_exists(
    connection: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: int,
) -> None:
    queries = {
        "financial_transaction": "SELECT id FROM financial_transactions WHERE id = ?",
        "payable_receivable_entry": "SELECT id FROM payable_receivable_entries WHERE id = ?",
        "supplier": "SELECT id FROM suppliers WHERE id = ?",
        "purchase_order": "SELECT id FROM purchase_orders WHERE id = ?",
    }
    row = connection.execute(queries[entity_type], (entity_id,)).fetchone()
    if row is None:
        raise ValueError("Registro para vinculo de documento nao encontrado")
