from __future__ import annotations

import json
import sqlite3
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from basilica_financeiro.config import Settings
from basilica_financeiro.repositories.audit import record_audit
from basilica_financeiro.services.approvals import get_sensitive_operation_request
from basilica_financeiro.services.asaas import asaas_base_url

_SUPPORTED_ASAAS_WRITE_OPERATIONS = {
    "asaas_create_charge",
    "asaas_cancel_charge",
    "asaas_refund_payment",
}


class AsaasWriteTransport(Protocol):
    def __call__(
        self,
        *,
        url: str,
        method: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        pass


@dataclass(frozen=True)
class SensitiveOperationExecution:
    id: int
    request_id: int
    status: str
    idempotency_key: str
    external_id: str | None
    response: dict[str, Any] | None
    error_message: str | None


@dataclass(frozen=True)
class SensitiveOperationExecutionReadiness:
    ready: bool
    reasons: list[str]
    idempotency_key: str | None


def execute_approved_asaas_operation(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    request_id: int,
    actor_user_id: int | None,
    transport: AsaasWriteTransport,
) -> SensitiveOperationExecution:
    existing = get_sensitive_operation_execution(connection, request_id=request_id)
    if existing is not None:
        return existing
    request = get_sensitive_operation_request(connection, request_id)
    if request.status != "approved":
        raise ValueError("Solicitacao sensivel precisa estar aprovada para execucao")
    if request.operation_type not in _SUPPORTED_ASAAS_WRITE_OPERATIONS:
        raise ValueError("Solicitacao nao corresponde a escrita Asaas")
    if not settings.asaas_enable_write_operations:
        raise ValueError("Escrita no Asaas esta desabilitada por configuracao")
    if not settings.asaas_api_key:
        raise ValueError("ASAAS_API_KEY precisa estar configurada no .env")

    idempotency_key = f"basilica-sensitive-operation-{request.id}"
    try:
        response = transport(
            url=_operation_url(settings.asaas_env, request.operation_type, request.payload),
            method=_operation_method(request.operation_type),
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "access_token": settings.asaas_api_key,
                "idempotency-key": idempotency_key,
                "user-agent": "basilica-financeiro/0.1",
            },
            body=_operation_body(request.operation_type, request.payload),
            timeout_seconds=20,
        )
    except ValueError as exc:
        return _record_execution(
            connection,
            request_id=request_id,
            status="failed",
            idempotency_key=idempotency_key,
            external_id=None,
            response=None,
            error_message=str(exc),
            actor_user_id=actor_user_id,
        )
    external_id = response.get("id")
    execution = _record_execution(
        connection,
        request_id=request_id,
        status="succeeded",
        idempotency_key=idempotency_key,
        external_id=external_id if isinstance(external_id, str) else None,
        response=response,
        error_message=None,
        actor_user_id=actor_user_id,
    )
    connection.execute(
        """
        UPDATE sensitive_operation_requests
        SET status = 'executed', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (request_id,),
    )
    record_audit(
        connection,
        user_id=actor_user_id,
        action="execute",
        entity="sensitive_operation_request",
        entity_id=str(request_id),
        before={"status": "approved"},
        after={"status": "executed", "execution_id": execution.id},
        origin="asaas",
        result="success",
    )
    return execution


def get_asaas_execution_readiness(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    request_id: int,
) -> SensitiveOperationExecutionReadiness:
    request = get_sensitive_operation_request(connection, request_id)
    existing = get_sensitive_operation_execution(connection, request_id=request_id)
    reasons: list[str] = []
    if existing is not None:
        reasons.append("Solicitacao ja possui tentativa de execucao registrada")
    if request.status != "approved":
        reasons.append("Solicitacao precisa estar aprovada por dois usuarios distintos")
    if request.operation_type not in _SUPPORTED_ASAAS_WRITE_OPERATIONS:
        reasons.append("Solicitacao nao corresponde a escrita Asaas suportada")
    if not settings.asaas_enable_write_operations:
        reasons.append("Escrita no Asaas esta desabilitada por configuracao")
    if not settings.asaas_api_key:
        reasons.append("ASAAS_API_KEY nao configurada no .env local")
    return SensitiveOperationExecutionReadiness(
        ready=not reasons,
        reasons=reasons,
        idempotency_key=(
            f"basilica-sensitive-operation-{request.id}"
            if request.operation_type in _SUPPORTED_ASAAS_WRITE_OPERATIONS
            else None
        ),
    )


def build_asaas_execution_readiness_json(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    request_id: int,
) -> str:
    request = get_sensitive_operation_request(connection, request_id)
    readiness = get_asaas_execution_readiness(
        connection,
        settings=settings,
        request_id=request_id,
    )
    payload = {
        "metadata_only": True,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_write_operation": False,
        "environment": settings.asaas_env,
        "write_operations_enabled": settings.asaas_enable_write_operations,
        "api_key_configured": bool(settings.asaas_api_key),
        "request_id": request.id,
        "operation_type": request.operation_type,
        "request_status": request.status,
        "readiness_ready": readiness.ready,
        "reasons": readiness.reasons,
        "idempotency_key": readiness.idempotency_key,
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_asaas_execution_report_json(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    request_id: int,
) -> str:
    request = get_sensitive_operation_request(connection, request_id)
    execution = get_sensitive_operation_execution(connection, request_id=request_id)
    payload = {
        "metadata_only": True,
        "contains_credentials": False,
        "contains_request_payload": False,
        "contains_api_response": False,
        "opens_external_connection": False,
        "executes_write_operation": False,
        "environment": settings.asaas_env,
        "request_id": request.id,
        "operation_type": request.operation_type,
        "request_status": request.status,
        "execution_registered": execution is not None,
        "execution_id": None if execution is None else execution.id,
        "execution_status": None if execution is None else execution.status,
        "external_id": None if execution is None else execution.external_id,
        "idempotency_key": None if execution is None else execution.idempotency_key,
        "error_recorded": execution is not None and execution.error_message is not None,
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_asaas_sandbox_validation_package_files(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    request_id: int,
) -> dict[str, str]:
    files = {
        "README.md": _asaas_sandbox_validation_package_readme(),
        "checklist-validacao-sandbox-asaas.md": _asaas_sandbox_validation_checklist(
            request_id=request_id,
        ),
        "prontidao-execucao-asaas.json": build_asaas_execution_readiness_json(
            connection,
            settings=settings,
            request_id=request_id,
        ),
        "evidencia-execucao-asaas.json": build_asaas_execution_report_json(
            connection,
            settings=settings,
            request_id=request_id,
        ),
    }
    return {
        **files,
        "manifesto-homologacao-asaas.json": _asaas_sandbox_validation_manifest(
            settings=settings,
            request_id=request_id,
            files=files,
        ),
    }


def write_asaas_sandbox_validation_package(
    connection: sqlite3.Connection,
    *,
    settings: Settings,
    request_id: int,
    output_path: Path,
) -> None:
    files = build_asaas_sandbox_validation_package_files(
        connection,
        settings=settings,
        request_id=request_id,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name, content in files.items():
            archive.writestr(file_name, content)


def build_asaas_sandbox_validation_package_verification_json(
    *,
    package_path: Path,
) -> str:
    expected_files = {
        "README.md",
        "checklist-validacao-sandbox-asaas.md",
        "prontidao-execucao-asaas.json",
        "evidencia-execucao-asaas.json",
        "manifesto-homologacao-asaas.json",
    }
    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
        contents = {
            name: archive.read(name).decode("utf-8") for name in names if not name.endswith("/")
        }

    manifest_content = contents.get("manifesto-homologacao-asaas.json")
    manifest = json.loads(manifest_content) if manifest_content else {}
    if not isinstance(manifest, dict):
        manifest = {}
    file_manifest = manifest.get("files", {})
    if not isinstance(file_manifest, dict):
        file_manifest = {}

    hash_results = {
        name: _package_file_hash_matches(
            content=content,
            expected=file_manifest.get(name),
        )
        for name, content in contents.items()
        if name != "manifesto-homologacao-asaas.json"
    }
    joined_content = "\n".join(contents.values())
    payload = {
        "metadata_only": True,
        "opens_external_connection": False,
        "executes_write_operation": False,
        "package_path": str(package_path),
        "expected_files_present": names == expected_files,
        "missing_files": sorted(expected_files - names),
        "unexpected_files": sorted(names - expected_files),
        "manifest_present": manifest_content is not None,
        "safe_flags_valid": _asaas_manifest_safe_flags_valid(manifest),
        "hashes_valid": all(hash_results.values()) and len(hash_results) == 4,
        "hash_results": hash_results,
        "contains_disallowed_markers": _package_contains_disallowed_markers(
            joined_content,
        ),
    }
    payload["ready_for_review"] = all(
        [
            payload["expected_files_present"],
            payload["manifest_present"],
            payload["safe_flags_valid"],
            payload["hashes_valid"],
            not payload["contains_disallowed_markers"],
        ]
    )
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_asaas_sandbox_validation_review_summary_markdown(
    *,
    package_path: Path,
) -> str:
    verification = json.loads(
        build_asaas_sandbox_validation_package_verification_json(
            package_path=package_path,
        )
    )
    status = "pronto para revisao tecnica" if verification["ready_for_review"] else "bloqueado"
    gates = [
        ("Arquivos esperados presentes", verification["expected_files_present"]),
        ("Manifesto presente", verification["manifest_present"]),
        ("Flags de seguranca validas", verification["safe_flags_valid"]),
        ("Hashes conferidos", verification["hashes_valid"]),
        (
            "Marcadores sensiveis ausentes",
            not verification["contains_disallowed_markers"],
        ),
    ]
    lines = [
        "# Resumo de aceite do pacote Asaas Sandbox",
        "",
        f"Pacote: `{package_path}`",
        f"Status: **{status}**",
        "",
        "## Gates locais",
        "",
        *[f"- [{'x' if passed else ' '}] {label}" for label, passed in gates],
        "",
        "## Arquivos",
        "",
        f"- Ausentes: {', '.join(verification['missing_files']) or 'nenhum'}",
        f"- Inesperados: {', '.join(verification['unexpected_files']) or 'nenhum'}",
        "",
        "## Segurança",
        "",
        "- Este resumo nao contem chaves, tokens, payload financeiro ou resposta bruta da API.",
        "- A verificacao local nao abre conexao externa e nao executa operacao de escrita.",
        "- Se qualquer gate estiver bloqueado, gere novamente o pacote antes da revisao.",
        "",
    ]
    return "\n".join(lines)


def urllib_asaas_write_transport(
    *,
    url: str,
    method: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    if not url.startswith("https://"):
        raise ValueError("Asaas requer HTTPS")
    if method not in {"POST", "DELETE"}:
        raise ValueError("Metodo Asaas nao suportado")

    data = (
        None
        if method == "DELETE" and not body
        else json.dumps(body, ensure_ascii=True).encode("utf-8")
    )
    request = Request(url, data=data, headers=headers, method=method)  # noqa: S310
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        raise ValueError(f"Asaas retornou HTTP {exc.code}") from exc
    except URLError as exc:
        raise ValueError("Asaas indisponivel no momento") from exc

    parsed = json.loads(payload) if payload.strip() else {}
    if not isinstance(parsed, dict):
        raise ValueError("Resposta do Asaas em formato inesperado")
    return parsed


def get_sensitive_operation_execution(
    connection: sqlite3.Connection,
    *,
    request_id: int,
) -> SensitiveOperationExecution | None:
    row = connection.execute(
        """
        SELECT id, request_id, status, idempotency_key, external_id, response_json, error_message
        FROM sensitive_operation_executions
        WHERE request_id = ?
        """,
        (request_id,),
    ).fetchone()
    return None if row is None else _execution_from_row(row)


def list_sensitive_operation_executions(
    connection: sqlite3.Connection,
    *,
    request_id: int,
) -> list[SensitiveOperationExecution]:
    rows = connection.execute(
        """
        SELECT id, request_id, status, idempotency_key, external_id, response_json, error_message
        FROM sensitive_operation_executions
        WHERE request_id = ?
        ORDER BY id
        """,
        (request_id,),
    ).fetchall()
    return [_execution_from_row(row) for row in rows]


def _record_execution(
    connection: sqlite3.Connection,
    *,
    request_id: int,
    status: str,
    idempotency_key: str,
    external_id: str | None,
    response: dict[str, Any] | None,
    error_message: str | None,
    actor_user_id: int | None,
) -> SensitiveOperationExecution:
    cursor = connection.execute(
        """
        INSERT INTO sensitive_operation_executions (
            request_id, status, idempotency_key, external_id, response_json,
            error_message, executed_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request_id,
            status,
            idempotency_key,
            external_id,
            json.dumps(response, ensure_ascii=True, sort_keys=True) if response else None,
            error_message,
            actor_user_id,
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Falha ao registrar execucao sensivel")
    record_audit(
        connection,
        user_id=actor_user_id,
        action="execute",
        entity="sensitive_operation_execution",
        entity_id=str(cursor.lastrowid),
        before=None,
        after={
            "request_id": request_id,
            "status": status,
            "idempotency_key": idempotency_key,
            "external_id": external_id,
        },
        origin="asaas",
        result="success" if status == "succeeded" else "failed",
    )
    return get_sensitive_operation_execution(connection, request_id=request_id) or (
        _raise_execution_lookup_error()
    )


def _operation_url(environment: str, operation_type: str, payload: dict[str, Any]) -> str:
    base_url = asaas_base_url(environment)
    if operation_type == "asaas_create_charge":
        return f"{base_url}/payments"
    asaas_id = _payload_text(payload, "asaas_id")
    if operation_type == "asaas_cancel_charge":
        return f"{base_url}/payments/{asaas_id}"
    return f"{base_url}/payments/{asaas_id}/refund"


def _operation_method(operation_type: str) -> str:
    if operation_type == "asaas_create_charge":
        return "POST"
    if operation_type == "asaas_cancel_charge":
        return "DELETE"
    return "POST"


def _operation_body(operation_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if operation_type == "asaas_create_charge":
        body = {key: value for key, value in payload.items() if key != "value_cents"}
        value_cents = payload.get("value_cents")
        if isinstance(value_cents, int):
            body["value"] = f"{value_cents / 100:.2f}"
        return body
    return {key: value for key, value in payload.items() if key != "asaas_id"}


def _payload_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Payload precisa conter {key}")
    return value.strip()


def _execution_from_row(row: sqlite3.Row) -> SensitiveOperationExecution:
    response_json = row["response_json"]
    response = None if response_json is None else json.loads(str(response_json))
    if response is not None and not isinstance(response, dict):
        raise ValueError("Resposta de execucao sensivel invalida")
    return SensitiveOperationExecution(
        id=int(row["id"]),
        request_id=int(row["request_id"]),
        status=str(row["status"]),
        idempotency_key=str(row["idempotency_key"]),
        external_id=None if row["external_id"] is None else str(row["external_id"]),
        response=response,
        error_message=None if row["error_message"] is None else str(row["error_message"]),
    )


def _asaas_sandbox_validation_package_readme() -> str:
    return "\n".join(
        [
            "# Pacote local de homologacao Asaas Sandbox",
            "",
            "Este pacote foi gerado localmente para revisar a validacao Sandbox.",
            "",
            "## Seguranca",
            "",
            "- Nao contem chaves, tokens, senhas ou credenciais.",
            "- Nao contem payload financeiro da solicitacao sensivel.",
            "- Nao contem resposta bruta da API Asaas.",
            "- Nao abre conexao externa e nao executa operacao de escrita.",
            "",
            "## Arquivos",
            "",
            "- `checklist-validacao-sandbox-asaas.md`: passos manuais de validacao.",
            "- `prontidao-execucao-asaas.json`: estado local antes da execucao.",
            "- `evidencia-execucao-asaas.json`: resumo local pos-execucao.",
            "- `manifesto-homologacao-asaas.json`: hashes SHA-256 e metadados.",
            "",
        ]
    )


def _asaas_sandbox_validation_checklist(*, request_id: int) -> str:
    return "\n".join(
        [
            "# Checklist de validacao Sandbox Asaas",
            "",
            f"Solicitacao local: #{request_id}",
            "",
            "## Antes da execucao",
            "",
            "- Confirmar `ASAAS_ENV=sandbox` no `.env` local.",
            "- Confirmar `ASAAS_ENABLE_WRITE_OPERATIONS=true` apenas durante a validacao.",
            "- Confirmar que a chave Sandbox esta somente no `.env` local.",
            "- Confirmar que a solicitacao recebeu duas aprovacoes distintas.",
            "- Revisar `prontidao-execucao-asaas.json`.",
            "",
            "## Depois da execucao",
            "",
            "- Conferir a cobranca/cancelamento/estorno no painel Sandbox.",
            "- Revisar `evidencia-execucao-asaas.json`.",
            "- Repetir a execucao e confirmar que a idempotencia reaproveita a tentativa local.",
            "- Desligar `ASAAS_ENABLE_WRITE_OPERATIONS=false` ao encerrar.",
            "",
            "## Nao fazer",
            "",
            "- Nao usar chave de producao nesta etapa.",
            "- Nao copiar chave Asaas para documentos, prints ou argumentos de terminal.",
            "- Nao compartilhar este pacote como prova de pagamento real.",
            "",
        ]
    )


def _asaas_sandbox_validation_manifest(
    *,
    settings: Settings,
    request_id: int,
    files: dict[str, str],
) -> str:
    payload = {
        "metadata_only": True,
        "contains_credentials": False,
        "contains_request_payload": False,
        "contains_api_response": False,
        "opens_external_connection": False,
        "executes_write_operation": False,
        "environment": settings.asaas_env,
        "request_id": request_id,
        "files": {
            name: {
                "sha256": sha256(content.encode("utf-8")).hexdigest(),
                "bytes": len(content.encode("utf-8")),
            }
            for name, content in sorted(files.items())
        },
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def _package_file_hash_matches(*, content: str, expected: object) -> bool:
    if not isinstance(expected, dict):
        return False
    expected_hash = expected.get("sha256")
    expected_bytes = expected.get("bytes")
    encoded = content.encode("utf-8")
    return (
        isinstance(expected_hash, str)
        and expected_hash == sha256(encoded).hexdigest()
        and isinstance(expected_bytes, int)
        and expected_bytes == len(encoded)
    )


def _asaas_manifest_safe_flags_valid(manifest: dict[str, Any]) -> bool:
    expected_flags = {
        "metadata_only": True,
        "contains_credentials": False,
        "contains_request_payload": False,
        "contains_api_response": False,
        "opens_external_connection": False,
        "executes_write_operation": False,
    }
    return all(manifest.get(key) is expected for key, expected in expected_flags.items())


def _package_contains_disallowed_markers(content: str) -> bool:
    markers = [
        "ASAAS_API_KEY=",
        "access_token",
        "invoiceUrl",
        "sk-",
        "AIza",
        "xoxb-",
        "xoxa-",
        "xoxp-",
        "xoxr-",
        "xoxs-",
    ]
    return any(marker in content for marker in markers)


def _raise_execution_lookup_error() -> SensitiveOperationExecution:
    raise RuntimeError("Falha ao consultar execucao sensivel")
