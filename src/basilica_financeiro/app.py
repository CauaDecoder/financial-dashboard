from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from basilica_financeiro.config import Settings, load_settings
from basilica_financeiro.database import connect, migrate
from basilica_financeiro.logging_config import configure_logging
from basilica_financeiro.repositories.bootstrap import ensure_default_admin
from basilica_financeiro.services.asaas_write_executor import (
    build_asaas_execution_readiness_json,
    build_asaas_execution_report_json,
    build_asaas_sandbox_validation_package_verification_json,
    build_asaas_sandbox_validation_review_summary_markdown,
    execute_approved_asaas_operation,
    urllib_asaas_write_transport,
    write_asaas_sandbox_validation_package,
)
from basilica_financeiro.services.backup import ensure_daily_encrypted_backup
from basilica_financeiro.services.deployment import (
    build_network_readiness_json,
    build_network_rehearsal_package_verification_json,
    build_network_rehearsal_review_summary_markdown,
    build_phase8_closeout_report_markdown,
    build_phase8_closure_readiness_json,
    build_phase8_local_acceptance_report_markdown,
    build_phase8_local_evidence_package_verification_json,
    build_phase8_local_evidence_review_summary_markdown,
    build_postgres_rehearsal_package_verification_json,
    build_postgres_rehearsal_review_summary_markdown,
    build_postgres_rehearsal_runner_readiness_json,
    get_deployment_readiness,
    get_local_database_health,
    get_local_schema_inventory,
    write_network_rehearsal_package,
    write_phase8_closeout_package,
    write_phase8_local_evidence_package,
    write_postgres_rehearsal_package,
)
from basilica_financeiro.services.postgres_rehearsal import (
    run_postgres_rehearsal_admin_action,
)
from basilica_financeiro.ui.qt_app import run_qt_app


def main(argv: Sequence[str] | None = None) -> int:
    """Start the desktop application or an explicit administrative command."""
    args = list(sys.argv[1:] if argv is None else argv)
    settings = load_settings()
    configure_logging(settings)
    settings.paths.ensure_directories()

    if args:
        try:
            return _run_admin_command(args, settings)
        except ValueError as exc:
            print(f"Erro: {exc}", file=sys.stderr)  # noqa: T201
            return 1

    with connect(settings.database_path) as connection:
        migrate(connection)
        ensure_default_admin(connection, settings)
        ensure_daily_encrypted_backup(connection, settings=settings, actor_user_id=None)

    return run_qt_app(settings)


def _run_admin_command(args: list[str], settings: Settings) -> int:
    parser = argparse.ArgumentParser(
        prog="basilica-financeiro",
        description="Comandos administrativos locais do Basilica Financeiro.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    asaas_readiness_parser = subparsers.add_parser(
        "asaas-readiness",
        help="Exporta prontidao local de uma solicitacao Asaas sem chamar API.",
    )
    asaas_readiness_parser.add_argument(
        "--request-id",
        type=int,
        required=True,
        help="ID local da solicitacao sensivel a validar.",
    )
    asaas_readiness_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do JSON de prontidao sem segredos.",
    )
    asaas_execute_parser = subparsers.add_parser(
        "asaas-execute",
        help="Executa uma solicitacao Asaas aprovada apenas em Sandbox opt-in.",
    )
    asaas_execute_parser.add_argument(
        "--request-id",
        type=int,
        required=True,
        help="ID local da solicitacao sensivel aprovada.",
    )
    asaas_execute_parser.add_argument(
        "--confirm-sandbox",
        action="store_true",
        help="Confirma que a execucao deve ocorrer somente no Asaas Sandbox.",
    )
    asaas_execute_parser.add_argument(
        "--actor-user-id",
        type=int,
        help="ID local do usuario tecnico responsavel pelo disparo.",
    )
    asaas_execute_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do JSON resumido sem segredos.",
    )
    asaas_report_parser = subparsers.add_parser(
        "asaas-execution-report",
        help="Exporta evidencia local de execucao Asaas sem chamar API.",
    )
    asaas_report_parser.add_argument(
        "--request-id",
        type=int,
        required=True,
        help="ID local da solicitacao sensivel.",
    )
    asaas_report_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do JSON de evidencia sem segredos.",
    )
    asaas_package_parser = subparsers.add_parser(
        "asaas-validation-package",
        help="Exporta pacote ZIP local de homologacao Asaas sem chamar API.",
    )
    asaas_package_parser.add_argument(
        "--request-id",
        type=int,
        required=True,
        help="ID local da solicitacao sensivel.",
    )
    asaas_package_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do ZIP de homologacao sem segredos.",
    )
    asaas_verify_parser = subparsers.add_parser(
        "asaas-verify-package",
        help="Verifica manifesto e hashes de um pacote ZIP Asaas sem chamar API.",
    )
    asaas_verify_parser.add_argument(
        "--package",
        type=Path,
        required=True,
        help="Caminho local do pacote ZIP de homologacao Asaas.",
    )
    asaas_verify_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do JSON de verificacao sem segredos.",
    )
    asaas_summary_parser = subparsers.add_parser(
        "asaas-review-summary",
        help="Exporta resumo Markdown dos gates locais de homologacao Asaas.",
    )
    asaas_summary_parser.add_argument(
        "--package",
        type=Path,
        required=True,
        help="Caminho local do pacote ZIP de homologacao Asaas.",
    )
    asaas_summary_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do resumo Markdown sem segredos.",
    )
    phase8_report_parser = subparsers.add_parser(
        "phase8-acceptance-report",
        help="Exporta relatorio local de aceite da Fase 8 sem conexoes externas.",
    )
    phase8_report_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do Markdown de aceite local sem segredos.",
    )
    phase8_package_parser = subparsers.add_parser(
        "phase8-evidence-package",
        help="Exporta pacote ZIP local de evidencias da Fase 8 sem conexoes externas.",
    )
    phase8_package_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do ZIP de evidencias locais sem segredos.",
    )
    phase8_verify_parser = subparsers.add_parser(
        "phase8-verify-package",
        help="Verifica manifesto e hashes de um pacote ZIP de evidencias da Fase 8.",
    )
    phase8_verify_parser.add_argument(
        "--package",
        type=Path,
        required=True,
        help="Caminho local do pacote ZIP de evidencias da Fase 8.",
    )
    phase8_verify_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do JSON de verificacao sem segredos.",
    )
    phase8_summary_parser = subparsers.add_parser(
        "phase8-review-summary",
        help="Exporta resumo Markdown dos gates locais do pacote da Fase 8.",
    )
    phase8_summary_parser.add_argument(
        "--package",
        type=Path,
        required=True,
        help="Caminho local do pacote ZIP de evidencias da Fase 8.",
    )
    phase8_summary_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do resumo Markdown sem segredos.",
    )
    phase8_closure_parser = subparsers.add_parser(
        "phase8-closure-readiness",
        help="Consolida evidencias externas para checar fechamento seguro da Fase 8.",
    )
    phase8_closure_parser.add_argument(
        "--asaas-verification",
        type=Path,
        help="JSON de verificacao do pacote Asaas Sandbox.",
    )
    phase8_closure_parser.add_argument(
        "--asaas-summary",
        type=Path,
        help="Resumo Markdown de aceite do pacote Asaas Sandbox.",
    )
    phase8_closure_parser.add_argument(
        "--postgres-package-verification",
        type=Path,
        help="JSON de verificacao do pacote PostgreSQL.",
    )
    phase8_closure_parser.add_argument(
        "--postgres-report",
        type=Path,
        help="Relatorio Markdown da homologacao PostgreSQL descartavel.",
    )
    phase8_closure_parser.add_argument(
        "--phase8-package-verification",
        type=Path,
        help="JSON de verificacao do pacote local de evidencias da Fase 8.",
    )
    phase8_closure_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do JSON de prontidao de fechamento sem segredos.",
    )
    phase8_closeout_parser = subparsers.add_parser(
        "phase8-closeout-report",
        help="Exporta relatorio final de encerramento a partir do gate da Fase 8.",
    )
    phase8_closeout_parser.add_argument(
        "--closure-readiness",
        type=Path,
        required=True,
        help="JSON gerado pelo comando phase8-closure-readiness.",
    )
    phase8_closeout_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do Markdown final sem segredos.",
    )
    phase8_closeout_package_parser = subparsers.add_parser(
        "phase8-closeout-package",
        help="Exporta ZIP final de encerramento da Fase 8 com manifesto.",
    )
    phase8_closeout_package_parser.add_argument(
        "--closure-readiness",
        type=Path,
        required=True,
        help="JSON gerado pelo comando phase8-closure-readiness.",
    )
    phase8_closeout_package_parser.add_argument(
        "--closeout-report",
        type=Path,
        required=True,
        help="Markdown gerado pelo comando phase8-closeout-report.",
    )
    phase8_closeout_package_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do ZIP final sem segredos.",
    )
    phase8_finalize_parser = subparsers.add_parser(
        "phase8-finalize",
        help="Gera prontidao, relatorio e ZIP final da Fase 8 em um unico passo.",
    )
    phase8_finalize_parser.add_argument(
        "--asaas-verification",
        type=Path,
        help="JSON de verificacao do pacote Asaas Sandbox.",
    )
    phase8_finalize_parser.add_argument(
        "--asaas-summary",
        type=Path,
        help="Resumo Markdown de aceite do pacote Asaas Sandbox.",
    )
    phase8_finalize_parser.add_argument(
        "--postgres-package-verification",
        type=Path,
        help="JSON de verificacao do pacote PostgreSQL.",
    )
    phase8_finalize_parser.add_argument(
        "--postgres-report",
        type=Path,
        help="Relatorio Markdown da homologacao PostgreSQL descartavel.",
    )
    phase8_finalize_parser.add_argument(
        "--phase8-package-verification",
        type=Path,
        help="JSON de verificacao do pacote local de evidencias da Fase 8.",
    )
    phase8_finalize_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("documents/exports"),
        help="Diretorio local para os tres artefatos finais.",
    )
    phase8_finalize_dir_parser = subparsers.add_parser(
        "phase8-finalize-from-dir",
        help="Localiza artefatos finais em uma pasta e executa phase8-finalize.",
    )
    phase8_finalize_dir_parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("documents/exports"),
        help="Diretorio local com artefatos de Asaas, PostgreSQL e Fase 8.",
    )
    phase8_finalize_dir_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("documents/exports"),
        help="Diretorio local para os tres artefatos finais.",
    )
    readiness_parser = subparsers.add_parser(
        "postgres-readiness",
        help="Exporta prontidao local do runner PostgreSQL sem abrir conexao externa.",
    )
    readiness_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do JSON de prontidao sem segredos.",
    )
    postgres_package_parser = subparsers.add_parser(
        "postgres-validation-package",
        help="Exporta pacote ZIP local de homologacao PostgreSQL sem conexao externa.",
    )
    postgres_package_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do ZIP de homologacao PostgreSQL sem segredos.",
    )
    postgres_verify_parser = subparsers.add_parser(
        "postgres-verify-package",
        help="Verifica manifesto e hashes de um pacote ZIP PostgreSQL sem conexao externa.",
    )
    postgres_verify_parser.add_argument(
        "--package",
        type=Path,
        required=True,
        help="Caminho local do pacote ZIP de homologacao PostgreSQL.",
    )
    postgres_verify_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do JSON de verificacao sem segredos.",
    )
    postgres_summary_parser = subparsers.add_parser(
        "postgres-review-summary",
        help="Exporta resumo Markdown dos gates locais de homologacao PostgreSQL.",
    )
    postgres_summary_parser.add_argument(
        "--package",
        type=Path,
        required=True,
        help="Caminho local do pacote ZIP de homologacao PostgreSQL.",
    )
    postgres_summary_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do resumo Markdown sem segredos.",
    )
    network_readiness_parser = subparsers.add_parser(
        "network-readiness",
        help="Exporta prontidao local para uso em rede sem abrir conexao externa.",
    )
    network_readiness_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do JSON de prontidao de rede sem segredos.",
    )
    network_package_parser = subparsers.add_parser(
        "network-validation-package",
        help="Exporta pacote ZIP local de homologacao de rede sem conexao externa.",
    )
    network_package_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do ZIP de homologacao de rede sem segredos.",
    )
    network_verify_parser = subparsers.add_parser(
        "network-verify-package",
        help="Verifica manifesto e hashes de um pacote ZIP de rede sem conexao externa.",
    )
    network_verify_parser.add_argument(
        "--package",
        type=Path,
        required=True,
        help="Caminho local do pacote ZIP de homologacao de rede.",
    )
    network_verify_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do JSON de verificacao sem segredos.",
    )
    network_summary_parser = subparsers.add_parser(
        "network-review-summary",
        help="Exporta resumo Markdown dos gates locais de homologacao de rede.",
    )
    network_summary_parser.add_argument(
        "--package",
        type=Path,
        required=True,
        help="Caminho local do pacote ZIP de homologacao de rede.",
    )
    network_summary_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do resumo Markdown sem segredos.",
    )
    rehearsal_parser = subparsers.add_parser(
        "postgres-rehearsal",
        help="Executa homologacao SQLite -> PostgreSQL em alvo descartavel.",
    )
    rehearsal_parser.add_argument(
        "--confirm-disposable-target",
        action="store_true",
        help="Confirma que o PostgreSQL alvo e descartavel e pode receber a carga.",
    )
    rehearsal_parser.add_argument(
        "--output",
        type=Path,
        help="Caminho local do relatorio Markdown sem segredos.",
    )
    namespace = parser.parse_args(args)
    if namespace.command == "asaas-readiness":
        return _run_asaas_readiness_command(
            settings=settings,
            request_id=namespace.request_id,
            output_path=namespace.output,
        )
    if namespace.command == "asaas-execute":
        return _run_asaas_execute_command(
            settings=settings,
            request_id=namespace.request_id,
            actor_user_id=namespace.actor_user_id,
            output_path=namespace.output,
            confirm_sandbox=namespace.confirm_sandbox,
        )
    if namespace.command == "asaas-execution-report":
        return _run_asaas_execution_report_command(
            settings=settings,
            request_id=namespace.request_id,
            output_path=namespace.output,
        )
    if namespace.command == "asaas-validation-package":
        return _run_asaas_validation_package_command(
            settings=settings,
            request_id=namespace.request_id,
            output_path=namespace.output,
        )
    if namespace.command == "asaas-verify-package":
        return _run_asaas_verify_package_command(
            package_path=namespace.package,
            output_path=namespace.output,
        )
    if namespace.command == "asaas-review-summary":
        return _run_asaas_review_summary_command(
            package_path=namespace.package,
            output_path=namespace.output,
        )
    if namespace.command == "phase8-acceptance-report":
        return _run_phase8_acceptance_report_command(
            settings=settings,
            output_path=namespace.output,
        )
    if namespace.command == "phase8-evidence-package":
        return _run_phase8_evidence_package_command(
            settings=settings,
            output_path=namespace.output,
        )
    if namespace.command == "phase8-verify-package":
        return _run_phase8_verify_package_command(
            package_path=namespace.package,
            output_path=namespace.output,
        )
    if namespace.command == "phase8-review-summary":
        return _run_phase8_review_summary_command(
            package_path=namespace.package,
            output_path=namespace.output,
        )
    if namespace.command == "phase8-closure-readiness":
        return _run_phase8_closure_readiness_command(
            asaas_verification_path=namespace.asaas_verification,
            asaas_summary_path=namespace.asaas_summary,
            postgres_package_verification_path=namespace.postgres_package_verification,
            postgres_rehearsal_report_path=namespace.postgres_report,
            phase8_package_verification_path=namespace.phase8_package_verification,
            output_path=namespace.output,
        )
    if namespace.command == "phase8-closeout-report":
        return _run_phase8_closeout_report_command(
            closure_readiness_path=namespace.closure_readiness,
            output_path=namespace.output,
        )
    if namespace.command == "phase8-closeout-package":
        return _run_phase8_closeout_package_command(
            closure_readiness_path=namespace.closure_readiness,
            closeout_report_path=namespace.closeout_report,
            output_path=namespace.output,
        )
    if namespace.command == "phase8-finalize":
        return _run_phase8_finalize_command(
            asaas_verification_path=namespace.asaas_verification,
            asaas_summary_path=namespace.asaas_summary,
            postgres_package_verification_path=namespace.postgres_package_verification,
            postgres_rehearsal_report_path=namespace.postgres_report,
            phase8_package_verification_path=namespace.phase8_package_verification,
            output_dir=namespace.output_dir,
        )
    if namespace.command == "phase8-finalize-from-dir":
        return _run_phase8_finalize_from_dir_command(
            input_dir=namespace.input_dir,
            output_dir=namespace.output_dir,
        )
    if namespace.command == "postgres-readiness":
        return _run_postgres_readiness_command(
            settings=settings,
            output_path=namespace.output,
        )
    if namespace.command == "postgres-validation-package":
        return _run_postgres_validation_package_command(
            settings=settings,
            output_path=namespace.output,
        )
    if namespace.command == "postgres-verify-package":
        return _run_postgres_verify_package_command(
            package_path=namespace.package,
            output_path=namespace.output,
        )
    if namespace.command == "postgres-review-summary":
        return _run_postgres_review_summary_command(
            package_path=namespace.package,
            output_path=namespace.output,
        )
    if namespace.command == "network-readiness":
        return _run_network_readiness_command(
            settings=settings,
            output_path=namespace.output,
        )
    if namespace.command == "network-validation-package":
        return _run_network_validation_package_command(
            settings=settings,
            output_path=namespace.output,
        )
    if namespace.command == "network-verify-package":
        return _run_network_verify_package_command(
            package_path=namespace.package,
            output_path=namespace.output,
        )
    if namespace.command == "network-review-summary":
        return _run_network_review_summary_command(
            package_path=namespace.package,
            output_path=namespace.output,
        )
    if namespace.command == "postgres-rehearsal":
        return _run_postgres_rehearsal_command(
            settings=settings,
            output_path=namespace.output,
            confirm_disposable_target=namespace.confirm_disposable_target,
        )
    parser.error("Comando administrativo desconhecido")


def _run_asaas_readiness_command(
    *,
    settings: Settings,
    request_id: int,
    output_path: Path | None,
) -> int:
    report_path = output_path or (
        settings.paths.data_dir
        / "homologacao-asaas"
        / f"prontidao-execucao-asaas-{request_id}.json"
    )
    with connect(settings.database_path) as connection:
        migrate(connection)
        payload = build_asaas_execution_readiness_json(
            connection,
            settings=settings,
            request_id=request_id,
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(payload, encoding="utf-8")
    print(  # noqa: T201
        f"Prontidao Asaas exportada. Arquivo local: {report_path}"
    )
    return 0


def _run_asaas_execute_command(
    *,
    settings: Settings,
    request_id: int,
    actor_user_id: int | None,
    output_path: Path | None,
    confirm_sandbox: bool,
) -> int:
    if not confirm_sandbox:
        raise ValueError("Use --confirm-sandbox apenas com chave Sandbox no .env local")
    if settings.asaas_env.strip().lower() != "sandbox":
        raise ValueError("asaas-execute e permitido somente com ASAAS_ENV=sandbox")

    with connect(settings.database_path) as connection:
        migrate(connection)
        execution = execute_approved_asaas_operation(
            connection,
            settings=settings,
            request_id=request_id,
            actor_user_id=actor_user_id,
            transport=urllib_asaas_write_transport,
        )

    payload = {
        "contains_credentials": False,
        "environment": settings.asaas_env,
        "request_id": request_id,
        "execution_id": execution.id,
        "status": execution.status,
        "external_id": execution.external_id,
        "idempotency_key": execution.idempotency_key,
        "error_recorded": execution.error_message is not None,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(  # noqa: T201
        "Execucao Asaas Sandbox registrada. "
        f"Solicitacao: {request_id}; status: {execution.status}; "
        f"execucao local: {execution.id}"
    )
    return 0 if execution.status == "succeeded" else 1


def _run_asaas_execution_report_command(
    *,
    settings: Settings,
    request_id: int,
    output_path: Path | None,
) -> int:
    report_path = output_path or (
        settings.paths.data_dir
        / "homologacao-asaas"
        / f"evidencia-execucao-asaas-{request_id}.json"
    )
    with connect(settings.database_path) as connection:
        migrate(connection)
        payload = build_asaas_execution_report_json(
            connection,
            settings=settings,
            request_id=request_id,
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(payload, encoding="utf-8")
    print(  # noqa: T201
        f"Evidencia Asaas exportada. Arquivo local: {report_path}"
    )
    return 0


def _run_asaas_validation_package_command(
    *,
    settings: Settings,
    request_id: int,
    output_path: Path | None,
) -> int:
    package_path = output_path or (
        settings.paths.data_dir / "homologacao-asaas" / f"pacote-homologacao-asaas-{request_id}.zip"
    )
    with connect(settings.database_path) as connection:
        migrate(connection)
        write_asaas_sandbox_validation_package(
            connection,
            settings=settings,
            request_id=request_id,
            output_path=package_path,
        )
    print(  # noqa: T201
        f"Pacote de homologacao Asaas exportado. Arquivo local: {package_path}"
    )
    return 0


def _run_asaas_verify_package_command(
    *,
    package_path: Path,
    output_path: Path | None,
) -> int:
    payload = build_asaas_sandbox_validation_package_verification_json(
        package_path=package_path,
    )
    parsed = json.loads(payload)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(  # noqa: T201
        f"Verificacao de pacote Asaas concluida. Pronto para revisao: {parsed['ready_for_review']}"
    )
    return 0 if parsed["ready_for_review"] else 1


def _run_asaas_review_summary_command(
    *,
    package_path: Path,
    output_path: Path | None,
) -> int:
    summary = build_asaas_sandbox_validation_review_summary_markdown(
        package_path=package_path,
    )
    verification = json.loads(
        build_asaas_sandbox_validation_package_verification_json(
            package_path=package_path,
        )
    )
    summary_path = output_path or package_path.with_name(
        f"{package_path.stem}-resumo-aceite.md",
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")
    print(  # noqa: T201
        "Resumo de aceite Asaas exportado. "
        f"Pronto para revisao: {verification['ready_for_review']}; "
        f"Arquivo local: {summary_path}"
    )
    return 0 if verification["ready_for_review"] else 1


def _run_phase8_acceptance_report_command(
    *,
    settings: Settings,
    output_path: Path | None,
) -> int:
    report_path = output_path or (settings.paths.data_dir / "fase-8" / "aceite-local-fase-8.md")
    readiness = get_deployment_readiness(settings)
    health = None
    inventory = None
    if readiness.database_backend == "sqlite":
        with connect(settings.database_path) as connection:
            migrate(connection)
            health = get_local_database_health(connection)
            inventory = get_local_schema_inventory(connection)
    report = build_phase8_local_acceptance_report_markdown(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(  # noqa: T201
        f"Relatorio local de aceite da Fase 8 exportado. Arquivo local: {report_path}"
    )
    return 0


def _run_phase8_evidence_package_command(
    *,
    settings: Settings,
    output_path: Path | None,
) -> int:
    package_path = output_path or (
        settings.paths.data_dir / "fase-8" / "pacote-evidencias-fase-8.zip"
    )
    readiness = get_deployment_readiness(settings)
    health = None
    inventory = None
    if readiness.database_backend == "sqlite":
        with connect(settings.database_path) as connection:
            migrate(connection)
            health = get_local_database_health(connection)
            inventory = get_local_schema_inventory(connection)
    write_phase8_local_evidence_package(
        output_path=package_path,
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )
    print(  # noqa: T201
        f"Pacote local de evidencias da Fase 8 exportado. Arquivo local: {package_path}"
    )
    return 0


def _run_phase8_verify_package_command(
    *,
    package_path: Path,
    output_path: Path | None,
) -> int:
    payload = build_phase8_local_evidence_package_verification_json(
        package_path=package_path,
    )
    parsed = json.loads(payload)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(  # noqa: T201
        "Verificacao de pacote da Fase 8 concluida. "
        f"Pronto para revisao: {parsed['ready_for_review']}"
    )
    return 0 if parsed["ready_for_review"] else 1


def _run_phase8_review_summary_command(
    *,
    package_path: Path,
    output_path: Path | None,
) -> int:
    summary = build_phase8_local_evidence_review_summary_markdown(
        package_path=package_path,
    )
    verification = json.loads(
        build_phase8_local_evidence_package_verification_json(
            package_path=package_path,
        )
    )
    summary_path = output_path or package_path.with_name(
        f"{package_path.stem}-resumo-aceite.md",
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")
    print(  # noqa: T201
        "Resumo de aceite da Fase 8 exportado. "
        f"Pronto para revisao: {verification['ready_for_review']}; "
        f"Arquivo local: {summary_path}"
    )
    return 0 if verification["ready_for_review"] else 1


def _run_phase8_closure_readiness_command(
    *,
    asaas_verification_path: Path | None,
    asaas_summary_path: Path | None,
    postgres_package_verification_path: Path | None,
    postgres_rehearsal_report_path: Path | None,
    phase8_package_verification_path: Path | None,
    output_path: Path | None,
) -> int:
    report_path = output_path or Path("documents/exports/prontidao-fechamento-fase-8.json")
    payload = build_phase8_closure_readiness_json(
        asaas_verification_path=asaas_verification_path,
        asaas_summary_path=asaas_summary_path,
        postgres_package_verification_path=postgres_package_verification_path,
        postgres_rehearsal_report_path=postgres_rehearsal_report_path,
        phase8_package_verification_path=phase8_package_verification_path,
    )
    parsed = json.loads(payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(payload, encoding="utf-8")
    print(  # noqa: T201
        "Prontidao de fechamento da Fase 8 exportada. "
        f"Pronto para fechar: {parsed['ready_to_close_phase8']}; "
        f"Arquivo local: {report_path}"
    )
    return 0 if parsed["ready_to_close_phase8"] else 1


def _run_phase8_closeout_report_command(
    *,
    closure_readiness_path: Path,
    output_path: Path | None,
) -> int:
    report = build_phase8_closeout_report_markdown(
        closure_readiness_path=closure_readiness_path,
    )
    ready_to_close = "Status: **Fase 8 pronta para encerramento operacional**" in report
    report_path = output_path or closure_readiness_path.with_name(
        "encerramento-fase-8.md",
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(  # noqa: T201
        "Relatorio final da Fase 8 exportado. "
        f"Pronto para fechar: {ready_to_close}; "
        f"Arquivo local: {report_path}"
    )
    return 0 if ready_to_close else 1


def _run_phase8_closeout_package_command(
    *,
    closure_readiness_path: Path,
    closeout_report_path: Path,
    output_path: Path | None,
) -> int:
    package_path = output_path or closeout_report_path.with_name(
        "pacote-encerramento-fase-8.zip",
    )
    write_phase8_closeout_package(
        closure_readiness_path=closure_readiness_path,
        closeout_report_path=closeout_report_path,
        output_path=package_path,
    )
    print(  # noqa: T201
        f"Pacote final da Fase 8 exportado. Arquivo local: {package_path}"
    )
    return 0


def _run_phase8_finalize_command(
    *,
    asaas_verification_path: Path | None,
    asaas_summary_path: Path | None,
    postgres_package_verification_path: Path | None,
    postgres_rehearsal_report_path: Path | None,
    phase8_package_verification_path: Path | None,
    output_dir: Path,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    closure_readiness_path = output_dir / "prontidao-fechamento-fase-8.json"
    closeout_report_path = output_dir / "encerramento-fase-8.md"
    package_path = output_dir / "pacote-encerramento-fase-8.zip"
    payload = build_phase8_closure_readiness_json(
        asaas_verification_path=asaas_verification_path,
        asaas_summary_path=asaas_summary_path,
        postgres_package_verification_path=postgres_package_verification_path,
        postgres_rehearsal_report_path=postgres_rehearsal_report_path,
        phase8_package_verification_path=phase8_package_verification_path,
    )
    closure_readiness_path.write_text(payload, encoding="utf-8")
    report = build_phase8_closeout_report_markdown(
        closure_readiness_path=closure_readiness_path,
    )
    closeout_report_path.write_text(report, encoding="utf-8")
    write_phase8_closeout_package(
        closure_readiness_path=closure_readiness_path,
        closeout_report_path=closeout_report_path,
        output_path=package_path,
    )
    ready_to_close = json.loads(payload)["ready_to_close_phase8"]
    print(  # noqa: T201
        "Finalizacao da Fase 8 exportada. "
        f"Pronto para fechar: {ready_to_close}; "
        f"Diretorio local: {output_dir}"
    )
    return 0 if ready_to_close else 1


def _run_phase8_finalize_from_dir_command(
    *,
    input_dir: Path,
    output_dir: Path,
) -> int:
    return _run_phase8_finalize_command(
        asaas_verification_path=_latest_matching_path(
            input_dir,
            "verificacao-pacote-asaas*.json",
        ),
        asaas_summary_path=_latest_matching_path(
            input_dir,
            "resumo-aceite-asaas*.md",
        ),
        postgres_package_verification_path=_latest_matching_path(
            input_dir,
            "verificacao-pacote-postgresql.json",
        ),
        postgres_rehearsal_report_path=_latest_matching_path(
            input_dir,
            "relatorio-homologacao-postgresql.md",
        ),
        phase8_package_verification_path=_latest_matching_path(
            input_dir,
            "verificacao-pacote-fase-8.json",
        ),
        output_dir=output_dir,
    )


def _latest_matching_path(directory: Path, pattern: str) -> Path | None:
    matches = [path for path in directory.glob(pattern) if path.is_file()]
    return max(matches, key=lambda path: path.stat().st_mtime) if matches else None


def _run_postgres_readiness_command(
    *,
    settings: Settings,
    output_path: Path | None,
) -> int:
    report_path = output_path or (
        settings.paths.data_dir
        / "homologacao-postgresql"
        / "prontidao-runner-homologacao-postgresql.json"
    )
    with connect(settings.database_path) as connection:
        migrate(connection)
        readiness = get_deployment_readiness(settings)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)
        payload = build_postgres_rehearsal_runner_readiness_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(payload, encoding="utf-8")
    print(  # noqa: T201
        f"Prontidao PostgreSQL exportada. Arquivo local: {report_path}"
    )
    return 0


def _run_postgres_validation_package_command(
    *,
    settings: Settings,
    output_path: Path | None,
) -> int:
    package_path = output_path or (
        settings.paths.data_dir / "homologacao-postgresql" / "pacote-homologacao-postgresql.zip"
    )
    with connect(settings.database_path) as connection:
        migrate(connection)
        readiness = get_deployment_readiness(settings)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)
        write_postgres_rehearsal_package(
            output_path=package_path,
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    print(  # noqa: T201
        f"Pacote de homologacao PostgreSQL exportado. Arquivo local: {package_path}"
    )
    return 0


def _run_postgres_verify_package_command(
    *,
    package_path: Path,
    output_path: Path | None,
) -> int:
    payload = build_postgres_rehearsal_package_verification_json(
        package_path=package_path,
    )
    parsed = json.loads(payload)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(  # noqa: T201
        "Verificacao de pacote PostgreSQL concluida. "
        f"Pronto para revisao: {parsed['ready_for_review']}"
    )
    return 0 if parsed["ready_for_review"] else 1


def _run_postgres_review_summary_command(
    *,
    package_path: Path,
    output_path: Path | None,
) -> int:
    summary = build_postgres_rehearsal_review_summary_markdown(
        package_path=package_path,
    )
    verification = json.loads(
        build_postgres_rehearsal_package_verification_json(
            package_path=package_path,
        )
    )
    summary_path = output_path or package_path.with_name(
        f"{package_path.stem}-resumo-aceite.md",
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")
    print(  # noqa: T201
        "Resumo de aceite PostgreSQL exportado. "
        f"Pronto para revisao: {verification['ready_for_review']}; "
        f"Arquivo local: {summary_path}"
    )
    return 0 if verification["ready_for_review"] else 1


def _run_network_readiness_command(
    *,
    settings: Settings,
    output_path: Path | None,
) -> int:
    report_path = output_path or (
        settings.paths.data_dir / "homologacao-rede" / "prontidao-uso-em-rede.json"
    )
    readiness = get_deployment_readiness(settings)
    health = None
    if readiness.database_backend == "sqlite":
        with connect(settings.database_path) as connection:
            migrate(connection)
            health = get_local_database_health(connection)
    payload = build_network_readiness_json(
        settings=settings,
        readiness=readiness,
        health=health,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(payload, encoding="utf-8")
    print(  # noqa: T201
        f"Prontidao de rede exportada. Arquivo local: {report_path}"
    )
    return 0


def _run_network_validation_package_command(
    *,
    settings: Settings,
    output_path: Path | None,
) -> int:
    package_path = output_path or (
        settings.paths.data_dir / "homologacao-rede" / "pacote-homologacao-rede.zip"
    )
    readiness = get_deployment_readiness(settings)
    health = None
    if readiness.database_backend == "sqlite":
        with connect(settings.database_path) as connection:
            migrate(connection)
            health = get_local_database_health(connection)
    write_network_rehearsal_package(
        output_path=package_path,
        settings=settings,
        readiness=readiness,
        health=health,
    )
    print(  # noqa: T201
        f"Pacote de homologacao de rede exportado. Arquivo local: {package_path}"
    )
    return 0


def _run_network_verify_package_command(
    *,
    package_path: Path,
    output_path: Path | None,
) -> int:
    payload = build_network_rehearsal_package_verification_json(
        package_path=package_path,
    )
    parsed = json.loads(payload)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(  # noqa: T201
        "Verificacao de pacote de rede concluida. "
        f"Pronto para revisao: {parsed['ready_for_review']}"
    )
    return 0 if parsed["ready_for_review"] else 1


def _run_network_review_summary_command(
    *,
    package_path: Path,
    output_path: Path | None,
) -> int:
    summary = build_network_rehearsal_review_summary_markdown(
        package_path=package_path,
    )
    verification = json.loads(
        build_network_rehearsal_package_verification_json(
            package_path=package_path,
        )
    )
    summary_path = output_path or package_path.with_name(
        f"{package_path.stem}-resumo-aceite.md",
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")
    print(  # noqa: T201
        "Resumo de aceite de rede exportado. "
        f"Pronto para revisao: {verification['ready_for_review']}; "
        f"Arquivo local: {summary_path}"
    )
    return 0 if verification["ready_for_review"] else 1


def _run_postgres_rehearsal_command(
    *,
    settings: Settings,
    output_path: Path | None,
    confirm_disposable_target: bool,
) -> int:
    if not confirm_disposable_target:
        raise ValueError(
            "Use --confirm-disposable-target apenas com PostgreSQL vazio e descartavel"
        )
    report_path = output_path or (
        settings.paths.data_dir / "homologacao-postgresql" / "relatorio-homologacao-postgresql.md"
    )
    with connect(settings.database_path) as connection:
        migrate(connection)
        report = run_postgres_rehearsal_admin_action(
            settings=settings,
            sqlite_connection=connection,
            output_path=report_path,
        )
    print(  # noqa: T201
        f"Homologacao PostgreSQL concluida. Relatorio local: {report.output_path}"
    )
    return 0
