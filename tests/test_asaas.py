from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from basilica_financeiro.config import Settings
from basilica_financeiro.database import connect, migrate
from basilica_financeiro.paths import AppPaths
from basilica_financeiro.repositories.finance import create_financial_account, record_revenue
from basilica_financeiro.services.asaas import AsaasClient
from basilica_financeiro.services.asaas_sync import (
    accept_asaas_match,
    cancel_asaas_reconciliation,
    list_asaas_payments,
    list_asaas_reconciliations,
    suggest_asaas_matches,
    sync_asaas_payments,
)


def test_asaas_client_lists_paginated_payments_without_exposing_token() -> None:
    calls: list[dict[str, object]] = []

    def transport(
        *,
        url: str,
        headers: dict[str, str],
        params: dict[str, str | int],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        calls.append({"url": url, "headers": headers, "params": params})
        if params["offset"] == 0:
            return {
                "hasMore": True,
                "data": [_payment_payload("pay_1", value=123.45)],
            }
        return {
            "hasMore": False,
            "data": [_payment_payload("pay_2", value=10)],
        }

    client = AsaasClient(api_key="test-token", environment="sandbox", transport=transport)

    payments = client.list_payments(due_date_start=date(2026, 6, 1), limit=1)

    assert [payment.asaas_id for payment in payments] == ["pay_1", "pay_2"]
    assert payments[0].value_cents == 12_345
    assert calls[0]["url"] == "https://api-sandbox.asaas.com/v3/payments"
    assert calls[0]["headers"]["access_token"] == "test-token"
    assert calls[0]["params"]["dueDate[ge]"] == "2026-06-01"


def test_sync_asaas_payments_requires_env_key(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        with pytest.raises(ValueError, match="ASAAS_API_KEY"):
            sync_asaas_payments(
                connection,
                settings=_settings(tmp_path, asaas_api_key=None),
                actor_user_id=None,
            )


def test_sync_asaas_payments_stores_snapshots_and_suggests_obvious_match(
    tmp_path: Path,
) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        account_id = create_financial_account(
            connection,
            name="Asaas",
            account_type="asaas",
            opening_balance_cents=0,
            balance_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        record_revenue(
            connection,
            account_id=account_id,
            amount_cents=12_345,
            description="Dizimo recebido",
            effective_date=date(2026, 6, 16),
            actor_user_id=None,
        )
        client = AsaasClient(
            api_key="test-token",
            environment="sandbox",
            transport=lambda **_: {
                "hasMore": False,
                "data": [_payment_payload("pay_1", value=123.45)],
            },
        )

        result = sync_asaas_payments(
            connection,
            settings=_settings(tmp_path, asaas_api_key="test-token"),
            actor_user_id=None,
            client=client,
        )

        payments = list_asaas_payments(connection)
        suggestions = suggest_asaas_matches(connection)
        assert result.fetched_count == 1
        assert result.stored_count == 1
        assert payments[0]["asaas_id"] == "pay_1"
        assert suggestions[0]["confidence"] == 100
        assert suggestions[0]["transaction_description"] == "Dizimo recebido"


def test_accept_asaas_match_records_audited_reconciliation(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        transaction_id = _seed_revenue_and_asaas_payment(connection, tmp_path)

        reconciliation_id = accept_asaas_match(
            connection,
            asaas_id="pay_1",
            transaction_id=transaction_id,
            actor_user_id=None,
            confidence=100,
            reason="Mesmo valor e mesma data de recebimento",
        )

        suggestions = suggest_asaas_matches(connection)
        reconciliations = list_asaas_reconciliations(connection)
        audit = connection.execute(
            """
            SELECT action, entity
            FROM audit_log
            WHERE entity = 'asaas_reconciliation'
            """
        ).fetchone()
        assert reconciliation_id > 0
        assert suggestions == []
        assert reconciliations[0]["asaas_id"] == "pay_1"
        assert reconciliations[0]["transaction_id"] == transaction_id
        assert audit["action"] == "accept_match"


def test_accept_asaas_match_rejects_amount_mismatch(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        transaction_id = _seed_revenue_and_asaas_payment(connection, tmp_path)
        connection.execute(
            "UPDATE asaas_payments SET value_cents = ? WHERE asaas_id = ?",
            (9_999, "pay_1"),
        )

        with pytest.raises(ValueError, match="mesmo valor"):
            accept_asaas_match(
                connection,
                asaas_id="pay_1",
                transaction_id=transaction_id,
                actor_user_id=None,
                confidence=100,
                reason="Mesmo valor e mesma data de recebimento",
            )


def test_cancel_asaas_reconciliation_restores_suggestion_and_can_reaccept(
    tmp_path: Path,
) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        transaction_id = _seed_revenue_and_asaas_payment(connection, tmp_path)
        reconciliation_id = accept_asaas_match(
            connection,
            asaas_id="pay_1",
            transaction_id=transaction_id,
            actor_user_id=None,
            confidence=100,
            reason="Mesmo valor e mesma data de recebimento",
        )

        cancel_asaas_reconciliation(
            connection,
            reconciliation_id=reconciliation_id,
            actor_user_id=None,
        )

        suggestions = suggest_asaas_matches(connection)
        reconciliations = list_asaas_reconciliations(connection)
        audit = connection.execute(
            """
            SELECT action
            FROM audit_log
            WHERE entity = 'asaas_reconciliation'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        reaccepted_id = accept_asaas_match(
            connection,
            asaas_id="pay_1",
            transaction_id=transaction_id,
            actor_user_id=None,
            confidence=100,
            reason="Mesmo valor e mesma data de recebimento",
        )

        assert suggestions[0]["asaas_id"] == "pay_1"
        assert reconciliations == []
        assert audit["action"] == "cancel_match"
        assert reaccepted_id == reconciliation_id
        assert len(list_asaas_reconciliations(connection)) == 1


def test_asaas_local_filters_by_status_text_and_period(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        transaction_id = _seed_revenue_and_asaas_payment(connection, tmp_path)
        _seed_asaas_payment_snapshot(
            connection,
            asaas_id="pay_2",
            value=10,
            status="PENDING",
            payment_date=None,
            customer_name="Devoto",
        )
        accept_asaas_match(
            connection,
            asaas_id="pay_1",
            transaction_id=transaction_id,
            actor_user_id=None,
            confidence=100,
            reason="Mesmo valor e mesma data de recebimento",
        )

        received = list_asaas_payments(connection, status="RECEIVED")
        searched = list_asaas_payments(connection, search="Devoto")
        suggestions = suggest_asaas_matches(
            connection,
            start_date=date(2026, 6, 17),
            end_date=date(2026, 6, 30),
        )
        reconciliations = list_asaas_reconciliations(
            connection,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )

        assert [payment["asaas_id"] for payment in received] == ["pay_1"]
        assert [payment["asaas_id"] for payment in searched] == ["pay_2"]
        assert suggestions == []
        assert reconciliations[0]["asaas_id"] == "pay_1"


def _settings(tmp_path: Path, *, asaas_api_key: str | None) -> Settings:
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
        asaas_api_key=asaas_api_key,
        asaas_enable_write_operations=False,
        pdv_database_url=None,
        google_client_secret_path=None,
        google_token_path=None,
        paths=AppPaths.from_workspace(tmp_path),
    )


def _seed_asaas_payment_snapshot(
    connection,
    *,
    asaas_id: str,
    value: float,
    status: str,
    payment_date: str | None,
    customer_name: str,
) -> None:
    client = AsaasClient(
        api_key="test-token",
        environment="sandbox",
        transport=lambda **_: {
            "hasMore": False,
            "data": [
                {
                    **_payment_payload(asaas_id, value=value),
                    "status": status,
                    "paymentDate": payment_date,
                    "customerName": customer_name,
                }
            ],
        },
    )
    sync_asaas_payments(
        connection,
        settings=_settings(Path("."), asaas_api_key="test-token"),
        actor_user_id=None,
        client=client,
    )


def _seed_revenue_and_asaas_payment(connection, tmp_path: Path) -> int:
    account_id = create_financial_account(
        connection,
        name="Asaas",
        account_type="asaas",
        opening_balance_cents=0,
        balance_date=date(2026, 6, 16),
        actor_user_id=None,
    )
    transaction_id = record_revenue(
        connection,
        account_id=account_id,
        amount_cents=12_345,
        description="Dizimo recebido",
        effective_date=date(2026, 6, 16),
        actor_user_id=None,
    )
    client = AsaasClient(
        api_key="test-token",
        environment="sandbox",
        transport=lambda **_: {
            "hasMore": False,
            "data": [_payment_payload("pay_1", value=123.45)],
        },
    )
    sync_asaas_payments(
        connection,
        settings=_settings(tmp_path, asaas_api_key="test-token"),
        actor_user_id=None,
        client=client,
    )
    return transaction_id


def _payment_payload(asaas_id: str, *, value: float) -> dict[str, object]:
    return {
        "id": asaas_id,
        "status": "RECEIVED",
        "value": value,
        "netValue": value,
        "dueDate": "2026-06-16",
        "paymentDate": "2026-06-16",
        "customerName": "Fiel",
        "description": "Dizimo",
        "billingType": "PIX",
        "externalReference": None,
    }
