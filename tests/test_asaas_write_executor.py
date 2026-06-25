import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from basilica_financeiro.config import Settings
from basilica_financeiro.database import connect, migrate
from basilica_financeiro.paths import AppPaths
from basilica_financeiro.repositories.users import create_user
from basilica_financeiro.services.approvals import (
    approve_sensitive_operation_request,
    create_sensitive_operation_request,
    get_sensitive_operation_request,
)
from basilica_financeiro.services.asaas_write_executor import (
    build_asaas_execution_readiness_json,
    build_asaas_execution_report_json,
    build_asaas_sandbox_validation_package_files,
    build_asaas_sandbox_validation_package_verification_json,
    build_asaas_sandbox_validation_review_summary_markdown,
    execute_approved_asaas_operation,
    get_asaas_execution_readiness,
    get_sensitive_operation_execution,
    list_sensitive_operation_executions,
    urllib_asaas_write_transport,
    write_asaas_sandbox_validation_package,
)


def test_execute_approved_asaas_operation_is_disabled_by_default(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, actor_id = _approved_request(connection)

        with pytest.raises(ValueError, match="desabilitada"):
            execute_approved_asaas_operation(
                connection,
                settings=_settings(tmp_path, writes_enabled=False),
                request_id=request_id,
                actor_user_id=actor_id,
                transport=lambda **_: {"id": "pay_123"},
            )

        assert get_sensitive_operation_execution(connection, request_id=request_id) is None


def test_get_asaas_execution_readiness_reports_disabled_config(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, _ = _approved_request(connection)

        readiness = get_asaas_execution_readiness(
            connection,
            settings=_settings(tmp_path, writes_enabled=False, asaas_api_key=None),
            request_id=request_id,
        )

    assert not readiness.ready
    assert readiness.idempotency_key == f"basilica-sensitive-operation-{request_id}"
    assert readiness.reasons == [
        "Escrita no Asaas esta desabilitada por configuracao",
        "ASAAS_API_KEY nao configurada no .env local",
    ]


def test_build_asaas_execution_readiness_json_is_safe_metadata(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, _ = _approved_request(connection)

        content = build_asaas_execution_readiness_json(
            connection,
            settings=_settings(
                tmp_path,
                writes_enabled=True,
                asaas_api_key="test-token",
            ),
            request_id=request_id,
        )

    payload = json.loads(content)

    assert payload["metadata_only"] is True
    assert payload["contains_credentials"] is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_write_operation"] is False
    assert payload["environment"] == "sandbox"
    assert payload["write_operations_enabled"] is True
    assert payload["api_key_configured"] is True
    assert payload["request_id"] == request_id
    assert payload["operation_type"] == "asaas_create_charge"
    assert payload["readiness_ready"] is True
    assert payload["idempotency_key"] == f"basilica-sensitive-operation-{request_id}"
    assert "test-token" not in content


def test_build_asaas_execution_report_json_omits_payload_response_and_token(
    tmp_path: Path,
) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, actor_id = _approved_request(connection)
        execute_approved_asaas_operation(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
            actor_user_id=actor_id,
            transport=lambda **_: {
                "id": "pay_123",
                "status": "PENDING",
                "invoiceUrl": "https://sandbox.local/cobranca",
            },
        )

        content = build_asaas_execution_report_json(
            connection,
            settings=_settings(
                tmp_path,
                writes_enabled=True,
                asaas_api_key="test-token",
            ),
            request_id=request_id,
        )

    payload = json.loads(content)

    assert payload == {
        "contains_api_response": False,
        "contains_credentials": False,
        "contains_request_payload": False,
        "environment": "sandbox",
        "error_recorded": False,
        "executes_write_operation": False,
        "execution_id": 1,
        "execution_registered": True,
        "execution_status": "succeeded",
        "external_id": "pay_123",
        "idempotency_key": f"basilica-sensitive-operation-{request_id}",
        "metadata_only": True,
        "opens_external_connection": False,
        "operation_type": "asaas_create_charge",
        "request_id": request_id,
        "request_status": "executed",
    }
    assert "test-token" not in content
    assert "invoiceUrl" not in content
    assert "Dizimo mensal" not in content


def test_asaas_sandbox_validation_package_files_are_safe_metadata(
    tmp_path: Path,
) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, actor_id = _approved_request(connection)
        execute_approved_asaas_operation(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
            actor_user_id=actor_id,
            transport=lambda **_: {
                "id": "pay_123",
                "status": "PENDING",
                "invoiceUrl": "https://sandbox.local/cobranca",
            },
        )
        files = build_asaas_sandbox_validation_package_files(
            connection,
            settings=_settings(
                tmp_path,
                writes_enabled=True,
                asaas_api_key="test-token",
            ),
            request_id=request_id,
        )

    manifest = json.loads(files["manifesto-homologacao-asaas.json"])
    joined_content = "\n".join(files.values())

    assert set(files) == {
        "README.md",
        "checklist-validacao-sandbox-asaas.md",
        "prontidao-execucao-asaas.json",
        "evidencia-execucao-asaas.json",
        "manifesto-homologacao-asaas.json",
    }
    assert manifest["metadata_only"] is True
    assert manifest["contains_credentials"] is False
    assert manifest["contains_request_payload"] is False
    assert manifest["contains_api_response"] is False
    assert manifest["opens_external_connection"] is False
    assert manifest["executes_write_operation"] is False
    assert manifest["files"]["README.md"]["sha256"]
    assert "test-token" not in joined_content
    assert "invoiceUrl" not in joined_content
    assert "Dizimo mensal" not in joined_content


def test_write_asaas_sandbox_validation_package_includes_hash_manifest(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "homologacao-asaas.zip"
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, _ = _approved_request(connection)
        write_asaas_sandbox_validation_package(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
            output_path=output_path,
        )

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifesto-homologacao-asaas.json").decode("utf-8"))
        readiness = archive.read("prontidao-execucao-asaas.json")

    assert names == {
        "README.md",
        "checklist-validacao-sandbox-asaas.md",
        "prontidao-execucao-asaas.json",
        "evidencia-execucao-asaas.json",
        "manifesto-homologacao-asaas.json",
    }
    assert manifest["files"]["prontidao-execucao-asaas.json"]["bytes"] == len(readiness)
    assert len(manifest["files"]["prontidao-execucao-asaas.json"]["sha256"]) == 64


def test_verify_asaas_sandbox_validation_package_accepts_safe_zip(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "homologacao-asaas.zip"
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, _ = _approved_request(connection)
        write_asaas_sandbox_validation_package(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
            output_path=output_path,
        )

    payload = json.loads(
        build_asaas_sandbox_validation_package_verification_json(
            package_path=output_path,
        )
    )

    assert payload["metadata_only"] is True
    assert payload["opens_external_connection"] is False
    assert payload["executes_write_operation"] is False
    assert payload["expected_files_present"] is True
    assert payload["manifest_present"] is True
    assert payload["safe_flags_valid"] is True
    assert payload["hashes_valid"] is True
    assert payload["contains_disallowed_markers"] is False
    assert payload["ready_for_review"] is True


def test_verify_asaas_sandbox_validation_package_rejects_tampered_zip(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "homologacao-asaas.zip"
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, _ = _approved_request(connection)
        write_asaas_sandbox_validation_package(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
            output_path=output_path,
        )
    with zipfile.ZipFile(output_path, mode="a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("segredo.txt", "access_token=test-token")

    payload = json.loads(
        build_asaas_sandbox_validation_package_verification_json(
            package_path=output_path,
        )
    )

    assert payload["expected_files_present"] is False
    assert payload["unexpected_files"] == ["segredo.txt"]
    assert payload["contains_disallowed_markers"] is True
    assert payload["ready_for_review"] is False


def test_build_asaas_sandbox_validation_review_summary_is_safe_markdown(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "homologacao-asaas.zip"
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, actor_id = _approved_request(connection)
        execute_approved_asaas_operation(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
            actor_user_id=actor_id,
            transport=lambda **_: {
                "id": "pay_123",
                "status": "PENDING",
                "invoiceUrl": "https://sandbox.local/cobranca",
            },
        )
        write_asaas_sandbox_validation_package(
            connection,
            settings=_settings(
                tmp_path,
                writes_enabled=True,
                asaas_api_key="test-token",
            ),
            request_id=request_id,
            output_path=output_path,
        )

    content = build_asaas_sandbox_validation_review_summary_markdown(
        package_path=output_path,
    )

    assert "# Resumo de aceite do pacote Asaas Sandbox" in content
    assert "Status: **pronto para revisao tecnica**" in content
    assert "- [x] Arquivos esperados presentes" in content
    assert "- [x] Marcadores sensiveis ausentes" in content
    assert "test-token" not in content
    assert "invoiceUrl" not in content
    assert "Dizimo mensal" not in content


def test_get_asaas_execution_readiness_accepts_approved_sandbox_config(
    tmp_path: Path,
) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, _ = _approved_request(connection)

        readiness = get_asaas_execution_readiness(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
        )

    assert readiness.ready
    assert readiness.reasons == []
    assert readiness.idempotency_key == f"basilica-sensitive-operation-{request_id}"


def test_execute_approved_asaas_operation_uses_idempotency_and_marks_executed(
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    def transport(
        *,
        url: str,
        method: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        calls.append(
            {
                "url": url,
                "method": method,
                "headers": headers,
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"id": "pay_123", "status": "PENDING"}

    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, actor_id = _approved_request(connection)

        first = execute_approved_asaas_operation(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
            actor_user_id=actor_id,
            transport=transport,
        )
        second = execute_approved_asaas_operation(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
            actor_user_id=actor_id,
            transport=transport,
        )
        executions = list_sensitive_operation_executions(connection, request_id=request_id)
        request = get_sensitive_operation_request(connection, request_id)

    assert first.status == "succeeded"
    assert first.external_id == "pay_123"
    assert second.id == first.id
    assert [execution.id for execution in executions] == [first.id]
    assert request.status == "executed"
    assert len(calls) == 1
    assert calls[0]["url"] == "https://api-sandbox.asaas.com/v3/payments"
    assert calls[0]["method"] == "POST"
    assert calls[0]["headers"]["idempotency-key"] == (f"basilica-sensitive-operation-{request_id}")
    assert calls[0]["headers"]["access_token"] == "test-token"
    assert calls[0]["body"]["value"] == "150.00"


def test_execute_approved_asaas_operation_records_failed_attempt(tmp_path: Path) -> None:
    def transport(**_: object) -> dict[str, Any]:
        raise ValueError("Asaas retornou HTTP 400")

    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, actor_id = _approved_request(connection)

        execution = execute_approved_asaas_operation(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
            actor_user_id=actor_id,
            transport=transport,
        )
        request = get_sensitive_operation_request(connection, request_id)

    assert execution.status == "failed"
    assert execution.error_message == "Asaas retornou HTTP 400"
    assert request.status == "approved"


def test_get_asaas_execution_readiness_blocks_existing_attempt(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        request_id, actor_id = _approved_request(connection)

        execute_approved_asaas_operation(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
            actor_user_id=actor_id,
            transport=lambda **_: {"id": "pay_123"},
        )
        readiness = get_asaas_execution_readiness(
            connection,
            settings=_settings(tmp_path, writes_enabled=True),
            request_id=request_id,
        )

    assert not readiness.ready
    assert readiness.reasons == [
        "Solicitacao ja possui tentativa de execucao registrada",
        "Solicitacao precisa estar aprovada por dois usuarios distintos",
    ]


def test_execute_approved_asaas_operation_requires_approved_request(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        requester_id, _, _ = _create_users(connection)
        request_id = create_sensitive_operation_request(
            connection,
            operation_type="asaas_cancel_charge",
            title="Cancelar cobranca",
            payload={"asaas_id": "pay_123", "reason": "duplicidade"},
            requested_by=requester_id,
        )

        with pytest.raises(ValueError, match="aprovada"):
            execute_approved_asaas_operation(
                connection,
                settings=_settings(tmp_path, writes_enabled=True),
                request_id=request_id,
                actor_user_id=requester_id,
                transport=lambda **_: {"id": "pay_123"},
            )


def test_urllib_asaas_write_transport_posts_safe_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> bool:
            return False

        def read(self) -> bytes:
            return b'{"id": "pay_123", "status": "PENDING"}'

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured["url"] = request.full_url  # type: ignore[attr-defined]
        captured["method"] = request.get_method()  # type: ignore[attr-defined]
        captured["data"] = request.data  # type: ignore[attr-defined]
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "basilica_financeiro.services.asaas_write_executor.urlopen",
        fake_urlopen,
    )

    response = urllib_asaas_write_transport(
        url="https://api-sandbox.asaas.com/v3/payments",
        method="POST",
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "access_token": "test-token",
        },
        body={"customer": "cus_123", "value": "10.00"},
        timeout_seconds=20,
    )

    assert response == {"id": "pay_123", "status": "PENDING"}
    assert captured["url"] == "https://api-sandbox.asaas.com/v3/payments"
    assert captured["method"] == "POST"
    assert captured["data"] == b'{"customer": "cus_123", "value": "10.00"}'
    assert captured["timeout"] == 20


def test_urllib_asaas_write_transport_omits_empty_delete_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> bool:
            return False

        def read(self) -> bytes:
            return b'{"id": "pay_123", "deleted": true}'

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured["method"] = request.get_method()  # type: ignore[attr-defined]
        captured["data"] = request.data  # type: ignore[attr-defined]
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "basilica_financeiro.services.asaas_write_executor.urlopen",
        fake_urlopen,
    )

    response = urllib_asaas_write_transport(
        url="https://api-sandbox.asaas.com/v3/payments/pay_123",
        method="DELETE",
        headers={"access_token": "test-token"},
        body={},
        timeout_seconds=20,
    )

    assert response == {"id": "pay_123", "deleted": True}
    assert captured == {"method": "DELETE", "data": None, "timeout": 20}


def test_urllib_asaas_write_transport_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        urllib_asaas_write_transport(
            url="http://api-sandbox.asaas.com/v3/payments",
            method="POST",
            headers={},
            body={},
            timeout_seconds=20,
        )


def _approved_request(connection) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    requester_id, first_approver_id, second_approver_id = _create_users(connection)
    request_id = create_sensitive_operation_request(
        connection,
        operation_type="asaas_create_charge",
        title="Criar cobranca",
        amount_cents=15_000,
        payload={
            "customer_id": "cus_123",
            "description": "Dizimo mensal",
            "value_cents": 15_000,
        },
        requested_by=requester_id,
    )
    approve_sensitive_operation_request(
        connection,
        request_id=request_id,
        approver_user_id=first_approver_id,
    )
    approve_sensitive_operation_request(
        connection,
        request_id=request_id,
        approver_user_id=second_approver_id,
    )
    return request_id, second_approver_id


def _create_users(connection) -> tuple[int, int, int]:  # type: ignore[no-untyped-def]
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


def _settings(
    tmp_path: Path,
    *,
    writes_enabled: bool,
    asaas_api_key: str | None = "test-token",
) -> Settings:
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
        asaas_enable_write_operations=writes_enabled,
        pdv_database_url=None,
        google_client_secret_path=None,
        google_token_path=None,
        paths=AppPaths.from_workspace(tmp_path),
    )
