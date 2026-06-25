from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from basilica_financeiro.repositories.audit import record_audit

APPROVALS_REQUIRED = 2
ALLOWED_OPERATION_TYPES = {
    "asaas_create_charge",
    "asaas_cancel_charge",
    "asaas_refund_payment",
}
FORBIDDEN_PAYLOAD_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "client_secret",
    "password",
    "secret",
    "token",
}


@dataclass(frozen=True)
class SensitiveOperationRequest:
    id: int
    operation_type: str
    title: str
    status: str
    amount_cents: int | None
    external_reference: str | None
    requested_by: int
    requested_username: str
    approvals_count: int
    rejections_count: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class SensitiveOperationApproval:
    approver_user_id: int
    approver_username: str
    decision: str
    notes: str | None
    created_at: str


def create_sensitive_operation_request(
    connection: sqlite3.Connection,
    *,
    operation_type: str,
    title: str,
    payload: dict[str, Any],
    requested_by: int,
    amount_cents: int | None = None,
    external_reference: str | None = None,
) -> int:
    if operation_type not in ALLOWED_OPERATION_TYPES:
        raise ValueError("Tipo de operacao sensivel invalido")
    title = title.strip()
    if not title:
        raise ValueError("Titulo da solicitacao precisa ser preenchido")
    if amount_cents is not None and amount_cents <= 0:
        raise ValueError("Valor da solicitacao precisa ser positivo")
    _validate_payload(payload)
    cursor = connection.execute(
        """
        INSERT INTO sensitive_operation_requests (
            operation_type, title, amount_cents, external_reference, payload_json, requested_by
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            operation_type,
            title,
            amount_cents,
            external_reference.strip() if external_reference else None,
            json.dumps(payload, ensure_ascii=True, sort_keys=True),
            requested_by,
        ),
    )
    request_id = cursor.lastrowid
    if request_id is None:
        raise RuntimeError("Falha ao criar solicitacao sensivel")
    record_audit(
        connection,
        user_id=requested_by,
        action="create",
        entity="sensitive_operation_request",
        entity_id=str(request_id),
        before=None,
        after={
            "operation_type": operation_type,
            "title": title,
            "amount_cents": amount_cents,
            "external_reference": external_reference,
            "status": "pending",
        },
        origin="local",
        result="success",
    )
    return int(request_id)


def approve_sensitive_operation_request(
    connection: sqlite3.Connection,
    *,
    request_id: int,
    approver_user_id: int,
    decision: str = "approved",
    notes: str | None = None,
) -> SensitiveOperationRequest:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decisao de aprovacao invalida")
    request = get_sensitive_operation_request(connection, request_id)
    if request.status != "pending":
        raise ValueError("Solicitacao sensivel nao esta pendente")
    if request.requested_by == approver_user_id:
        raise ValueError("Solicitante nao pode aprovar a propria operacao")
    existing_decision = connection.execute(
        """
        SELECT id
        FROM sensitive_operation_approvals
        WHERE request_id = ? AND approver_user_id = ?
        """,
        (request_id, approver_user_id),
    ).fetchone()
    if existing_decision is not None:
        raise ValueError("Usuario ja registrou decisao para esta solicitacao")
    connection.execute(
        """
        INSERT INTO sensitive_operation_approvals (request_id, approver_user_id, decision, notes)
        VALUES (?, ?, ?, ?)
        """,
        (request_id, approver_user_id, decision, notes.strip() if notes else None),
    )
    next_status = _next_status(connection, request_id)
    connection.execute(
        """
        UPDATE sensitive_operation_requests
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (next_status, request_id),
    )
    record_audit(
        connection,
        user_id=approver_user_id,
        action=decision,
        entity="sensitive_operation_request",
        entity_id=str(request_id),
        before={"status": request.status},
        after={"status": next_status},
        origin="local",
        result="success",
    )
    return get_sensitive_operation_request(connection, request_id)


def cancel_sensitive_operation_request(
    connection: sqlite3.Connection,
    *,
    request_id: int,
    actor_user_id: int,
) -> SensitiveOperationRequest:
    request = get_sensitive_operation_request(connection, request_id)
    if request.status != "pending":
        raise ValueError("Apenas solicitacoes pendentes podem ser canceladas")
    connection.execute(
        """
        UPDATE sensitive_operation_requests
        SET status = 'canceled', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (request_id,),
    )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="cancel",
        entity="sensitive_operation_request",
        entity_id=str(request_id),
        before={"status": "pending"},
        after={"status": "canceled"},
        origin="local",
        result="success",
    )
    return get_sensitive_operation_request(connection, request_id)


def get_sensitive_operation_request(
    connection: sqlite3.Connection,
    request_id: int,
) -> SensitiveOperationRequest:
    row = connection.execute(
        """
        SELECT
            r.id,
            r.operation_type,
            r.title,
            r.status,
            r.amount_cents,
            r.external_reference,
            r.payload_json,
            r.requested_by,
            u.username AS requested_username,
            COUNT(CASE WHEN a.decision = 'approved' THEN 1 END) AS approvals_count,
            COUNT(CASE WHEN a.decision = 'rejected' THEN 1 END) AS rejections_count
        FROM sensitive_operation_requests r
        JOIN users u ON u.id = r.requested_by
        LEFT JOIN sensitive_operation_approvals a ON a.request_id = r.id
        WHERE r.id = ?
        GROUP BY r.id
        """,
        (request_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Solicitacao sensivel nao encontrada")
    return _request_from_row(row)


def list_sensitive_operation_requests(
    connection: sqlite3.Connection,
    *,
    status: str | None = None,
) -> list[SensitiveOperationRequest]:
    valid_statuses = {"pending", "approved", "rejected", "canceled", "executed"}
    if status is not None and status not in valid_statuses:
        raise ValueError("Status de solicitacao sensivel invalido")
    if status is None:
        rows = connection.execute(
            """
            SELECT
                r.id,
                r.operation_type,
                r.title,
                r.status,
                r.amount_cents,
                r.external_reference,
                r.payload_json,
                r.requested_by,
                u.username AS requested_username,
                COUNT(CASE WHEN a.decision = 'approved' THEN 1 END) AS approvals_count,
                COUNT(CASE WHEN a.decision = 'rejected' THEN 1 END) AS rejections_count
            FROM sensitive_operation_requests r
            JOIN users u ON u.id = r.requested_by
            LEFT JOIN sensitive_operation_approvals a ON a.request_id = r.id
            GROUP BY r.id
            ORDER BY r.id DESC
            """
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT
                r.id,
                r.operation_type,
                r.title,
                r.status,
                r.amount_cents,
                r.external_reference,
                r.payload_json,
                r.requested_by,
                u.username AS requested_username,
                COUNT(CASE WHEN a.decision = 'approved' THEN 1 END) AS approvals_count,
                COUNT(CASE WHEN a.decision = 'rejected' THEN 1 END) AS rejections_count
            FROM sensitive_operation_requests r
            JOIN users u ON u.id = r.requested_by
            LEFT JOIN sensitive_operation_approvals a ON a.request_id = r.id
            WHERE r.status = ?
            GROUP BY r.id
            ORDER BY r.id DESC
            """,
            (status,),
        ).fetchall()
    return [_request_from_row(row) for row in rows]


def list_sensitive_operation_approvals(
    connection: sqlite3.Connection,
    *,
    request_id: int,
) -> list[SensitiveOperationApproval]:
    rows = connection.execute(
        """
        SELECT
            a.approver_user_id,
            u.username AS approver_username,
            a.decision,
            a.notes,
            a.created_at
        FROM sensitive_operation_approvals a
        JOIN users u ON u.id = a.approver_user_id
        WHERE a.request_id = ?
        ORDER BY a.created_at, a.id
        """,
        (request_id,),
    ).fetchall()
    return [
        SensitiveOperationApproval(
            approver_user_id=int(row["approver_user_id"]),
            approver_username=str(row["approver_username"]),
            decision=str(row["decision"]),
            notes=None if row["notes"] is None else str(row["notes"]),
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]


def _next_status(connection: sqlite3.Connection, request_id: int) -> str:
    counts = connection.execute(
        """
        SELECT
            SUM(CASE WHEN decision = 'approved' THEN 1 ELSE 0 END) AS approvals_count,
            SUM(CASE WHEN decision = 'rejected' THEN 1 ELSE 0 END) AS rejections_count
        FROM sensitive_operation_approvals
        WHERE request_id = ?
        """,
        (request_id,),
    ).fetchone()
    approvals_count = 0 if counts["approvals_count"] is None else int(counts["approvals_count"])
    rejections_count = 0 if counts["rejections_count"] is None else int(counts["rejections_count"])
    if rejections_count:
        return "rejected"
    if approvals_count >= APPROVALS_REQUIRED:
        return "approved"
    return "pending"


def _request_from_row(row: sqlite3.Row) -> SensitiveOperationRequest:
    payload = json.loads(str(row["payload_json"]))
    if not isinstance(payload, dict):
        raise ValueError("Payload da solicitacao sensivel esta invalido")
    return SensitiveOperationRequest(
        id=int(row["id"]),
        operation_type=str(row["operation_type"]),
        title=str(row["title"]),
        status=str(row["status"]),
        amount_cents=None if row["amount_cents"] is None else int(row["amount_cents"]),
        external_reference=(
            None if row["external_reference"] is None else str(row["external_reference"])
        ),
        requested_by=int(row["requested_by"]),
        requested_username=str(row["requested_username"]),
        approvals_count=int(row["approvals_count"]),
        rejections_count=int(row["rejections_count"]),
        payload=payload,
    )


def _validate_payload(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).strip()
            if key_text.lower() in FORBIDDEN_PAYLOAD_KEYS:
                raise ValueError(f"Payload contem campo sensivel: {path}.{key_text}")
            _validate_payload(child, path=f"{path}.{key_text}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_payload(child, path=f"{path}[{index}]")
        return
    if not isinstance(value, str | int | bool | None):
        raise ValueError("Payload precisa conter apenas valores JSON")
