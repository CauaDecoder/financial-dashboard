from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from basilica_financeiro.config import Settings
from basilica_financeiro.database import SCHEMA_VERSION


@dataclass(frozen=True)
class DeploymentReadiness:
    database_backend: str
    database_location: str
    offline_ready: bool
    network_ready: bool
    postgres_ready: bool
    warnings: list[str]
    next_steps: list[str]


@dataclass(frozen=True)
class LocalDatabaseHealth:
    schema_version: int | None
    expected_schema_version: int
    quick_check_ok: bool
    foreign_key_violations: int
    journal_mode: str
    wal_enabled: bool
    critical_table_counts: dict[str, int]

    @property
    def ready_for_migration_rehearsal(self) -> bool:
        return (
            self.schema_version == self.expected_schema_version
            and self.quick_check_ok
            and self.foreign_key_violations == 0
            and self.wal_enabled
        )


@dataclass(frozen=True)
class SchemaCompatibilityFinding:
    severity: str
    location: str
    message: str


@dataclass(frozen=True)
class SchemaCompatibilityReport:
    ready_for_rehearsal: bool
    findings: list[SchemaCompatibilityFinding]


@dataclass(frozen=True)
class PostgresLoadPlanStep:
    table_name: str
    dependencies: list[str]
    critical_row_count: int | None


@dataclass(frozen=True)
class PostgresLoadPlan:
    ready_for_load_rehearsal: bool
    steps: list[PostgresLoadPlanStep]
    unresolved_tables: list[str]


@dataclass(frozen=True)
class PostgresRehearsalPreflightCheck:
    status: str
    code: str
    message: str


@dataclass(frozen=True)
class PostgresRehearsalPreflight:
    ready_to_run: bool
    checks: list[PostgresRehearsalPreflightCheck]


class PostgresRehearsalTransport(Protocol):
    def __call__(
        self,
        *,
        target_database_url: str,
        execution_plan: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        pass


@dataclass(frozen=True)
class PostgresRehearsalExecutionReadiness:
    ready: bool
    reasons: list[str]
    target_database_location: str | None
    driver_available: bool


@dataclass(frozen=True)
class PostgresRehearsalExecutionResult:
    status: str
    target_database_location: str
    executed_steps: int | None


def build_network_readiness_json(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth | None,
) -> str:
    sqlite_health_ready = None if health is None else health.ready_for_migration_rehearsal
    backup_configured = bool(settings.backup_encryption_key)
    ready_for_network_use = (
        readiness.network_ready
        and readiness.postgres_ready
        and backup_configured
        and settings.database_url.startswith(
            ("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")
        )
    )
    checks = [
        {
            "status": "blocked" if readiness.database_backend == "sqlite" else "ok",
            "code": "sqlite_multiwriter_guard",
            "message": (
                "SQLite local permanece permitido apenas para uso offline em uma instalacao."
                if readiness.database_backend == "sqlite"
                else "Backend operacional nao esta em SQLite local."
            ),
        },
        {
            "status": "ok" if readiness.network_ready else "blocked",
            "code": "network_backend_guard",
            "message": (
                "Backend atual indica suporte de rede."
                if readiness.network_ready
                else "Uso em rede exige backend homologado antes de multiplas instalacoes."
            ),
        },
        {
            "status": "ok" if readiness.postgres_ready else "blocked",
            "code": "postgres_adapter_guard",
            "message": (
                "Adapter PostgreSQL operacional esta pronto."
                if readiness.postgres_ready
                else "PostgreSQL ainda requer adapter, migracao e testes de concorrencia."
            ),
        },
        {
            "status": (
                "not_applicable"
                if sqlite_health_ready is None
                else "ok"
                if sqlite_health_ready
                else "blocked"
            ),
            "code": "sqlite_origin_health",
            "message": (
                "Preflight SQLite nao se aplica ao backend atual."
                if sqlite_health_ready is None
                else "Origem SQLite esta integra para ensaio."
                if sqlite_health_ready
                else "Saneie schema, integridade, chaves estrangeiras e WAL antes da transicao."
            ),
        },
        {
            "status": "ok" if backup_configured else "warning",
            "code": "backup_encryption_guard",
            "message": (
                "Chave de backup foi configurada localmente."
                if backup_configured
                else "Configure BACKUP_ENCRYPTION_KEY no .env local antes de homologar rede."
            ),
        },
        {
            "status": "ok",
            "code": "secret_handling_guard",
            "message": "Este relatorio mascara URLs e nao inclui chaves, tokens ou senhas.",
        },
    ]
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "offline_ready": readiness.offline_ready,
        "network_ready": readiness.network_ready,
        "postgres_ready": readiness.postgres_ready,
        "ready_for_network_use": ready_for_network_use,
        "sqlite_origin_health_ready": sqlite_health_ready,
        "backup_auto_daily": settings.backup_auto_daily,
        "backup_encryption_configured": backup_configured,
        "warnings": readiness.warnings,
        "next_steps": [
            *readiness.next_steps,
            "Validar restauracao de backup em copia descartavel antes do uso em rede",
            "Executar homologacao PostgreSQL com alvo vazio e descartavel",
            "Rodar testes de concorrencia com usuarios simultaneos antes de operacao real",
        ],
        "checks": checks,
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_network_rehearsal_package_files(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth | None,
) -> dict[str, str]:
    files = {
        "README.md": _network_rehearsal_package_readme(),
        "prontidao-uso-em-rede.json": build_network_readiness_json(
            settings=settings,
            readiness=readiness,
            health=health,
        ),
        "checklist-homologacao-rede.md": build_network_rehearsal_checklist(
            settings=settings,
            readiness=readiness,
            health=health,
        ),
    }
    return {
        **files,
        "manifesto-homologacao-rede.json": _network_rehearsal_manifest(
            settings=settings,
            readiness=readiness,
            health=health,
            files=files,
        ),
    }


def write_network_rehearsal_package(
    *,
    output_path: Path,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth | None,
) -> None:
    files = build_network_rehearsal_package_files(
        settings=settings,
        readiness=readiness,
        health=health,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name, content in files.items():
            archive.writestr(file_name, content)


def build_network_rehearsal_package_verification_json(
    *,
    package_path: Path,
) -> str:
    expected_files = {
        "README.md",
        "prontidao-uso-em-rede.json",
        "checklist-homologacao-rede.md",
        "manifesto-homologacao-rede.json",
    }
    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
        contents = {
            name: archive.read(name).decode("utf-8") for name in names if not name.endswith("/")
        }

    manifest_content = contents.get("manifesto-homologacao-rede.json")
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
        if name != "manifesto-homologacao-rede.json"
    }
    joined_content = "\n".join(contents.values())
    payload = {
        "metadata_only": True,
        "opens_external_connection": False,
        "executes_migration": False,
        "package_path": str(package_path),
        "expected_files_present": names == expected_files,
        "missing_files": sorted(expected_files - names),
        "unexpected_files": sorted(names - expected_files),
        "manifest_present": manifest_content is not None,
        "safe_flags_valid": _network_manifest_safe_flags_valid(manifest),
        "hashes_valid": all(hash_results.values()) and len(hash_results) == 3,
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


def build_network_rehearsal_review_summary_markdown(
    *,
    package_path: Path,
) -> str:
    verification = json.loads(
        build_network_rehearsal_package_verification_json(
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
    return "\n".join(
        [
            "# Resumo de aceite do pacote de rede",
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
            "## Seguranca",
            "",
            "- Este resumo nao contem credenciais, linhas financeiras, usuarios ou documentos.",
            "- A verificacao local nao abre conexao externa e nao executa migracao.",
            "- Se qualquer gate estiver bloqueado, gere novamente o pacote antes da revisao.",
            "",
        ]
    )


def build_postgres_rehearsal_package_verification_json(
    *,
    package_path: Path,
) -> str:
    expected_files = {
        "README.md",
        "roteiro-migracao-postgresql.md",
        "inventario-schema-sqlite.json",
        "compatibilidade-postgresql.md",
        "plano-carga-postgresql.json",
        "contrato-adapter-postgresql.json",
        "plano-execucao-homologacao-postgresql.json",
        "preflight-runner-homologacao-postgresql.json",
        "prontidao-runner-homologacao-postgresql.json",
        "blueprint-postgresql.sql",
        "manifesto-homologacao.json",
    }
    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
        contents = {
            name: archive.read(name).decode("utf-8") for name in names if not name.endswith("/")
        }

    manifest_content = contents.get("manifesto-homologacao.json")
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
        if name != "manifesto-homologacao.json"
    }
    joined_content = "\n".join(contents.values())
    payload = {
        "metadata_only": True,
        "opens_external_connection": False,
        "executes_migration": False,
        "package_path": str(package_path),
        "expected_files_present": names == expected_files,
        "missing_files": sorted(expected_files - names),
        "unexpected_files": sorted(names - expected_files),
        "manifest_present": manifest_content is not None,
        "safe_flags_valid": _network_manifest_safe_flags_valid(manifest),
        "hashes_valid": all(hash_results.values()) and len(hash_results) == 10,
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


def build_postgres_rehearsal_review_summary_markdown(
    *,
    package_path: Path,
) -> str:
    verification = json.loads(
        build_postgres_rehearsal_package_verification_json(
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
    return "\n".join(
        [
            "# Resumo de aceite do pacote PostgreSQL",
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
            "## Seguranca",
            "",
            "- Este resumo nao contem credenciais, linhas financeiras, usuarios ou documentos.",
            "- A verificacao local nao abre conexao externa e nao executa migracao.",
            "- O SQL do blueprint permanece artefato de revisao tecnica, nao de execucao.",
            "- Se qualquer gate estiver bloqueado, gere novamente o pacote antes da revisao.",
            "",
        ]
    )


def build_phase8_local_evidence_package_verification_json(
    *,
    package_path: Path,
) -> str:
    expected_files = {
        "README.md",
        "aceite-local-fase-8.md",
        "prontidao-uso-em-rede.json",
        "prontidao-runner-homologacao-postgresql.json",
        "manifesto-evidencias-fase-8.json",
    }
    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
        contents = {
            name: archive.read(name).decode("utf-8") for name in names if not name.endswith("/")
        }

    manifest_content = contents.get("manifesto-evidencias-fase-8.json")
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
        if name != "manifesto-evidencias-fase-8.json"
    }
    joined_content = "\n".join(contents.values())
    payload = {
        "metadata_only": True,
        "opens_external_connection": False,
        "executes_migration": False,
        "package_path": str(package_path),
        "expected_files_present": names == expected_files,
        "missing_files": sorted(expected_files - names),
        "unexpected_files": sorted(names - expected_files),
        "manifest_present": manifest_content is not None,
        "safe_flags_valid": _network_manifest_safe_flags_valid(manifest),
        "phase_completion_guard_valid": manifest.get("phase_complete") is False,
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
            payload["phase_completion_guard_valid"],
            payload["hashes_valid"],
            not payload["contains_disallowed_markers"],
        ]
    )
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_phase8_local_evidence_review_summary_markdown(
    *,
    package_path: Path,
) -> str:
    verification = json.loads(
        build_phase8_local_evidence_package_verification_json(
            package_path=package_path,
        )
    )
    status = "pronto para revisao tecnica" if verification["ready_for_review"] else "bloqueado"
    gates = [
        ("Arquivos esperados presentes", verification["expected_files_present"]),
        ("Manifesto presente", verification["manifest_present"]),
        ("Flags de seguranca validas", verification["safe_flags_valid"]),
        (
            "Conclusao da fase permanece pendente",
            verification["phase_completion_guard_valid"],
        ),
        ("Hashes conferidos", verification["hashes_valid"]),
        (
            "Marcadores sensiveis ausentes",
            not verification["contains_disallowed_markers"],
        ),
    ]
    return "\n".join(
        [
            "# Resumo de aceite do pacote de evidencias da Fase 8",
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
            "## Seguranca",
            "",
            "- Este resumo nao contem credenciais, linhas financeiras, usuarios ou documentos.",
            "- A verificacao local nao abre conexao externa e nao executa migracao.",
            "- Este pacote nao substitui Sandbox Asaas nem homologacao PostgreSQL real.",
            "- Se qualquer gate estiver bloqueado, gere novamente o pacote antes da revisao.",
            "",
        ]
    )


def build_phase8_closure_readiness_json(
    *,
    asaas_verification_path: Path | None,
    asaas_summary_path: Path | None,
    postgres_package_verification_path: Path | None,
    postgres_rehearsal_report_path: Path | None,
    phase8_package_verification_path: Path | None,
) -> str:
    gates = [
        _json_verification_gate(
            label="Verificacao do pacote Asaas Sandbox",
            path=asaas_verification_path,
        ),
        _markdown_evidence_gate(
            label="Resumo de aceite Asaas Sandbox",
            path=asaas_summary_path,
            required_fragment="# Resumo de aceite do pacote Asaas Sandbox",
        ),
        _json_verification_gate(
            label="Verificacao do pacote PostgreSQL",
            path=postgres_package_verification_path,
        ),
        _postgres_rehearsal_report_gate(
            postgres_rehearsal_report_path,
        ),
        _json_verification_gate(
            label="Verificacao do pacote local da Fase 8",
            path=phase8_package_verification_path,
        ),
    ]
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "executes_write_operation": False,
        "ready_to_close_phase8": all(gate["passed"] for gate in gates),
        "gates": gates,
        "blocking_reasons": [gate["message"] for gate in gates if not gate["passed"]],
        "next_steps": [
            "Executar validacao real no Asaas Sandbox com chave apenas no .env local.",
            "Executar homologacao PostgreSQL em banco vazio e descartavel.",
            "Gerar novamente este relatorio anexando todos os artefatos externos.",
            "Registrar decisao operacional antes de encerrar a Fase 8.",
        ],
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_phase8_closeout_report_markdown(
    *,
    closure_readiness_path: Path,
) -> str:
    content = closure_readiness_path.read_text(encoding="utf-8")
    readiness = json.loads(content)
    contains_disallowed_markers = _package_contains_disallowed_markers(content)
    ready_to_close = (
        readiness.get("ready_to_close_phase8") is True and not contains_disallowed_markers
    )
    status = (
        "Fase 8 pronta para encerramento operacional" if ready_to_close else "Fase 8 ainda pendente"
    )
    gates = readiness.get("gates", [])
    if not isinstance(gates, list):
        gates = []
    blocking_reasons = readiness.get("blocking_reasons", [])
    if not isinstance(blocking_reasons, list):
        blocking_reasons = []

    return "\n".join(
        [
            "# Encerramento da Fase 8",
            "",
            f"Fonte: `{closure_readiness_path}`",
            f"Status: **{status}**",
            "",
            "## Gates finais",
            "",
            *[
                f"- [{'x' if gate.get('passed') else ' '}] {gate.get('label', 'Gate sem nome')}"
                for gate in gates
                if isinstance(gate, dict)
            ],
            "",
            "## Bloqueios",
            "",
            *(
                [f"- {reason}" for reason in blocking_reasons]
                or ["- Nenhum bloqueio informado pelo gate final."]
            ),
            "",
            "## Decisao",
            "",
            (
                "- Resultado: **Fase 8 pode ser encerrada**, desde que a equipe "
                "registre a decisao operacional junto aos artefatos anexados."
                if ready_to_close
                else "- Resultado: **Fase 8 nao deve ser encerrada** ate que todos "
                "os artefatos externos passem no gate final."
            ),
            "- Seguranca: este relatorio nao contem credenciais, linhas financeiras, "
            "payloads de API ou URL sem mascara.",
            "- Execucao: este relatorio nao chama API, nao abre PostgreSQL e nao executa migracao.",
            "",
        ]
    )


def write_phase8_closeout_package(
    *,
    closure_readiness_path: Path,
    closeout_report_path: Path,
    output_path: Path,
) -> None:
    files = {
        "prontidao-fechamento-fase-8.json": closure_readiness_path.read_text(
            encoding="utf-8",
        ),
        "encerramento-fase-8.md": closeout_report_path.read_text(encoding="utf-8"),
    }
    files["manifesto-encerramento-fase-8.json"] = _phase8_closeout_manifest(
        files=files,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name, content in files.items():
            archive.writestr(file_name, content)


def build_phase8_local_acceptance_report_markdown(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth | None,
    inventory: dict[str, Any] | None,
) -> str:
    network_payload = json.loads(
        build_network_readiness_json(
            settings=settings,
            readiness=readiness,
            health=health,
        )
    )
    postgres_runner_payload: dict[str, Any] | None = None
    compatibility_ready = False
    if health is not None and inventory is not None:
        postgres_runner_payload = json.loads(
            build_postgres_rehearsal_runner_readiness_json(
                settings=settings,
                readiness=readiness,
                health=health,
                inventory=inventory,
            )
        )
        compatibility_ready = assess_postgres_schema_compatibility(
            health=health,
            inventory=inventory,
        ).ready_for_rehearsal

    local_gates = [
        (
            "Relatorio sem dados financeiros, usuarios, documentos ou credenciais",
            True,
        ),
        (
            "Diagnostico de rede gerado sem conexao externa",
            not bool(network_payload["opens_external_connection"])
            and not bool(network_payload["executes_migration"]),
        ),
        (
            "SQLite local integro para ensaio",
            bool(health and health.ready_for_migration_rehearsal),
        ),
        (
            "Schema sem bloqueios conhecidos para blueprint PostgreSQL",
            compatibility_ready,
        ),
        (
            "Runner PostgreSQL permanece opt-in e fora da UI operacional",
            not settings.postgres_rehearsal_enable_execution
            or settings.app_env.lower() != "production",
        ),
    ]
    external_gates = [
        "Validar execucao Asaas Sandbox com chave real apenas no `.env` local.",
        "Anexar JSON e resumo Markdown do pacote Asaas gerado apos a execucao Sandbox.",
        "Executar homologacao PostgreSQL em banco vazio, descartavel e com URL no `.env` local.",
        "Anexar relatorio Markdown da homologacao PostgreSQL com URL mascarada.",
        "Registrar decisao operacional antes de habilitar qualquer uso multi-instalacao.",
    ]
    postgres_reasons = (
        postgres_runner_payload["reasons"]
        if postgres_runner_payload is not None
        else ["Preflight PostgreSQL indisponivel porque o backend atual nao e SQLite local."]
    )
    return "\n".join(
        [
            "# Aceite local da Fase 8",
            "",
            "Este relatorio consolida somente evidencias locais e nao substitui "
            "homologacao externa.",
            "",
            "## Escopo",
            "",
            "- Recursos de planejamento, orcamento, projecoes e aprovacoes sensiveis.",
            "- Preparacao de rede/PostgreSQL e pacotes locais de revisao.",
            "- Sem chamada de API, sem conexao PostgreSQL e sem migracao neste relatorio.",
            "",
            "## Estado local",
            "",
            f"- Ambiente: {settings.app_env}",
            f"- Backend operacional: {readiness.database_backend}",
            f"- Local mascarado: {readiness.database_location}",
            f"- Schema: {_schema_status_label(health)}",
            f"- Prontidao de rede operacional: {network_payload['ready_for_network_use']}",
            "- Runner PostgreSQL opt-in pronto: "
            f"{_postgres_runner_ready_label(postgres_runner_payload)}",
            "",
            "## Gates locais",
            "",
            *[f"- [{'x' if passed else ' '}] {label}" for label, passed in local_gates],
            "",
            "## Pendencias externas para fechar a Fase 8",
            "",
            *[f"- [ ] {gate}" for gate in external_gates],
            "",
            "## Motivos atuais de bloqueio PostgreSQL",
            "",
            *[f"- {reason}" for reason in postgres_reasons],
            "",
            "## Comandos seguros sugeridos",
            "",
            "- `uv run python -m basilica_financeiro asaas-readiness "
            "--request-id <id> --output documents/exports/prontidao-asaas-<id>.json`",
            "- `uv run python -m basilica_financeiro asaas-validation-package "
            "--request-id <id> --output "
            "documents/exports/pacote-homologacao-asaas-<id>.zip`",
            "- `uv run python -m basilica_financeiro postgres-validation-package "
            "--output documents/exports/pacote-homologacao-postgresql.zip`",
            "- `uv run python -m basilica_financeiro postgres-verify-package "
            "--package documents/exports/pacote-homologacao-postgresql.zip "
            "--output documents/exports/verificacao-pacote-postgresql.json`",
            "- `uv run python -m basilica_financeiro postgres-rehearsal "
            "--confirm-disposable-target --output "
            "documents/exports/relatorio-homologacao-postgresql.md`",
            "",
            "## Conclusao",
            "",
            "- Resultado: **Fase 8 ainda nao encerrada**.",
            "- Motivo: faltam evidencias reais de Sandbox Asaas e homologacao "
            "PostgreSQL descartavel.",
            "- Seguranca: este relatorio e local, nao contem segredos e nao abre "
            "conexoes externas.",
            "",
        ]
    )


def build_phase8_local_evidence_package_files(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth | None,
    inventory: dict[str, Any] | None,
) -> dict[str, str]:
    files = {
        "README.md": _phase8_local_evidence_package_readme(),
        "aceite-local-fase-8.md": build_phase8_local_acceptance_report_markdown(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        ),
        "prontidao-uso-em-rede.json": build_network_readiness_json(
            settings=settings,
            readiness=readiness,
            health=health,
        ),
        "prontidao-runner-homologacao-postgresql.json": (
            build_postgres_rehearsal_runner_readiness_json(
                settings=settings,
                readiness=readiness,
                health=health,
                inventory=inventory,
            )
            if health is not None and inventory is not None
            else _unavailable_postgres_runner_readiness_json(
                settings=settings,
                readiness=readiness,
            )
        ),
    }
    return {
        **files,
        "manifesto-evidencias-fase-8.json": _phase8_local_evidence_manifest(
            settings=settings,
            readiness=readiness,
            health=health,
            files=files,
        ),
    }


def write_phase8_local_evidence_package(
    *,
    output_path: Path,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth | None,
    inventory: dict[str, Any] | None,
) -> None:
    files = build_phase8_local_evidence_package_files(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name, content in files.items():
            archive.writestr(file_name, content)


def _schema_status_label(health: LocalDatabaseHealth | None) -> str:
    if health is None:
        return "indisponivel para backend atual"
    return f"{health.schema_version}/{health.expected_schema_version}"


def _postgres_runner_ready_label(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return "nao aplicavel"
    return str(payload["ready_for_opt_in_runner"])


def _unavailable_postgres_runner_readiness_json(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
) -> str:
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "target_database_location": None,
        "postgresql_driver_available": False,
        "execution_enabled": settings.postgres_rehearsal_enable_execution,
        "ready_for_opt_in_runner": False,
        "reasons": [
            "Prontidao PostgreSQL indisponivel porque o backend atual nao e SQLite local.",
        ],
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_network_rehearsal_checklist(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth | None,
) -> str:
    status = "pronto" if readiness.network_ready and readiness.postgres_ready else "bloqueado"
    health_lines = (
        _migration_health_lines(health)
        if health is not None
        else ["- Preflight SQLite nao disponivel para o backend atual."]
    )
    return "\n".join(
        [
            "# Checklist de homologacao de rede",
            "",
            "## Escopo",
            "",
            "- Preparar decisao tecnica para multiplas instalacoes.",
            "- Nao habilita uso em rede por si so.",
            "- Nao abre conexao externa e nao executa migracao.",
            "- Nao incluir chaves, tokens, senhas ou segredos neste pacote.",
            "",
            "## Origem",
            "",
            f"- Ambiente: {settings.app_env}",
            f"- Backend atual: {readiness.database_backend}",
            f"- Local mascarado: {readiness.database_location}",
            f"- Status de rede: {status}",
            "",
            "## Preflight local",
            "",
            *health_lines,
            "",
            "## Gates antes de multiplas instalacoes",
            "",
            "- [ ] Restaurar backup criptografado em copia descartavel.",
            "- [ ] Confirmar que SQLite nao sera compartilhado para escrita simultanea.",
            "- [ ] Executar pacote de homologacao PostgreSQL em ambiente descartavel.",
            "- [ ] Rodar testes automatizados completos no backend homologado.",
            "- [ ] Simular usuarios simultaneos em lancamento, baixa e conciliacao.",
            "- [ ] Validar auditoria, backup, restauracao e rollback operacional.",
            "- [ ] Registrar decisao operacional antes de trocar qualquer instalacao real.",
            "",
        ]
    )


def assess_postgres_schema_compatibility(
    *,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> SchemaCompatibilityReport:
    findings = (
        [
            SchemaCompatibilityFinding(
                severity="error",
                location="schema_version",
                message="Schema local nao esta na versao esperada.",
            )
        ]
        if health.schema_version != health.expected_schema_version
        else []
    )
    if not health.quick_check_ok:
        findings.append(
            SchemaCompatibilityFinding(
                severity="error",
                location="sqlite",
                message="PRAGMA quick_check precisa retornar OK antes de qualquer migracao.",
            )
        )
    if health.foreign_key_violations:
        findings.append(
            SchemaCompatibilityFinding(
                severity="error",
                location="foreign_keys",
                message="Existem violacoes de chave estrangeira na base local.",
            )
        )
    for table in inventory["tables"]:
        table_name = str(table["name"])
        columns = list(table["columns"])
        if not columns:
            findings.append(
                SchemaCompatibilityFinding(
                    severity="error",
                    location=table_name,
                    message="Tabela sem colunas no inventario.",
                )
            )
        for column in columns:
            column_name = str(column["name"])
            column_type = str(column["type"]).upper()
            location = f"{table_name}.{column_name}"
            if not column_type:
                findings.append(
                    SchemaCompatibilityFinding(
                        severity="warning",
                        location=location,
                        message="Coluna sem tipo explicito; mapear manualmente no PostgreSQL.",
                    )
                )
            if column_name.endswith("_cents") and column_type != "INTEGER":
                findings.append(
                    SchemaCompatibilityFinding(
                        severity="error",
                        location=location,
                        message="Valor monetario em centavos precisa permanecer INTEGER.",
                    )
                )
            if column["primary_key_position"] and column_type != "INTEGER":
                findings.append(
                    SchemaCompatibilityFinding(
                        severity="warning",
                        location=location,
                        message="Chave primaria nao INTEGER exige sequencia/identity explicita.",
                    )
                )
    return SchemaCompatibilityReport(
        ready_for_rehearsal=not any(finding.severity == "error" for finding in findings),
        findings=findings,
    )


def build_postgres_load_plan(
    *,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> PostgresLoadPlan:
    table_names = [str(table["name"]) for table in inventory["tables"]]
    remaining = {
        table_name: _table_dependencies(table, table_names)
        for table_name, table in zip(table_names, inventory["tables"], strict=True)
    }
    steps: list[PostgresLoadPlanStep] = []
    while remaining:
        ready_tables = [
            table_name
            for table_name, dependencies in remaining.items()
            if not [dependency for dependency in dependencies if dependency in remaining]
        ]
        if not ready_tables:
            break
        for table_name in sorted(ready_tables):
            dependencies = remaining.pop(table_name)
            steps.append(
                PostgresLoadPlanStep(
                    table_name=table_name,
                    dependencies=dependencies,
                    critical_row_count=health.critical_table_counts.get(table_name),
                )
            )
    unresolved_tables = sorted(remaining)
    return PostgresLoadPlan(
        ready_for_load_rehearsal=health.ready_for_migration_rehearsal and not unresolved_tables,
        steps=steps,
        unresolved_tables=unresolved_tables,
    )


def build_postgres_load_plan_json(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> str:
    load_plan = build_postgres_load_plan(health=health, inventory=inventory)
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "schema_version": health.schema_version,
        "expected_schema_version": health.expected_schema_version,
        "ready_for_load_rehearsal": load_plan.ready_for_load_rehearsal,
        "steps": [
            {
                "order": index,
                "table": step.table_name,
                "depends_on": step.dependencies,
                "critical_row_count": step.critical_row_count,
            }
            for index, step in enumerate(load_plan.steps, start=1)
        ],
        "unresolved_tables": load_plan.unresolved_tables,
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_postgres_adapter_contract_json(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> str:
    load_plan = build_postgres_load_plan(health=health, inventory=inventory)
    tables_by_name = {str(table["name"]): table for table in inventory["tables"]}
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "schema_version": health.schema_version,
        "expected_schema_version": health.expected_schema_version,
        "ready_for_adapter_rehearsal": load_plan.ready_for_load_rehearsal,
        "tables": [
            _postgres_adapter_table_contract(
                table=tables_by_name[step.table_name],
                load_order=index,
                source_count=step.critical_row_count,
            )
            for index, step in enumerate(load_plan.steps, start=1)
        ],
        "unresolved_tables": load_plan.unresolved_tables,
        "post_load_checks": [
            {
                "table": table_name,
                "source_count": count,
                "target_check": {
                    "operation": "count_rows",
                    "table": table_name,
                },
            }
            for table_name, count in health.critical_table_counts.items()
        ],
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_postgres_rehearsal_execution_plan_json(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> str:
    contract = json.loads(
        build_postgres_adapter_contract_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "schema_version": health.schema_version,
        "expected_schema_version": health.expected_schema_version,
        "ready_for_execution_rehearsal": contract["ready_for_adapter_rehearsal"],
        "phases": [
            {
                "name": "preflight",
                "operations": [
                    {"operation": "verify_sqlite_health", "required": True},
                    {"operation": "verify_empty_postgres_target", "required": True},
                    {"operation": "create_verified_backup", "required": True},
                ],
            },
            {
                "name": "schema",
                "operations": [
                    {
                        "operation": "apply_reviewed_blueprint",
                        "source_file": "blueprint-postgresql.sql",
                        "requires_manual_review": True,
                    }
                ],
            },
            {
                "name": "load",
                "operations": [
                    _postgres_rehearsal_insert_operation(table) for table in contract["tables"]
                ],
            },
            {
                "name": "identity",
                "operations": [
                    _postgres_rehearsal_identity_operation(table)
                    for table in contract["tables"]
                    if table["insert_strategy"] == "preserve_primary_keys_then_reset_identity"
                ],
            },
            {
                "name": "validation",
                "operations": [
                    {
                        "operation": "compare_row_count",
                        "table": check["table"],
                        "source_count": check["source_count"],
                    }
                    for check in contract["post_load_checks"]
                ],
            },
        ],
        "unresolved_tables": contract["unresolved_tables"],
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_postgres_rehearsal_preflight(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
    target_database_url: str | None = None,
) -> PostgresRehearsalPreflight:
    contract = json.loads(
        build_postgres_adapter_contract_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )
    execution_plan = json.loads(
        build_postgres_rehearsal_execution_plan_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )
    target_ready = bool(target_database_url and target_database_url.strip())
    checks = [
        PostgresRehearsalPreflightCheck(
            status="ok" if health.ready_for_migration_rehearsal else "blocked",
            code="sqlite_health",
            message=(
                "Base SQLite local esta integra para ensaio offline."
                if health.ready_for_migration_rehearsal
                else "Saneie schema, quick_check, chaves estrangeiras e WAL antes do ensaio."
            ),
        ),
        PostgresRehearsalPreflightCheck(
            status="ok" if readiness.database_backend == "sqlite" else "blocked",
            code="operational_backend_guard",
            message=(
                "Backend operacional permanece em SQLite durante o preflight."
                if readiness.database_backend == "sqlite"
                else "Volte DATABASE_URL para SQLite antes de preparar a homologacao."
            ),
        ),
        PostgresRehearsalPreflightCheck(
            status="ok",
            code="external_connection_guard",
            message="Este preflight nao abre conexao externa e nao toca no banco alvo.",
        ),
        PostgresRehearsalPreflightCheck(
            status="ok"
            if not execution_plan["opens_external_connection"]
            and not execution_plan["executes_migration"]
            else "blocked",
            code="execution_plan_guard",
            message="Plano estruturado permanece offline, parametrizado e sem execucao real.",
        ),
        PostgresRehearsalPreflightCheck(
            status="ok" if contract["ready_for_adapter_rehearsal"] else "blocked",
            code="adapter_contract_guard",
            message=(
                "Contrato do adapter nao possui tabelas sem ordem de carga."
                if contract["ready_for_adapter_rehearsal"]
                else "Resolva tabelas sem ordem de carga antes do ensaio."
            ),
        ),
        PostgresRehearsalPreflightCheck(
            status="ok" if target_ready else "warning",
            code="target_database_guard",
            message=(
                "URL alvo foi informada e sera exibida apenas mascarada."
                if target_ready
                else "Configure o alvo de homologacao apenas em .env local antes do runner real."
            ),
        ),
        PostgresRehearsalPreflightCheck(
            status="warning",
            code="package_review_guard",
            message="Revise manifesto, hashes e blueprint antes de implementar o runner real.",
        ),
    ]
    return PostgresRehearsalPreflight(
        ready_to_run=not any(check.status == "blocked" for check in checks),
        checks=checks,
    )


def build_postgres_rehearsal_preflight_json(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
    target_database_url: str | None = None,
) -> str:
    preflight = build_postgres_rehearsal_preflight(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
        target_database_url=target_database_url,
    )
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "target_database_configured": bool(target_database_url and target_database_url.strip()),
        "target_database_location": (
            _mask_database_url(target_database_url.strip())
            if target_database_url and target_database_url.strip()
            else None
        ),
        "schema_version": health.schema_version,
        "expected_schema_version": health.expected_schema_version,
        "ready_to_run": preflight.ready_to_run,
        "runner_mode": "offline_preflight_only",
        "checks": [
            {
                "status": check.status,
                "code": check.code,
                "message": check.message,
            }
            for check in preflight.checks
        ],
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def get_postgres_rehearsal_execution_readiness(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> PostgresRehearsalExecutionReadiness:
    target_database_url = settings.postgres_rehearsal_database_url
    driver_available = _postgres_driver_available()
    preflight = build_postgres_rehearsal_preflight(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
        target_database_url=target_database_url,
    )
    reasons = [check.message for check in preflight.checks if check.status == "blocked"]
    if not settings.postgres_rehearsal_enable_execution:
        reasons.append("POSTGRES_REHEARSAL_ENABLE_EXECUTION precisa estar true no .env local")
    if not target_database_url or not target_database_url.strip():
        reasons.append("POSTGRES_REHEARSAL_DATABASE_URL precisa estar configurada no .env local")
    elif not target_database_url.startswith(
        ("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")
    ):
        reasons.append("POSTGRES_REHEARSAL_DATABASE_URL precisa usar PostgreSQL")
    elif not driver_available:
        reasons.append("Driver PostgreSQL psycopg/psycopg2 nao esta instalado no ambiente")
    if settings.app_env.lower() == "production":
        reasons.append("Runner de homologacao nao executa com APP_ENV=production")
    return PostgresRehearsalExecutionReadiness(
        ready=not reasons,
        reasons=reasons,
        target_database_location=(
            _mask_database_url(target_database_url.strip())
            if target_database_url and target_database_url.strip()
            else None
        ),
        driver_available=driver_available,
    )


def build_postgres_rehearsal_runner_readiness_json(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> str:
    execution_readiness = get_postgres_rehearsal_execution_readiness(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "target_database_location": execution_readiness.target_database_location,
        "postgresql_driver_available": execution_readiness.driver_available,
        "execution_enabled": settings.postgres_rehearsal_enable_execution,
        "ready_for_opt_in_runner": execution_readiness.ready,
        "reasons": execution_readiness.reasons,
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def _postgres_driver_available() -> bool:
    return (
        importlib.util.find_spec("psycopg") is not None
        or importlib.util.find_spec("psycopg2") is not None
    )


def execute_postgres_rehearsal(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
    transport: PostgresRehearsalTransport,
) -> PostgresRehearsalExecutionResult:
    execution_readiness = get_postgres_rehearsal_execution_readiness(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )
    if not execution_readiness.ready:
        raise ValueError("; ".join(execution_readiness.reasons))
    if not settings.postgres_rehearsal_database_url:
        raise ValueError("POSTGRES_REHEARSAL_DATABASE_URL precisa estar configurada")

    response = transport(
        target_database_url=settings.postgres_rehearsal_database_url,
        execution_plan=json.loads(
            build_postgres_rehearsal_execution_plan_json(
                settings=settings,
                readiness=readiness,
                health=health,
                inventory=inventory,
            )
        ),
        timeout_seconds=60,
    )
    status = response.get("status")
    executed_steps = response.get("executed_steps")
    return PostgresRehearsalExecutionResult(
        status=status if isinstance(status, str) else "unknown",
        target_database_location=execution_readiness.target_database_location or "",
        executed_steps=executed_steps if isinstance(executed_steps, int) else None,
    )


def build_postgres_compatibility_report(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> str:
    report = assess_postgres_schema_compatibility(health=health, inventory=inventory)
    finding_lines = [
        f"- [{finding.severity.upper()}] {finding.location}: {finding.message}"
        for finding in report.findings
    ] or ["- Nenhum achado bloqueante ou aviso tecnico identificado."]
    return "\n".join(
        [
            "# Relatorio de compatibilidade PostgreSQL",
            "",
            "## Escopo",
            "",
            "- Analise local baseada apenas em metadados do schema SQLite.",
            "- Nao contem linhas financeiras, usuarios, auditoria ou documentos.",
            "- Nao realiza conexao externa nem executa migracao.",
            "",
            "## Origem",
            "",
            f"- Ambiente: {settings.app_env}",
            f"- Backend atual: {readiness.database_backend}",
            f"- Local mascarado: {readiness.database_location}",
            f"- Schema: {health.schema_version}/{health.expected_schema_version}",
            f"- Pronto para ensaio: {'sim' if report.ready_for_rehearsal else 'nao'}",
            "",
            "## Achados",
            "",
            *finding_lines,
            "",
        ]
    )


def build_postgres_schema_blueprint(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> str:
    compatibility = assess_postgres_schema_compatibility(
        health=health,
        inventory=inventory,
    )
    table_blocks = [_postgres_table_blueprint(table) for table in inventory["tables"]]
    index_blocks = [
        _postgres_index_blueprint(table) for table in inventory["tables"] if table["indexes"]
    ]
    return "\n".join(
        [
            "-- Blueprint PostgreSQL gerado localmente para revisao tecnica.",
            "-- Nao contem dados financeiros, usuarios, auditoria ou documentos.",
            "-- Nao executar sem revisao, adapter implementado, backup e ensaio validado.",
            f"-- Ambiente: {settings.app_env}",
            f"-- Backend atual: {readiness.database_backend}",
            f"-- Origem mascarada: {readiness.database_location}",
            f"-- Schema: {health.schema_version}/{health.expected_schema_version}",
            f"-- Compatibilidade: {'pronto' if compatibility.ready_for_rehearsal else 'revisar'}",
            "",
            "BEGIN;",
            "",
            *table_blocks,
            *index_blocks,
            "COMMIT;",
            "",
        ]
    )


def build_postgres_rehearsal_package_files(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> dict[str, str]:
    files = {
        "README.md": _postgres_rehearsal_package_readme(),
        "roteiro-migracao-postgresql.md": build_migration_rehearsal_plan(
            settings=settings,
            readiness=readiness,
            health=health,
        ),
        "inventario-schema-sqlite.json": build_schema_inventory_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        ),
        "compatibilidade-postgresql.md": build_postgres_compatibility_report(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        ),
        "plano-carga-postgresql.json": build_postgres_load_plan_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        ),
        "contrato-adapter-postgresql.json": build_postgres_adapter_contract_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        ),
        "plano-execucao-homologacao-postgresql.json": (
            build_postgres_rehearsal_execution_plan_json(
                settings=settings,
                readiness=readiness,
                health=health,
                inventory=inventory,
            )
        ),
        "preflight-runner-homologacao-postgresql.json": (
            build_postgres_rehearsal_preflight_json(
                settings=settings,
                readiness=readiness,
                health=health,
                inventory=inventory,
            )
        ),
        "prontidao-runner-homologacao-postgresql.json": (
            build_postgres_rehearsal_runner_readiness_json(
                settings=settings,
                readiness=readiness,
                health=health,
                inventory=inventory,
            )
        ),
        "blueprint-postgresql.sql": build_postgres_schema_blueprint(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        ),
    }
    return {
        **files,
        "manifesto-homologacao.json": _postgres_rehearsal_manifest(
            settings=settings,
            readiness=readiness,
            health=health,
            files=files,
        ),
    }


def write_postgres_rehearsal_package(
    *,
    output_path: Path,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> None:
    files = build_postgres_rehearsal_package_files(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name, content in files.items():
            archive.writestr(file_name, content)


def build_schema_inventory_json(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
) -> str:
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "schema_version": health.schema_version,
        "expected_schema_version": health.expected_schema_version,
        "quick_check_ok": health.quick_check_ok,
        "foreign_key_violations": health.foreign_key_violations,
        "journal_mode": health.journal_mode,
        "wal_enabled": health.wal_enabled,
        "critical_table_counts": health.critical_table_counts,
        "tables": inventory["tables"],
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def build_migration_rehearsal_plan(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth | None,
) -> str:
    status = (
        "pronto para ensaio local"
        if health is not None and health.ready_for_migration_rehearsal
        else "pendente de saneamento"
    )
    health_lines = (
        _migration_health_lines(health)
        if health is not None
        else ["- Preflight SQLite nao disponivel para o backend atual."]
    )
    count_lines = (
        [f"- {table_name}: {count}" for table_name, count in health.critical_table_counts.items()]
        if health is not None
        else ["- Nao aplicavel."]
    )
    warning_lines = [f"- {warning}" for warning in readiness.warnings] or ["- Nenhum aviso."]
    next_step_lines = [f"- {step}" for step in readiness.next_steps] or ["- Nenhum passo pendente."]
    return "\n".join(
        [
            "# Roteiro de ensaio de migracao",
            "",
            "## Escopo",
            "",
            "- Ensaio local e controlado para preparar migracao futura.",
            "- Nao executar contra producao.",
            "- Nao incluir chaves, tokens, senhas ou segredos no roteiro.",
            "- Manter `DATABASE_URL` operacional em SQLite ate adapter e homologacao.",
            "",
            "## Origem",
            "",
            f"- Ambiente: {settings.app_env}",
            f"- Backend atual: {readiness.database_backend}",
            f"- Local mascarado: {readiness.database_location}",
            f"- Status do preflight: {status}",
            "",
            "## Preflight local",
            "",
            *health_lines,
            "",
            "## Tabelas criticas",
            "",
            *count_lines,
            "",
            "## Avisos",
            "",
            *warning_lines,
            "",
            "## Passos de ensaio",
            "",
            "1. Criar backup criptografado e validar restauracao em copia descartavel.",
            "2. Copiar a base SQLite para ambiente de homologacao sem alterar a producao.",
            "3. Criar banco PostgreSQL vazio em ambiente isolado, com credenciais no `.env` local.",
            "4. Executar adapter de migracao quando estiver implementado.",
            "5. Comparar contagens das tabelas criticas antes e depois.",
            "6. Rodar testes automatizados, auditoria e fluxo de backup/restauracao.",
            "7. Registrar resultado do ensaio antes de qualquer decisao operacional.",
            "",
            "## Proximos passos registrados",
            "",
            *next_step_lines,
            "",
        ]
    )


def get_local_schema_inventory(connection: sqlite3.Connection) -> dict[str, Any]:
    table_rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return {
        "tables": [
            {
                "name": str(row["name"]),
                "columns": _table_columns(connection, str(row["name"])),
                "foreign_keys": _table_foreign_keys(connection, str(row["name"])),
                "indexes": _table_indexes(connection, str(row["name"])),
            }
            for row in table_rows
        ]
    }


def get_deployment_readiness(settings: Settings) -> DeploymentReadiness:
    database_url = settings.database_url.strip()
    if database_url.startswith("sqlite:///"):
        return _sqlite_readiness(settings, database_url)
    if database_url.startswith(
        ("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")
    ):
        return _postgres_readiness(database_url)
    return DeploymentReadiness(
        database_backend="desconhecido",
        database_location=_mask_database_url(database_url),
        offline_ready=False,
        network_ready=False,
        postgres_ready=False,
        warnings=["DATABASE_URL usa um backend nao suportado pela aplicacao atual"],
        next_steps=[
            "Voltar para sqlite:/// no .env local ou planejar adapter oficial antes da migracao"
        ],
    )


def get_local_database_health(connection: sqlite3.Connection) -> LocalDatabaseHealth:
    schema_row = connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    quick_check_row = connection.execute("PRAGMA quick_check").fetchone()
    foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
    journal_mode_row = connection.execute("PRAGMA journal_mode").fetchone()
    counts = {
        table_name: int(connection.execute(query).fetchone()[0])
        for table_name, query in _CRITICAL_TABLE_COUNT_QUERIES.items()
    }
    journal_mode = str(journal_mode_row[0]).lower() if journal_mode_row else "desconhecido"
    return LocalDatabaseHealth(
        schema_version=None if schema_row is None else int(schema_row["version"]),
        expected_schema_version=SCHEMA_VERSION,
        quick_check_ok=quick_check_row is not None and str(quick_check_row[0]).lower() == "ok",
        foreign_key_violations=len(foreign_key_rows),
        journal_mode=journal_mode,
        wal_enabled=journal_mode == "wal",
        critical_table_counts=counts,
    )


def _sqlite_readiness(settings: Settings, database_url: str) -> DeploymentReadiness:
    database_path = settings.paths.resolve_app_path(database_url.removeprefix("sqlite:///"))
    warnings = [
        "SQLite local nao deve ser usado por varios computadores escrevendo ao mesmo tempo",
        "Migracao para rede/PostgreSQL ainda exige adapter, migracao testada e backup validado",
    ]
    return DeploymentReadiness(
        database_backend="sqlite",
        database_location=str(database_path),
        offline_ready=True,
        network_ready=False,
        postgres_ready=False,
        warnings=warnings,
        next_steps=[
            "Validar rotina de backup antes de qualquer compartilhamento em rede",
            "Definir computador servidor ou instancia PostgreSQL em ambiente separado",
            "Criar migracao ensaiada em copia descartavel antes de trocar DATABASE_URL",
        ],
    )


def _postgres_readiness(database_url: str) -> DeploymentReadiness:
    return DeploymentReadiness(
        database_backend="postgresql",
        database_location=_mask_database_url(database_url),
        offline_ready=False,
        network_ready=True,
        postgres_ready=False,
        warnings=[
            "PostgreSQL ainda esta em preparacao: os repositorios atuais usam sqlite3 direto",
            "Nao usar este DATABASE_URL em producao ate a camada de persistencia ser migrada",
        ],
        next_steps=[
            "Criar adapter SQLAlchemy/PostgreSQL sem alterar regras de negocio",
            "Executar migracao em base de homologacao com backup verificado",
            "Rodar testes de concorrencia, auditoria e backup antes de uso real",
        ],
    )


def _mask_database_url(database_url: str) -> str:
    if "@" not in database_url or "://" not in database_url:
        return database_url
    scheme, rest = database_url.split("://", 1)
    credentials, host = rest.split("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def _migration_health_lines(health: LocalDatabaseHealth) -> list[str]:
    return [
        f"- Schema: {health.schema_version}/{health.expected_schema_version}",
        f"- Integridade SQLite: {'OK' if health.quick_check_ok else 'revisar'}",
        f"- Violacoes de chave estrangeira: {health.foreign_key_violations}",
        f"- Jornal SQLite: {health.journal_mode}",
        f"- WAL habilitado: {'sim' if health.wal_enabled else 'nao'}",
    ]


def _table_columns(connection: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT cid, name, type, "notnull", dflt_value, pk
        FROM pragma_table_info(?)
        ORDER BY cid
        """,
        (table_name,),
    ).fetchall()
    return [
        {
            "name": str(row["name"]),
            "type": str(row["type"]),
            "not_null": bool(row["notnull"]),
            "default": None if row["dflt_value"] is None else str(row["dflt_value"]),
            "primary_key_position": int(row["pk"]),
        }
        for row in rows
    ]


def _table_foreign_keys(connection: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, seq, "table", "from", "to", on_update, on_delete
        FROM pragma_foreign_key_list(?)
        ORDER BY id, seq
        """,
        (table_name,),
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "seq": int(row["seq"]),
            "table": str(row["table"]),
            "from": str(row["from"]),
            "to": str(row["to"]),
            "on_update": str(row["on_update"]),
            "on_delete": str(row["on_delete"]),
        }
        for row in rows
    ]


def _table_indexes(connection: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT name, "unique", origin, partial
        FROM pragma_index_list(?)
        ORDER BY name
        """,
        (table_name,),
    ).fetchall()
    return [
        {
            "name": str(row["name"]),
            "unique": bool(row["unique"]),
            "origin": str(row["origin"]),
            "partial": bool(row["partial"]),
            "columns": _index_columns(connection, str(row["name"])),
        }
        for row in rows
    ]


def _index_columns(connection: sqlite3.Connection, index_name: str) -> list[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM pragma_index_info(?)
        ORDER BY seqno
        """,
        (index_name,),
    ).fetchall()
    return [str(row["name"]) for row in rows]


def _table_dependencies(table: dict[str, Any], table_names: list[str]) -> list[str]:
    known_tables = set(table_names)
    return sorted(
        {
            str(foreign_key["table"])
            for foreign_key in table["foreign_keys"]
            if str(foreign_key["table"]) in known_tables
            and str(foreign_key["table"]) != str(table["name"])
        }
    )


def _postgres_table_blueprint(table: dict[str, Any]) -> str:
    table_name = str(table["name"])
    columns = list(table["columns"])
    primary_key_columns = [
        str(column["name"])
        for column in sorted(columns, key=lambda item: int(item["primary_key_position"]))
        if column["primary_key_position"]
    ]
    column_lines = [
        f"    {_quote_identifier(str(column['name']))} {_postgres_column_type(column)}"
        f"{' NOT NULL' if column['not_null'] else ''}"
        for column in columns
    ]
    constraints = (
        [f"    PRIMARY KEY ({_identifier_list(primary_key_columns)})"]
        if primary_key_columns
        else []
    ) + [
        (
            f"    FOREIGN KEY ({_quote_identifier(str(foreign_key['from']))}) "
            f"REFERENCES {_quote_identifier(str(foreign_key['table']))}"
            f"({_quote_identifier(str(foreign_key['to']))})"
        )
        for foreign_key in table["foreign_keys"]
    ]
    return "\n".join(
        [
            f"CREATE TABLE IF NOT EXISTS {_quote_identifier(table_name)} (",
            ",\n".join([*column_lines, *constraints]),
            ");",
            "",
        ]
    )


def _postgres_index_blueprint(table: dict[str, Any]) -> str:
    table_name = str(table["name"])
    statements = []
    for index in table["indexes"]:
        columns = list(index["columns"])
        if not columns or index["origin"] == "pk":
            continue
        unique = "UNIQUE " if index["unique"] else ""
        statements.append(
            f"CREATE {unique}INDEX IF NOT EXISTS {_quote_identifier(str(index['name']))} "
            f"ON {_quote_identifier(table_name)} ({_identifier_list(columns)});"
        )
    return "\n".join([*statements, ""]) if statements else ""


def _postgres_adapter_table_contract(
    *,
    table: dict[str, Any],
    load_order: int,
    source_count: int | None,
) -> dict[str, Any]:
    primary_key_columns = [
        column for column in table["columns"] if int(column["primary_key_position"])
    ]
    return {
        "load_order": load_order,
        "table": str(table["name"]),
        "insert_strategy": _postgres_insert_strategy(primary_key_columns),
        "source_count": source_count,
        "columns": [
            {
                "name": str(column["name"]),
                "sqlite_type": str(column["type"]),
                "postgres_type": _postgres_column_type(column),
                "nullable": not bool(column["not_null"]),
                "default": column["default"],
                "primary_key_position": int(column["primary_key_position"]),
            }
            for column in table["columns"]
        ],
        "foreign_keys": [
            {
                "from": str(foreign_key["from"]),
                "to_table": str(foreign_key["table"]),
                "to_column": str(foreign_key["to"]),
            }
            for foreign_key in table["foreign_keys"]
        ],
        "indexes": [
            {
                "name": str(index["name"]),
                "unique": bool(index["unique"]),
                "columns": list(index["columns"]),
            }
            for index in table["indexes"]
            if index["origin"] != "pk"
        ],
    }


def _postgres_insert_strategy(primary_key_columns: list[dict[str, Any]]) -> str:
    if not primary_key_columns:
        return "insert_without_primary_key"
    if any(str(column["type"]).upper() == "INTEGER" for column in primary_key_columns):
        return "preserve_primary_keys_then_reset_identity"
    return "preserve_primary_keys"


def _postgres_rehearsal_insert_operation(table: dict[str, Any]) -> dict[str, Any]:
    column_names = [str(column["name"]) for column in table["columns"]]
    return {
        "operation": "insert_rows",
        "table": table["table"],
        "load_order": table["load_order"],
        "strategy": table["insert_strategy"],
        "columns": column_names,
        "parameters": [f":{column_name}" for column_name in column_names],
        "source_count": table["source_count"],
        "uses_parameter_binding": True,
    }


def _postgres_rehearsal_identity_operation(table: dict[str, Any]) -> dict[str, Any]:
    primary_keys = [
        column["name"] for column in table["columns"] if int(column["primary_key_position"])
    ]
    return {
        "operation": "reset_identity_sequence",
        "table": table["table"],
        "primary_keys": primary_keys,
        "requires_empty_target_before_load": True,
    }


def _postgres_column_type(column: dict[str, Any]) -> str:
    column_name = str(column["name"])
    column_type = str(column["type"]).upper()
    if column["primary_key_position"] and column_type == "INTEGER":
        return "BIGINT GENERATED BY DEFAULT AS IDENTITY"
    if column_name.endswith("_cents"):
        return "BIGINT"
    if column_type in {"INTEGER", "INT"}:
        return "BIGINT"
    if column_type in {"REAL", "FLOAT", "DOUBLE"}:
        return "NUMERIC"
    if column_type in {"BLOB"}:
        return "BYTEA"
    if column_type in {"TEXT", "VARCHAR", "CHAR", "STRING"} or not column_type:
        return "TEXT"
    if column_type in {"BOOLEAN", "BOOL"}:
        return "BOOLEAN"
    return "TEXT"


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def _identifier_list(identifiers: list[str]) -> str:
    return ", ".join(_quote_identifier(identifier) for identifier in identifiers)


def _postgres_rehearsal_package_readme() -> str:
    return "\n".join(
        [
            "# Pacote local de homologacao PostgreSQL",
            "",
            "Este pacote foi gerado localmente a partir de metadados SQLite.",
            "",
            "## Seguranca",
            "",
            "- Nao contem linhas financeiras, usuarios, auditoria ou documentos.",
            "- Nao contem chaves, tokens, senhas ou credenciais.",
            "- Nao executa migracao e nao abre conexao externa.",
            "- O SQL deve ser revisado antes de qualquer uso em homologacao.",
            "",
            "## Arquivos",
            "",
            "- `roteiro-migracao-postgresql.md`: passos seguros de ensaio.",
            "- `inventario-schema-sqlite.json`: inventario tecnico do schema local.",
            "- `compatibilidade-postgresql.md`: achados de compatibilidade.",
            "- `plano-carga-postgresql.json`: ordem tecnica de carga por dependencias.",
            "- `contrato-adapter-postgresql.json`: contrato tecnico do adapter futuro.",
            "- `plano-execucao-homologacao-postgresql.json`: roteiro estruturado de execucao.",
            "- `preflight-runner-homologacao-postgresql.json`: validacao offline do runner futuro.",
            "- `prontidao-runner-homologacao-postgresql.json`: guardas para execucao opt-in.",
            "- `blueprint-postgresql.sql`: DDL preliminar para revisao.",
            "- `manifesto-homologacao.json`: hashes SHA-256 e metadados do pacote.",
            "",
        ]
    )


def _phase8_local_evidence_package_readme() -> str:
    return "\n".join(
        [
            "# Pacote local de evidencias da Fase 8",
            "",
            "Este pacote consolida apenas evidencias locais da Fase 8.",
            "",
            "## Seguranca",
            "",
            "- Nao contem linhas financeiras, usuarios, auditoria ou documentos.",
            "- Nao contem chaves, tokens, senhas ou credenciais.",
            "- Nao chama API, nao abre PostgreSQL e nao executa migracao.",
            "- Nao declara a Fase 8 concluida sem homologacoes externas reais.",
            "",
            "## Arquivos",
            "",
            "- `aceite-local-fase-8.md`: resumo local e pendencias externas.",
            "- `prontidao-uso-em-rede.json`: gates locais de rede.",
            "- `prontidao-runner-homologacao-postgresql.json`: gates do runner.",
            "- `manifesto-evidencias-fase-8.json`: hashes SHA-256 e metadados.",
            "",
        ]
    )


def _network_rehearsal_package_readme() -> str:
    return "\n".join(
        [
            "# Pacote local de homologacao de rede",
            "",
            "Este pacote foi gerado localmente para revisar uso futuro em rede.",
            "",
            "## Seguranca",
            "",
            "- Nao contem linhas financeiras, usuarios, auditoria ou documentos.",
            "- Nao contem chaves, tokens, senhas ou credenciais.",
            "- Nao abre conexao externa e nao executa migracao.",
            "- Nao autoriza compartilhar SQLite para escrita simultanea.",
            "",
            "## Arquivos",
            "",
            "- `prontidao-uso-em-rede.json`: gates locais de prontidao.",
            "- `checklist-homologacao-rede.md`: revisao manual antes de rede.",
            "- `manifesto-homologacao-rede.json`: hashes SHA-256 e metadados.",
            "",
        ]
    )


def _phase8_local_evidence_manifest(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth | None,
    files: dict[str, str],
) -> str:
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "phase_complete": False,
        "requires_external_asaas_sandbox_validation": True,
        "requires_external_postgres_rehearsal": True,
        "contains_disallowed_markers": _package_contains_disallowed_markers(
            "\n".join(files.values()),
        ),
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "schema_version": None if health is None else health.schema_version,
        "expected_schema_version": None if health is None else health.expected_schema_version,
        "files": {
            name: {
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "bytes": len(content.encode("utf-8")),
            }
            for name, content in sorted(files.items())
        },
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def _network_rehearsal_manifest(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth | None,
    files: dict[str, str],
) -> str:
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "ready_for_network_use": (
            readiness.network_ready
            and readiness.postgres_ready
            and bool(settings.backup_encryption_key)
        ),
        "schema_version": None if health is None else health.schema_version,
        "expected_schema_version": None if health is None else health.expected_schema_version,
        "files": {
            name: {
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
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
        and expected_hash == hashlib.sha256(encoded).hexdigest()
        and isinstance(expected_bytes, int)
        and expected_bytes == len(encoded)
    )


def _network_manifest_safe_flags_valid(manifest: dict[str, Any]) -> bool:
    expected_flags = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
    }
    return all(manifest.get(key) is expected for key, expected in expected_flags.items())


def _package_contains_disallowed_markers(content: str) -> bool:
    markers = [
        "ASAAS_API_KEY=",
        "APP_SECRET_KEY=",
        "BACKUP_ENCRYPTION_KEY=",
        "access_token",
        "invoiceUrl",
        "valor_local",
        "sk-",
        "AIza",
        "xoxb-",
        "xoxa-",
        "xoxp-",
        "xoxr-",
        "xoxs-",
    ]
    return any(marker in content for marker in markers)


def _json_verification_gate(
    *,
    label: str,
    path: Path | None,
) -> dict[str, Any]:
    base = _evidence_gate_base(label=label, path=path)
    if path is None or not path.exists():
        return base

    content = path.read_text(encoding="utf-8")
    if _package_contains_disallowed_markers(content):
        return {
            **base,
            "present": True,
            "contains_disallowed_markers": True,
            "message": f"{label}: arquivo contem marcadores sensiveis.",
        }

    payload = json.loads(content)
    checks = [
        payload.get("ready_for_review") is True,
        payload.get("safe_flags_valid") is True,
        payload.get("hashes_valid") is True,
        payload.get("contains_disallowed_markers") is False,
        payload.get("opens_external_connection") is False,
        payload.get("executes_migration") is False,
        payload.get("executes_write_operation", False) is False,
    ]
    passed = all(checks)
    return {
        **base,
        "present": True,
        "passed": passed,
        "ready_for_review": payload.get("ready_for_review"),
        "contains_disallowed_markers": False,
        "message": (
            f"{label}: verificacao pronta para fechamento."
            if passed
            else f"{label}: JSON de verificacao nao passou em todos os gates."
        ),
    }


def _markdown_evidence_gate(
    *,
    label: str,
    path: Path | None,
    required_fragment: str,
) -> dict[str, Any]:
    base = _evidence_gate_base(label=label, path=path)
    if path is None or not path.exists():
        return base

    content = path.read_text(encoding="utf-8")
    contains_disallowed_markers = _package_contains_disallowed_markers(content)
    required_fragment_present = required_fragment in content
    passed = required_fragment_present and not contains_disallowed_markers
    return {
        **base,
        "present": True,
        "passed": passed,
        "required_fragment_present": required_fragment_present,
        "contains_disallowed_markers": contains_disallowed_markers,
        "message": (
            f"{label}: resumo pronto para fechamento."
            if passed
            else f"{label}: resumo ausente, incompleto ou com marcador sensivel."
        ),
    }


def _postgres_rehearsal_report_gate(path: Path | None) -> dict[str, Any]:
    label = "Relatorio real de homologacao PostgreSQL"
    base = _evidence_gate_base(label=label, path=path)
    if path is None or not path.exists():
        return base

    content = path.read_text(encoding="utf-8")
    contains_disallowed_markers = _package_contains_disallowed_markers(content)
    title_present = "# Relatorio local de homologacao PostgreSQL" in content
    success_status_present = "- Status: succeeded" in content
    passed = title_present and success_status_present and not contains_disallowed_markers
    return {
        **base,
        "present": True,
        "passed": passed,
        "title_present": title_present,
        "success_status_present": success_status_present,
        "contains_disallowed_markers": contains_disallowed_markers,
        "message": (
            f"{label}: homologacao descartavel concluida."
            if passed
            else f"{label}: relatorio ausente, sem sucesso ou com marcador sensivel."
        ),
    }


def _evidence_gate_base(*, label: str, path: Path | None) -> dict[str, Any]:
    return {
        "label": label,
        "path": None if path is None else str(path),
        "present": False,
        "passed": False,
        "message": f"{label}: evidencia obrigatoria nao informada ou nao encontrada.",
    }


def _phase8_closeout_manifest(*, files: dict[str, str]) -> str:
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "executes_write_operation": False,
        "ready_to_close_phase8": (
            "Status: **Fase 8 pronta para encerramento operacional**"
            in files["encerramento-fase-8.md"]
        ),
        "contains_disallowed_markers": _package_contains_disallowed_markers(
            "\n".join(files.values()),
        ),
        "files": {
            name: {
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "bytes": len(content.encode("utf-8")),
            }
            for name, content in sorted(files.items())
        },
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


def _postgres_rehearsal_manifest(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    files: dict[str, str],
) -> str:
    payload = {
        "metadata_only": True,
        "contains_financial_rows": False,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "environment": settings.app_env,
        "database_backend": readiness.database_backend,
        "database_location": readiness.database_location,
        "schema_version": health.schema_version,
        "expected_schema_version": health.expected_schema_version,
        "ready_for_rehearsal": health.ready_for_migration_rehearsal,
        "files": {
            name: {
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "bytes": len(content.encode("utf-8")),
            }
            for name, content in sorted(files.items())
        },
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)


_CRITICAL_TABLE_COUNT_QUERIES = {
    "users": "SELECT COUNT(*) FROM users",
    "audit_log": "SELECT COUNT(*) FROM audit_log",
    "financial_accounts": "SELECT COUNT(*) FROM financial_accounts",
    "financial_transactions": "SELECT COUNT(*) FROM financial_transactions",
    "payable_receivable_entries": "SELECT COUNT(*) FROM payable_receivable_entries",
    "budgets": "SELECT COUNT(*) FROM budgets",
    "sensitive_operation_requests": "SELECT COUNT(*) FROM sensitive_operation_requests",
    "sensitive_operation_executions": "SELECT COUNT(*) FROM sensitive_operation_executions",
}
