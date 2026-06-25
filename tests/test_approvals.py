import sqlite3
from pathlib import Path

import pytest

from basilica_financeiro.database import connect, migrate
from basilica_financeiro.repositories.users import create_user
from basilica_financeiro.services.approvals import (
    approve_sensitive_operation_request,
    cancel_sensitive_operation_request,
    create_sensitive_operation_request,
    get_sensitive_operation_request,
    list_sensitive_operation_approvals,
    list_sensitive_operation_requests,
)


def test_sensitive_operation_requires_two_distinct_approvers(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        requester_id, first_approver_id, second_approver_id = _create_users(connection)

        request_id = create_sensitive_operation_request(
            connection,
            operation_type="asaas_create_charge",
            title="Criar cobranca de dizimo",
            amount_cents=15_000,
            external_reference="DIZ-2026-001",
            payload={
                "customer_id": "cus_123",
                "description": "Dizimo mensal",
                "value_cents": 15_000,
            },
            requested_by=requester_id,
        )
        after_first = approve_sensitive_operation_request(
            connection,
            request_id=request_id,
            approver_user_id=first_approver_id,
            notes="Conferido com secretaria.",
        )
        after_second = approve_sensitive_operation_request(
            connection,
            request_id=request_id,
            approver_user_id=second_approver_id,
            notes="Conferido com financeiro.",
        )
        approvals = list_sensitive_operation_approvals(connection, request_id=request_id)

        audit_actions = [
            row["action"]
            for row in connection.execute(
                """
                SELECT action
                FROM audit_log
                WHERE entity = 'sensitive_operation_request'
                ORDER BY id
                """
            ).fetchall()
        ]

        assert after_first.status == "pending"
        assert after_first.approvals_count == 1
        assert after_second.status == "approved"
        assert after_second.approvals_count == 2
        assert after_second.rejections_count == 0
        assert [approval.approver_username for approval in approvals] == ["gestor", "admin"]
        assert approvals[0].notes == "Conferido com secretaria."
        assert audit_actions == ["create", "approved", "approved"]


def test_sensitive_operation_rejects_requester_self_approval(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        requester_id, _, _ = _create_users(connection)
        request_id = create_sensitive_operation_request(
            connection,
            operation_type="asaas_cancel_charge",
            title="Cancelar cobranca duplicada",
            payload={"asaas_id": "pay_123", "reason": "Duplicidade"},
            requested_by=requester_id,
        )

        with pytest.raises(ValueError, match="propria operacao"):
            approve_sensitive_operation_request(
                connection,
                request_id=request_id,
                approver_user_id=requester_id,
            )

        request = get_sensitive_operation_request(connection, request_id)
        assert request.status == "pending"
        assert request.approvals_count == 0


def test_sensitive_operation_rejection_closes_request(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        requester_id, first_approver_id, second_approver_id = _create_users(connection)
        request_id = create_sensitive_operation_request(
            connection,
            operation_type="asaas_refund_payment",
            title="Estornar cobranca",
            amount_cents=5_000,
            payload={"asaas_id": "pay_123", "reason": "Pagamento indevido"},
            requested_by=requester_id,
        )

        rejected = approve_sensitive_operation_request(
            connection,
            request_id=request_id,
            approver_user_id=first_approver_id,
            decision="rejected",
            notes="Documento divergente.",
        )

        assert rejected.status == "rejected"
        assert rejected.rejections_count == 1
        with pytest.raises(ValueError, match="nao esta pendente"):
            approve_sensitive_operation_request(
                connection,
                request_id=request_id,
                approver_user_id=second_approver_id,
            )


def test_sensitive_operation_rejects_sensitive_payload_fields(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        requester_id, _, _ = _create_users(connection)

        with pytest.raises(ValueError, match="campo sensivel"):
            create_sensitive_operation_request(
                connection,
                operation_type="asaas_create_charge",
                title="Criar cobranca",
                payload={"customer_id": "cus_123", "access_token": "test-token"},
                requested_by=requester_id,
            )


def test_sensitive_operation_can_be_canceled_and_listed(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        requester_id, first_approver_id, _ = _create_users(connection)
        request_id = create_sensitive_operation_request(
            connection,
            operation_type="asaas_cancel_charge",
            title="Cancelar cobranca",
            payload={"asaas_id": "pay_123", "reason": "Solicitacao cancelada"},
            requested_by=requester_id,
        )

        canceled = cancel_sensitive_operation_request(
            connection,
            request_id=request_id,
            actor_user_id=first_approver_id,
        )
        requests = list_sensitive_operation_requests(connection, status="canceled")

        assert canceled.status == "canceled"
        assert [request.id for request in requests] == [request_id]


def _create_users(connection: sqlite3.Connection) -> tuple[int, int, int]:
    requester_id = create_user(
        connection,
        username="operador",
        password="SenhaForte123!",
        role="operador_financeiro",
        actor_user_id=None,
    )
    first_approver_id = create_user(
        connection,
        username="gestor",
        password="SenhaForte123!",
        role="gestor_financeiro",
        actor_user_id=requester_id,
    )
    second_approver_id = create_user(
        connection,
        username="admin",
        password="SenhaForte123!",
        role="administrador",
        actor_user_id=requester_id,
    )
    return requester_id, first_approver_id, second_approver_id
