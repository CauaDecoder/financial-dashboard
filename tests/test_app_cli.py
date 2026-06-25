import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from basilica_financeiro import app
from basilica_financeiro.config import Settings
from basilica_financeiro.database import connect, migrate
from basilica_financeiro.paths import AppPaths
from basilica_financeiro.repositories.users import create_user
from basilica_financeiro.services.approvals import (
    approve_sensitive_operation_request,
    create_sensitive_operation_request,
)
from basilica_financeiro.services.asaas_write_executor import (
    execute_approved_asaas_operation,
    write_asaas_sandbox_validation_package,
)


def test_asaas_readiness_cli_exports_safe_json_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    output_path = tmp_path / "reports" / "asaas-prontidao.json"
    settings.paths.ensure_directories()
    with connect(settings.database_path) as connection:
        migrate(connection)
        requester_id = create_user(
            connection,
            username="solicitante",
            password="SenhaForte123!",
            role="operador_financeiro",
            actor_user_id=None,
        )
        request_id = create_sensitive_operation_request(
            connection,
            operation_type="asaas_create_charge",
            title="Criar cobranca Sandbox",
            amount_cents=1_000,
            payload={
                "customer_id": "cus_123",
                "description": "Validacao Sandbox",
                "value_cents": 1_000,
            },
            requested_by=requester_id,
        )

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(
        [
            "asaas-readiness",
            "--request-id",
            str(request_id),
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["metadata_only"] is True
    assert payload["contains_credentials"] is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_write_operation"] is False
    assert payload["request_id"] == request_id
    assert payload["readiness_ready"] is False
    assert "Prontidao Asaas exportada" in capsys.readouterr().out
    with connect(settings.database_path) as connection:
        users_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert users_count == 1


def test_asaas_execute_cli_requires_sandbox_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(
        tmp_path,
        asaas_api_key="test-token",
        asaas_enable_write_operations=True,
    )
    called = False

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)

    def fail_if_called(**kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(app, "execute_approved_asaas_operation", fail_if_called)

    exit_code = app.main(["asaas-execute", "--request-id", "1"])

    assert exit_code == 1
    assert "confirm-sandbox" in capsys.readouterr().err
    assert called is False


def test_asaas_execute_cli_blocks_production_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(
        tmp_path,
        asaas_env="production",
        asaas_api_key="test-token",
        asaas_enable_write_operations=True,
    )
    called = False

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)

    def fail_if_called(**kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(app, "execute_approved_asaas_operation", fail_if_called)

    exit_code = app.main(["asaas-execute", "--request-id", "1", "--confirm-sandbox"])

    assert exit_code == 1
    assert "ASAAS_ENV=sandbox" in capsys.readouterr().err
    assert called is False


def test_asaas_execute_cli_runs_sandbox_executor_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(
        tmp_path,
        asaas_api_key="test-token",
        asaas_enable_write_operations=True,
    )
    output_path = tmp_path / "reports" / "execucao-asaas.json"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    def fake_execute(connection: object, **kwargs: object) -> SimpleNamespace:
        assert kwargs["settings"] is settings
        assert kwargs["request_id"] == 7
        assert kwargs["actor_user_id"] == 3
        assert kwargs["transport"] is app.urllib_asaas_write_transport
        assert connection.execute("SELECT version FROM schema_version").fetchone()  # type: ignore[attr-defined]
        return SimpleNamespace(
            id=11,
            status="succeeded",
            external_id="pay_123",
            idempotency_key="basilica-sensitive-operation-7",
            error_message=None,
        )

    monkeypatch.setattr(app, "execute_approved_asaas_operation", fake_execute)

    exit_code = app.main(
        [
            "asaas-execute",
            "--request-id",
            "7",
            "--actor-user-id",
            "3",
            "--confirm-sandbox",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload == {
        "contains_credentials": False,
        "environment": "sandbox",
        "error_recorded": False,
        "execution_id": 11,
        "external_id": "pay_123",
        "idempotency_key": "basilica-sensitive-operation-7",
        "request_id": 7,
        "status": "succeeded",
    }
    assert "test-token" not in output_path.read_text(encoding="utf-8")
    assert "Execucao Asaas Sandbox registrada" in capsys.readouterr().out
    with connect(settings.database_path) as connection:
        users_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert users_count == 0


def test_asaas_execution_report_cli_exports_safe_json_without_external_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(
        tmp_path,
        asaas_api_key="test-token",
        asaas_enable_write_operations=True,
    )
    output_path = tmp_path / "reports" / "evidencia-asaas.json"
    settings.paths.ensure_directories()
    with connect(settings.database_path) as connection:
        migrate(connection)
        requester_id = create_user(
            connection,
            username="solicitante",
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
        request_id = create_sensitive_operation_request(
            connection,
            operation_type="asaas_create_charge",
            title="Criar cobranca Sandbox",
            amount_cents=1_000,
            payload={
                "customer_id": "cus_123",
                "description": "Validacao Sandbox",
                "value_cents": 1_000,
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
        execute_approved_asaas_operation(
            connection,
            settings=settings,
            request_id=request_id,
            actor_user_id=second_approver_id,
            transport=lambda **_: {
                "id": "pay_123",
                "status": "PENDING",
                "invoiceUrl": "https://sandbox.local/cobranca",
            },
        )

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(
        [
            "asaas-execution-report",
            "--request-id",
            str(request_id),
            "--output",
            str(output_path),
        ]
    )

    content = output_path.read_text(encoding="utf-8")
    payload = json.loads(content)

    assert exit_code == 0
    assert payload["metadata_only"] is True
    assert payload["contains_credentials"] is False
    assert payload["contains_request_payload"] is False
    assert payload["contains_api_response"] is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_write_operation"] is False
    assert payload["execution_registered"] is True
    assert payload["execution_status"] == "succeeded"
    assert payload["external_id"] == "pay_123"
    assert "test-token" not in content
    assert "invoiceUrl" not in content
    assert "Validacao Sandbox" not in content
    assert "Evidencia Asaas exportada" in capsys.readouterr().out


def test_asaas_validation_package_cli_exports_safe_zip_without_external_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(
        tmp_path,
        asaas_api_key="test-token",
        asaas_enable_write_operations=True,
    )
    output_path = tmp_path / "reports" / "homologacao-asaas.zip"
    settings.paths.ensure_directories()
    with connect(settings.database_path) as connection:
        migrate(connection)
        requester_id = create_user(
            connection,
            username="solicitante",
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
        request_id = create_sensitive_operation_request(
            connection,
            operation_type="asaas_create_charge",
            title="Criar cobranca Sandbox",
            amount_cents=1_000,
            payload={
                "customer_id": "cus_123",
                "description": "Validacao Sandbox",
                "value_cents": 1_000,
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
        execute_approved_asaas_operation(
            connection,
            settings=settings,
            request_id=request_id,
            actor_user_id=second_approver_id,
            transport=lambda **_: {
                "id": "pay_123",
                "status": "PENDING",
                "invoiceUrl": "https://sandbox.local/cobranca",
            },
        )

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(
        [
            "asaas-validation-package",
            "--request-id",
            str(request_id),
            "--output",
            str(output_path),
        ]
    )

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifesto-homologacao-asaas.json").decode("utf-8"))
        joined_content = "\n".join(
            archive.read(name).decode("utf-8") for name in archive.namelist()
        )

    assert exit_code == 0
    assert names == {
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
    assert "test-token" not in joined_content
    assert "invoiceUrl" not in joined_content
    assert "Validacao Sandbox" not in joined_content
    assert "Pacote de homologacao Asaas exportado" in capsys.readouterr().out


def test_asaas_verify_package_cli_exports_safe_verification_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(
        tmp_path,
        asaas_api_key="test-token",
        asaas_enable_write_operations=True,
    )
    package_path = tmp_path / "reports" / "homologacao-asaas.zip"
    output_path = tmp_path / "reports" / "verificacao-asaas.json"
    settings.paths.ensure_directories()
    with connect(settings.database_path) as connection:
        migrate(connection)
        requester_id = create_user(
            connection,
            username="solicitante",
            password="SenhaForte123!",
            role="operador_financeiro",
            actor_user_id=None,
        )
        request_id = create_sensitive_operation_request(
            connection,
            operation_type="asaas_create_charge",
            title="Criar cobranca Sandbox",
            amount_cents=1_000,
            payload={
                "customer_id": "cus_123",
                "description": "Validacao Sandbox",
                "value_cents": 1_000,
            },
            requested_by=requester_id,
        )
        write_asaas_sandbox_validation_package(
            connection,
            settings=settings,
            request_id=request_id,
            output_path=package_path,
        )

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(
        [
            "asaas-verify-package",
            "--package",
            str(package_path),
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["metadata_only"] is True
    assert payload["opens_external_connection"] is False
    assert payload["executes_write_operation"] is False
    assert payload["ready_for_review"] is True
    assert payload["safe_flags_valid"] is True
    assert payload["hashes_valid"] is True
    assert "test-token" not in output_path.read_text(encoding="utf-8")
    assert "Pronto para revisao: True" in capsys.readouterr().out


def test_asaas_review_summary_cli_exports_safe_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(
        tmp_path,
        asaas_api_key="test-token",
        asaas_enable_write_operations=True,
    )
    package_path = tmp_path / "reports" / "homologacao-asaas.zip"
    output_path = tmp_path / "reports" / "resumo-aceite-asaas.md"
    settings.paths.ensure_directories()
    with connect(settings.database_path) as connection:
        migrate(connection)
        requester_id = create_user(
            connection,
            username="solicitante",
            password="SenhaForte123!",
            role="operador_financeiro",
            actor_user_id=None,
        )
        request_id = create_sensitive_operation_request(
            connection,
            operation_type="asaas_create_charge",
            title="Criar cobranca Sandbox",
            amount_cents=1_000,
            payload={
                "customer_id": "cus_123",
                "description": "Validacao Sandbox",
                "value_cents": 1_000,
            },
            requested_by=requester_id,
        )
        write_asaas_sandbox_validation_package(
            connection,
            settings=settings,
            request_id=request_id,
            output_path=package_path,
        )

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(
        [
            "asaas-review-summary",
            "--package",
            str(package_path),
            "--output",
            str(output_path),
        ]
    )

    content = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "Status: **pronto para revisao tecnica**" in content
    assert "- [x] Hashes conferidos" in content
    assert "test-token" not in content
    assert "Validacao Sandbox" not in content
    assert "Resumo de aceite Asaas exportado" in capsys.readouterr().out


def test_postgres_readiness_cli_exports_safe_json_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    output_path = tmp_path / "reports" / "prontidao.json"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(["postgres-readiness", "--output", str(output_path)])

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["metadata_only"] is True
    assert payload["contains_financial_rows"] is False
    assert payload["contains_credentials"] is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_migration"] is False
    assert payload["ready_for_opt_in_runner"] is False
    assert str(output_path) in capsys.readouterr().out
    with connect(settings.database_path) as connection:
        users_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert users_count == 0


def test_network_readiness_cli_exports_safe_json_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    output_path = tmp_path / "reports" / "prontidao-rede.json"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(["network-readiness", "--output", str(output_path)])

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["metadata_only"] is True
    assert payload["contains_financial_rows"] is False
    assert payload["contains_credentials"] is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_migration"] is False
    assert payload["ready_for_network_use"] is False
    assert str(output_path) in capsys.readouterr().out
    with connect(settings.database_path) as connection:
        users_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert users_count == 0


def test_network_validation_package_cli_exports_zip_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    output_path = tmp_path / "reports" / "pacote-rede.zip"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(["network-validation-package", "--output", str(output_path)])

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifesto-homologacao-rede.json").decode("utf-8"))

    assert exit_code == 0
    assert "prontidao-uso-em-rede.json" in names
    assert "checklist-homologacao-rede.md" in names
    assert manifest["contains_credentials"] is False
    assert manifest["contains_financial_rows"] is False
    assert str(output_path) in capsys.readouterr().out
    with connect(settings.database_path) as connection:
        users_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert users_count == 0


def test_network_verify_package_cli_exports_safe_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    package_path = tmp_path / "reports" / "pacote-rede.zip"
    output_path = tmp_path / "reports" / "verificacao-rede.json"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    assert app.main(["network-validation-package", "--output", str(package_path)]) == 0
    exit_code = app.main(
        [
            "network-verify-package",
            "--package",
            str(package_path),
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ready_for_review"] is True
    assert payload["contains_disallowed_markers"] is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_migration"] is False
    assert "Verificacao de pacote de rede concluida" in capsys.readouterr().out


def test_network_review_summary_cli_exports_safe_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    package_path = tmp_path / "reports" / "pacote-rede.zip"
    output_path = tmp_path / "reports" / "resumo-rede.md"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    assert app.main(["network-validation-package", "--output", str(package_path)]) == 0
    exit_code = app.main(
        [
            "network-review-summary",
            "--package",
            str(package_path),
            "--output",
            str(output_path),
        ]
    )

    content = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "Status: **pronto para revisao tecnica**" in content
    assert "- [x] Hashes conferidos" in content
    assert "BACKUP_ENCRYPTION_KEY=" not in content
    assert "Resumo de aceite de rede exportado" in capsys.readouterr().out


def test_postgres_validation_package_cli_exports_zip_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    output_path = tmp_path / "reports" / "pacote-postgresql.zip"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(["postgres-validation-package", "--output", str(output_path)])

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifesto-homologacao.json").decode("utf-8"))

    assert exit_code == 0
    assert "blueprint-postgresql.sql" in names
    assert "plano-carga-postgresql.json" in names
    assert "contrato-adapter-postgresql.json" in names
    assert manifest["contains_credentials"] is False
    assert manifest["contains_financial_rows"] is False
    assert str(output_path) in capsys.readouterr().out
    with connect(settings.database_path) as connection:
        users_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert users_count == 0


def test_phase8_acceptance_report_cli_exports_safe_markdown_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    output_path = tmp_path / "reports" / "aceite-fase-8.md"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(["phase8-acceptance-report", "--output", str(output_path)])

    content = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "# Aceite local da Fase 8" in content
    assert "Fase 8 ainda nao encerrada" in content
    assert "ASAAS_API_KEY=" not in content
    assert "BACKUP_ENCRYPTION_KEY=" not in content
    assert "Relatorio local de aceite da Fase 8 exportado" in capsys.readouterr().out
    with connect(settings.database_path) as connection:
        users_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert users_count == 0


def test_phase8_evidence_package_cli_exports_safe_zip_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    output_path = tmp_path / "reports" / "pacote-fase-8.zip"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(["phase8-evidence-package", "--output", str(output_path)])

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifesto-evidencias-fase-8.json").decode("utf-8"))

    assert exit_code == 0
    assert "aceite-local-fase-8.md" in names
    assert "prontidao-uso-em-rede.json" in names
    assert manifest["contains_credentials"] is False
    assert manifest["phase_complete"] is False
    assert "Pacote local de evidencias da Fase 8 exportado" in capsys.readouterr().out
    with connect(settings.database_path) as connection:
        users_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert users_count == 0


def test_phase8_verify_package_cli_exports_safe_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    package_path = tmp_path / "reports" / "pacote-fase-8.zip"
    output_path = tmp_path / "reports" / "verificacao-fase-8.json"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    assert app.main(["phase8-evidence-package", "--output", str(package_path)]) == 0
    exit_code = app.main(
        [
            "phase8-verify-package",
            "--package",
            str(package_path),
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ready_for_review"] is True
    assert payload["phase_completion_guard_valid"] is True
    assert payload["contains_disallowed_markers"] is False
    assert "Verificacao de pacote da Fase 8 concluida" in capsys.readouterr().out


def test_phase8_review_summary_cli_exports_safe_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    package_path = tmp_path / "reports" / "pacote-fase-8.zip"
    output_path = tmp_path / "reports" / "resumo-fase-8.md"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    assert app.main(["phase8-evidence-package", "--output", str(package_path)]) == 0
    exit_code = app.main(
        [
            "phase8-review-summary",
            "--package",
            str(package_path),
            "--output",
            str(output_path),
        ]
    )

    content = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "Status: **pronto para revisao tecnica**" in content
    assert "- [x] Conclusao da fase permanece pendente" in content
    assert "ASAAS_API_KEY=" not in content
    assert "Resumo de aceite da Fase 8 exportado" in capsys.readouterr().out


def test_phase8_closure_readiness_cli_exports_safe_json_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    output_path = tmp_path / "reports" / "prontidao-fechamento-fase-8.json"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(["phase8-closure-readiness", "--output", str(output_path)])

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["ready_to_close_phase8"] is False
    assert payload["contains_credentials"] is False
    assert payload["opens_external_connection"] is False
    assert len(payload["blocking_reasons"]) == 5
    assert "Prontidao de fechamento da Fase 8 exportada" in capsys.readouterr().out
    assert not settings.database_path.exists()


def test_phase8_closeout_report_cli_exports_markdown_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    readiness_path = tmp_path / "reports" / "prontidao-fechamento-fase-8.json"
    output_path = tmp_path / "reports" / "encerramento-fase-8.md"
    readiness_path.parent.mkdir(parents=True)
    readiness_path.write_text(
        json.dumps(
            {
                "ready_to_close_phase8": True,
                "gates": [{"label": "Gates externos", "passed": True}],
                "blocking_reasons": [],
            },
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(
        [
            "phase8-closeout-report",
            "--closure-readiness",
            str(readiness_path),
            "--output",
            str(output_path),
        ]
    )

    content = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "Fase 8 pronta para encerramento operacional" in content
    assert "- [x] Gates externos" in content
    assert "Relatorio final da Fase 8 exportado" in capsys.readouterr().out
    assert not settings.database_path.exists()


def test_phase8_closeout_package_cli_exports_zip_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    readiness_path = tmp_path / "reports" / "prontidao-fechamento-fase-8.json"
    report_path = tmp_path / "reports" / "encerramento-fase-8.md"
    package_path = tmp_path / "reports" / "pacote-encerramento-fase-8.zip"
    readiness_path.parent.mkdir(parents=True)
    readiness_path.write_text(
        json.dumps({"ready_to_close_phase8": True}),
        encoding="utf-8",
    )
    report_path.write_text(
        "# Encerramento da Fase 8\n\nStatus: **Fase 8 pronta para encerramento operacional**\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(
        [
            "phase8-closeout-package",
            "--closure-readiness",
            str(readiness_path),
            "--closeout-report",
            str(report_path),
            "--output",
            str(package_path),
        ]
    )

    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())

    assert exit_code == 0
    assert "manifesto-encerramento-fase-8.json" in names
    assert "Pacote final da Fase 8 exportado" in capsys.readouterr().out
    assert not settings.database_path.exists()


def test_phase8_finalize_cli_exports_final_artifacts_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    output_dir = tmp_path / "reports" / "fase-8-final"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(["phase8-finalize", "--output-dir", str(output_dir)])

    readiness_path = output_dir / "prontidao-fechamento-fase-8.json"
    report_path = output_dir / "encerramento-fase-8.md"
    package_path = output_dir / "pacote-encerramento-fase-8.zip"
    payload = json.loads(readiness_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["ready_to_close_phase8"] is False
    assert report_path.exists()
    assert package_path.exists()
    assert "Finalizacao da Fase 8 exportada" in capsys.readouterr().out
    assert not settings.database_path.exists()


def test_phase8_finalize_from_dir_cli_exports_final_artifacts_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    input_dir = tmp_path / "reports" / "entrada"
    output_dir = tmp_path / "reports" / "saida"
    input_dir.mkdir(parents=True)

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    exit_code = app.main(
        [
            "phase8-finalize-from-dir",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
        ]
    )

    payload = json.loads(
        (output_dir / "prontidao-fechamento-fase-8.json").read_text(
            encoding="utf-8",
        )
    )

    assert exit_code == 1
    assert payload["ready_to_close_phase8"] is False
    assert (output_dir / "encerramento-fase-8.md").exists()
    assert (output_dir / "pacote-encerramento-fase-8.zip").exists()
    assert "Finalizacao da Fase 8 exportada" in capsys.readouterr().out
    assert not settings.database_path.exists()


def test_postgres_verify_package_cli_exports_safe_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    package_path = tmp_path / "reports" / "pacote-postgresql.zip"
    output_path = tmp_path / "reports" / "verificacao-postgresql.json"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    assert app.main(["postgres-validation-package", "--output", str(package_path)]) == 0
    exit_code = app.main(
        [
            "postgres-verify-package",
            "--package",
            str(package_path),
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ready_for_review"] is True
    assert payload["contains_disallowed_markers"] is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_migration"] is False
    assert "Verificacao de pacote PostgreSQL concluida" in capsys.readouterr().out


def test_postgres_review_summary_cli_exports_safe_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    package_path = tmp_path / "reports" / "pacote-postgresql.zip"
    output_path = tmp_path / "reports" / "resumo-postgresql.md"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    assert app.main(["postgres-validation-package", "--output", str(package_path)]) == 0
    exit_code = app.main(
        [
            "postgres-review-summary",
            "--package",
            str(package_path),
            "--output",
            str(output_path),
        ]
    )

    content = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "Status: **pronto para revisao tecnica**" in content
    assert "- [x] Hashes conferidos" in content
    assert "BACKUP_ENCRYPTION_KEY=" not in content
    assert "Resumo de aceite PostgreSQL exportado" in capsys.readouterr().out


def test_postgres_rehearsal_cli_runs_without_bootstrap_or_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    report_path = tmp_path / "reports" / "homologacao.md"

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)
    monkeypatch.setattr(app, "run_qt_app", lambda settings: pytest.fail("UI nao deve abrir"))

    def fake_rehearsal_admin_action(**kwargs: object) -> SimpleNamespace:
        sqlite_connection = kwargs["sqlite_connection"]
        output_path = kwargs["output_path"]
        assert sqlite_connection.execute("SELECT version FROM schema_version").fetchone()
        assert isinstance(output_path, Path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("# relatorio local\n", encoding="utf-8")
        return SimpleNamespace(output_path=output_path)

    monkeypatch.setattr(
        app,
        "run_postgres_rehearsal_admin_action",
        fake_rehearsal_admin_action,
    )

    exit_code = app.main(
        [
            "postgres-rehearsal",
            "--confirm-disposable-target",
            "--output",
            str(report_path),
        ]
    )

    assert exit_code == 0
    assert report_path.read_text(encoding="utf-8") == "# relatorio local\n"
    assert str(report_path) in capsys.readouterr().out
    with connect(settings.database_path) as connection:
        users_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert users_count == 0


def test_postgres_rehearsal_cli_requires_disposable_target_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path)
    report_path = tmp_path / "reports" / "homologacao.md"
    called = False

    monkeypatch.setattr(app, "load_settings", lambda: settings)
    monkeypatch.setattr(app, "configure_logging", lambda settings: None)

    def fail_if_called(**kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(app, "run_postgres_rehearsal_admin_action", fail_if_called)

    exit_code = app.main(["postgres-rehearsal", "--output", str(report_path)])

    assert exit_code == 1
    assert "confirm-disposable-target" in capsys.readouterr().err
    assert called is False
    assert not report_path.exists()


def _settings(
    tmp_path: Path,
    *,
    asaas_env: str = "sandbox",
    asaas_api_key: str | None = None,
    asaas_enable_write_operations: bool = False,
) -> Settings:
    return Settings(
        app_env="test",
        secret_key="test-secret-value",
        database_url="sqlite:///data/test.sqlite3",
        session_timeout_minutes=30,
        log_level="INFO",
        backup_encryption_key=None,
        backup_auto_daily=False,
        default_admin_username="admin",
        default_admin_password=None,
        asaas_env=asaas_env,
        asaas_api_key=asaas_api_key,
        asaas_enable_write_operations=asaas_enable_write_operations,
        pdv_database_url=None,
        google_client_secret_path=None,
        google_token_path=None,
        paths=AppPaths.from_workspace(tmp_path),
        postgres_rehearsal_database_url=None,
        postgres_rehearsal_enable_execution=False,
    )
