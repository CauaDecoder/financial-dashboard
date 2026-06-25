import json
import zipfile
from pathlib import Path

import pytest

from basilica_financeiro.config import Settings
from basilica_financeiro.database import SCHEMA_VERSION, connect, migrate
from basilica_financeiro.paths import AppPaths
from basilica_financeiro.services.deployment import (
    assess_postgres_schema_compatibility,
    build_migration_rehearsal_plan,
    build_network_readiness_json,
    build_network_rehearsal_package_files,
    build_network_rehearsal_package_verification_json,
    build_network_rehearsal_review_summary_markdown,
    build_phase8_closeout_report_markdown,
    build_phase8_closure_readiness_json,
    build_phase8_local_acceptance_report_markdown,
    build_phase8_local_evidence_package_files,
    build_phase8_local_evidence_package_verification_json,
    build_phase8_local_evidence_review_summary_markdown,
    build_postgres_adapter_contract_json,
    build_postgres_compatibility_report,
    build_postgres_load_plan,
    build_postgres_load_plan_json,
    build_postgres_rehearsal_execution_plan_json,
    build_postgres_rehearsal_package_files,
    build_postgres_rehearsal_package_verification_json,
    build_postgres_rehearsal_preflight_json,
    build_postgres_rehearsal_review_summary_markdown,
    build_postgres_rehearsal_runner_readiness_json,
    build_postgres_schema_blueprint,
    build_schema_inventory_json,
    execute_postgres_rehearsal,
    get_deployment_readiness,
    get_local_database_health,
    get_local_schema_inventory,
    get_postgres_rehearsal_execution_readiness,
    write_network_rehearsal_package,
    write_phase8_closeout_package,
    write_phase8_local_evidence_package,
    write_postgres_rehearsal_package,
)


def test_sqlite_deployment_readiness_preserves_offline_mode(tmp_path: Path) -> None:
    readiness = get_deployment_readiness(_settings(tmp_path))

    assert readiness.database_backend == "sqlite"
    assert readiness.database_location == str(tmp_path / "data" / "test.sqlite3")
    assert readiness.offline_ready is True
    assert readiness.network_ready is False
    assert readiness.postgres_ready is False
    assert "SQLite local" in readiness.warnings[0]


def test_phase8_local_acceptance_report_marks_external_gates_pending(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    report = build_phase8_local_acceptance_report_markdown(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )

    assert "# Aceite local da Fase 8" in report
    assert "Fase 8 ainda nao encerrada" in report
    assert "Validar execucao Asaas Sandbox" in report
    assert "homologacao PostgreSQL descartavel" in report
    assert "BACKUP_ENCRYPTION_KEY=" not in report
    assert "ASAAS_API_KEY=" not in report
    assert "valor_local" not in report


def test_phase8_local_evidence_package_files_are_safe_metadata(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    files = build_phase8_local_evidence_package_files(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )
    manifest = json.loads(files["manifesto-evidencias-fase-8.json"])

    assert set(files) == {
        "README.md",
        "aceite-local-fase-8.md",
        "prontidao-uso-em-rede.json",
        "prontidao-runner-homologacao-postgresql.json",
        "manifesto-evidencias-fase-8.json",
    }
    assert manifest["metadata_only"] is True
    assert manifest["contains_credentials"] is False
    assert manifest["contains_financial_rows"] is False
    assert manifest["opens_external_connection"] is False
    assert manifest["executes_migration"] is False
    assert manifest["phase_complete"] is False
    assert manifest["contains_disallowed_markers"] is False
    assert "Fase 8 ainda nao encerrada" in files["aceite-local-fase-8.md"]


def test_write_phase8_local_evidence_package_includes_hash_manifest(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)
    output_path = tmp_path / "pacote-evidencias-fase-8.zip"

    write_phase8_local_evidence_package(
        output_path=output_path,
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifesto-evidencias-fase-8.json").decode("utf-8"))
        acceptance = archive.read("aceite-local-fase-8.md")

    assert "aceite-local-fase-8.md" in names
    assert "prontidao-uso-em-rede.json" in names
    assert manifest["files"]["aceite-local-fase-8.md"]["bytes"] == len(acceptance)
    assert len(manifest["files"]["aceite-local-fase-8.md"]["sha256"]) == 64


def test_verify_phase8_local_evidence_package_accepts_safe_zip(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)
    output_path = tmp_path / "pacote-evidencias-fase-8.zip"
    write_phase8_local_evidence_package(
        output_path=output_path,
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )

    payload = json.loads(
        build_phase8_local_evidence_package_verification_json(
            package_path=output_path,
        )
    )

    assert payload["ready_for_review"] is True
    assert payload["expected_files_present"] is True
    assert payload["safe_flags_valid"] is True
    assert payload["phase_completion_guard_valid"] is True
    assert payload["hashes_valid"] is True
    assert payload["contains_disallowed_markers"] is False


def test_verify_phase8_local_evidence_package_rejects_tampered_zip(
    tmp_path: Path,
) -> None:
    package_path = tmp_path / "tampered-fase-8.zip"
    with zipfile.ZipFile(package_path, mode="w") as archive:
        archive.writestr(
            "manifesto-evidencias-fase-8.json",
            json.dumps(
                {
                    "metadata_only": True,
                    "contains_financial_rows": False,
                    "contains_credentials": False,
                    "opens_external_connection": False,
                    "executes_migration": False,
                    "phase_complete": True,
                    "files": {},
                },
            ),
        )
        archive.writestr("segredo.txt", "ASAAS_API_KEY=valor_local")

    payload = json.loads(
        build_phase8_local_evidence_package_verification_json(
            package_path=package_path,
        )
    )

    assert payload["ready_for_review"] is False
    assert payload["phase_completion_guard_valid"] is False
    assert payload["contains_disallowed_markers"] is True
    assert "segredo.txt" in payload["unexpected_files"]


def test_phase8_local_evidence_review_summary_is_safe_markdown(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)
    package_path = tmp_path / "pacote-evidencias-fase-8.zip"
    write_phase8_local_evidence_package(
        output_path=package_path,
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )

    content = build_phase8_local_evidence_review_summary_markdown(
        package_path=package_path,
    )

    assert "Status: **pronto para revisao tecnica**" in content
    assert "- [x] Conclusao da fase permanece pendente" in content
    assert "ASAAS_API_KEY=" not in content
    assert "valor_local" not in content


def test_phase8_closure_readiness_blocks_missing_external_evidence() -> None:
    payload = json.loads(
        build_phase8_closure_readiness_json(
            asaas_verification_path=None,
            asaas_summary_path=None,
            postgres_package_verification_path=None,
            postgres_rehearsal_report_path=None,
            phase8_package_verification_path=None,
        )
    )

    assert payload["ready_to_close_phase8"] is False
    assert payload["metadata_only"] is True
    assert payload["opens_external_connection"] is False
    assert len(payload["blocking_reasons"]) == 5


def test_phase8_closure_readiness_accepts_safe_external_evidence(
    tmp_path: Path,
) -> None:
    asaas_verification = tmp_path / "verificacao-asaas.json"
    asaas_summary = tmp_path / "resumo-asaas.md"
    postgres_verification = tmp_path / "verificacao-postgresql.json"
    postgres_report = tmp_path / "relatorio-postgresql.md"
    phase8_verification = tmp_path / "verificacao-fase-8.json"
    safe_verification = {
        "ready_for_review": True,
        "safe_flags_valid": True,
        "hashes_valid": True,
        "contains_disallowed_markers": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "executes_write_operation": False,
    }
    asaas_verification.write_text(json.dumps(safe_verification), encoding="utf-8")
    postgres_verification.write_text(json.dumps(safe_verification), encoding="utf-8")
    phase8_verification.write_text(json.dumps(safe_verification), encoding="utf-8")
    asaas_summary.write_text(
        "# Resumo de aceite do pacote Asaas Sandbox\n\nStatus: pronto\n",
        encoding="utf-8",
    )
    postgres_report.write_text(
        "# Relatorio local de homologacao PostgreSQL\n\n- Status: succeeded\n",
        encoding="utf-8",
    )

    payload = json.loads(
        build_phase8_closure_readiness_json(
            asaas_verification_path=asaas_verification,
            asaas_summary_path=asaas_summary,
            postgres_package_verification_path=postgres_verification,
            postgres_rehearsal_report_path=postgres_report,
            phase8_package_verification_path=phase8_verification,
        )
    )

    assert payload["ready_to_close_phase8"] is True
    assert payload["blocking_reasons"] == []
    assert all(gate["passed"] for gate in payload["gates"])


def test_phase8_closure_readiness_rejects_sensitive_markers(
    tmp_path: Path,
) -> None:
    asaas_verification = tmp_path / "verificacao-asaas.json"
    asaas_verification.write_text("ASAAS_API_KEY=valor_local", encoding="utf-8")

    payload = json.loads(
        build_phase8_closure_readiness_json(
            asaas_verification_path=asaas_verification,
            asaas_summary_path=None,
            postgres_package_verification_path=None,
            postgres_rehearsal_report_path=None,
            phase8_package_verification_path=None,
        )
    )

    assert payload["ready_to_close_phase8"] is False
    assert payload["gates"][0]["contains_disallowed_markers"] is True
    assert "marcadores sensiveis" in payload["gates"][0]["message"]


def test_phase8_closeout_report_marks_ready_gate_as_closable(
    tmp_path: Path,
) -> None:
    readiness_path = tmp_path / "prontidao-fechamento-fase-8.json"
    readiness_path.write_text(
        json.dumps(
            {
                "ready_to_close_phase8": True,
                "gates": [{"label": "Sandbox Asaas", "passed": True}],
                "blocking_reasons": [],
            },
        ),
        encoding="utf-8",
    )

    content = build_phase8_closeout_report_markdown(
        closure_readiness_path=readiness_path,
    )

    assert "Fase 8 pronta para encerramento operacional" in content
    assert "- [x] Sandbox Asaas" in content
    assert "Fase 8 pode ser encerrada" in content


def test_phase8_closeout_report_keeps_blocked_gate_pending(
    tmp_path: Path,
) -> None:
    readiness_path = tmp_path / "prontidao-fechamento-fase-8.json"
    readiness_path.write_text(
        json.dumps(
            {
                "ready_to_close_phase8": False,
                "gates": [{"label": "PostgreSQL descartavel", "passed": False}],
                "blocking_reasons": ["PostgreSQL descartavel pendente."],
            },
        ),
        encoding="utf-8",
    )

    content = build_phase8_closeout_report_markdown(
        closure_readiness_path=readiness_path,
    )

    assert "Fase 8 ainda pendente" in content
    assert "- [ ] PostgreSQL descartavel" in content
    assert "PostgreSQL descartavel pendente" in content


def test_write_phase8_closeout_package_includes_final_manifest(
    tmp_path: Path,
) -> None:
    readiness_path = tmp_path / "prontidao-fechamento-fase-8.json"
    report_path = tmp_path / "encerramento-fase-8.md"
    package_path = tmp_path / "pacote-encerramento-fase-8.zip"
    readiness_path.write_text(
        json.dumps({"ready_to_close_phase8": True}),
        encoding="utf-8",
    )
    report_path.write_text(
        "# Encerramento da Fase 8\n\nStatus: **Fase 8 pronta para encerramento operacional**\n",
        encoding="utf-8",
    )

    write_phase8_closeout_package(
        closure_readiness_path=readiness_path,
        closeout_report_path=report_path,
        output_path=package_path,
    )

    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifesto-encerramento-fase-8.json").decode("utf-8"))

    assert names == {
        "prontidao-fechamento-fase-8.json",
        "encerramento-fase-8.md",
        "manifesto-encerramento-fase-8.json",
    }
    assert manifest["ready_to_close_phase8"] is True
    assert manifest["contains_credentials"] is False
    assert manifest["contains_disallowed_markers"] is False


def test_postgres_deployment_readiness_masks_credentials(tmp_path: Path) -> None:
    readiness = get_deployment_readiness(
        _settings(
            tmp_path,
            database_url="postgresql://financeiro:valor_local@localhost:5432/basilica",
        )
    )

    assert readiness.database_backend == "postgresql"
    assert readiness.database_location == "postgresql://financeiro:***@localhost:5432/basilica"
    assert "valor_local" not in readiness.database_location
    assert readiness.network_ready is True
    assert readiness.postgres_ready is False


def test_unknown_deployment_backend_is_not_ready(tmp_path: Path) -> None:
    readiness = get_deployment_readiness(_settings(tmp_path, database_url="mysql://localhost/db"))

    assert readiness.database_backend == "desconhecido"
    assert readiness.offline_ready is False
    assert readiness.network_ready is False
    assert readiness.postgres_ready is False


def test_network_readiness_blocks_sqlite_multi_installation(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)

    payload = json.loads(
        build_network_readiness_json(
            settings=settings,
            readiness=readiness,
            health=health,
        )
    )
    checks = {check["code"]: check for check in payload["checks"]}

    assert payload["metadata_only"] is True
    assert payload["contains_financial_rows"] is False
    assert payload["contains_credentials"] is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_migration"] is False
    assert payload["ready_for_network_use"] is False
    assert checks["sqlite_multiwriter_guard"]["status"] == "blocked"
    assert checks["sqlite_origin_health"]["status"] == "ok"


def test_network_readiness_masks_postgres_location(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path,
        database_url="postgresql://financeiro:valor_local@localhost:5432/basilica",
    )
    readiness = get_deployment_readiness(settings)

    payload_text = build_network_readiness_json(
        settings=settings,
        readiness=readiness,
        health=None,
    )
    payload = json.loads(payload_text)

    assert payload["database_location"] == "postgresql://financeiro:***@localhost:5432/basilica"
    assert payload["ready_for_network_use"] is False
    assert payload["contains_credentials"] is False
    assert "valor_local" not in payload_text


def test_network_rehearsal_package_files_are_safe_metadata(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)

    files = build_network_rehearsal_package_files(
        settings=settings,
        readiness=readiness,
        health=health,
    )
    readiness_payload = json.loads(files["prontidao-uso-em-rede.json"])
    manifest = json.loads(files["manifesto-homologacao-rede.json"])

    assert set(files) == {
        "README.md",
        "prontidao-uso-em-rede.json",
        "checklist-homologacao-rede.md",
        "manifesto-homologacao-rede.json",
    }
    assert readiness_payload["contains_credentials"] is False
    assert readiness_payload["contains_financial_rows"] is False
    assert readiness_payload["ready_for_network_use"] is False
    assert manifest["contains_credentials"] is False
    assert manifest["opens_external_connection"] is False
    assert "sqlite_multiwriter_guard" in files["prontidao-uso-em-rede.json"]
    assert "SQLite nao sera compartilhado" in files["checklist-homologacao-rede.md"]


def test_write_network_rehearsal_package_includes_hash_manifest(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
    output_path = tmp_path / "homologacao-rede.zip"

    write_network_rehearsal_package(
        output_path=output_path,
        settings=settings,
        readiness=readiness,
        health=health,
    )

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifesto-homologacao-rede.json").decode("utf-8"))
        readiness_bytes = archive.read("prontidao-uso-em-rede.json")

    assert names == {
        "README.md",
        "prontidao-uso-em-rede.json",
        "checklist-homologacao-rede.md",
        "manifesto-homologacao-rede.json",
    }
    assert manifest["files"]["prontidao-uso-em-rede.json"]["bytes"] == len(readiness_bytes)
    assert len(manifest["files"]["prontidao-uso-em-rede.json"]["sha256"]) == 64


def test_verify_network_rehearsal_package_accepts_safe_zip(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
    output_path = tmp_path / "homologacao-rede.zip"
    write_network_rehearsal_package(
        output_path=output_path,
        settings=settings,
        readiness=readiness,
        health=health,
    )

    payload = json.loads(
        build_network_rehearsal_package_verification_json(
            package_path=output_path,
        )
    )

    assert payload["ready_for_review"] is True
    assert payload["expected_files_present"] is True
    assert payload["manifest_present"] is True
    assert payload["safe_flags_valid"] is True
    assert payload["hashes_valid"] is True
    assert payload["contains_disallowed_markers"] is False


def test_verify_network_rehearsal_package_rejects_tampered_zip(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
    output_path = tmp_path / "homologacao-rede.zip"
    write_network_rehearsal_package(
        output_path=output_path,
        settings=settings,
        readiness=readiness,
        health=health,
    )
    with zipfile.ZipFile(output_path, mode="a") as archive:
        archive.writestr("segredo.txt", "BACKUP_ENCRYPTION_KEY=valor_local")

    payload = json.loads(
        build_network_rehearsal_package_verification_json(
            package_path=output_path,
        )
    )

    assert payload["ready_for_review"] is False
    assert payload["expected_files_present"] is False
    assert payload["unexpected_files"] == ["segredo.txt"]
    assert payload["contains_disallowed_markers"] is True


def test_network_rehearsal_review_summary_uses_local_gates(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
    output_path = tmp_path / "homologacao-rede.zip"
    write_network_rehearsal_package(
        output_path=output_path,
        settings=settings,
        readiness=readiness,
        health=health,
    )

    content = build_network_rehearsal_review_summary_markdown(
        package_path=output_path,
    )

    assert "# Resumo de aceite do pacote de rede" in content
    assert "Status: **pronto para revisao tecnica**" in content
    assert "- [x] Hashes conferidos" in content
    assert "BACKUP_ENCRYPTION_KEY=" not in content
    assert "valor_local" not in content


def test_local_database_health_is_ready_after_migration(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        health = get_local_database_health(connection)

    assert health.schema_version == SCHEMA_VERSION
    assert health.expected_schema_version == SCHEMA_VERSION
    assert health.quick_check_ok is True
    assert health.foreign_key_violations == 0
    assert health.wal_enabled is True
    assert health.ready_for_migration_rehearsal is True
    assert "audit_log" in health.critical_table_counts


def test_local_database_health_blocks_migration_rehearsal_for_old_schema(
    tmp_path: Path,
) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        connection.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION - 1,))

        health = get_local_database_health(connection)

    assert health.schema_version == SCHEMA_VERSION - 1
    assert health.ready_for_migration_rehearsal is False


def test_build_migration_rehearsal_plan_uses_local_preflight(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)

    plan = build_migration_rehearsal_plan(
        settings=settings,
        readiness=readiness,
        health=health,
    )

    assert "# Roteiro de ensaio de migracao" in plan
    assert "Status do preflight: pronto para ensaio local" in plan
    assert f"Schema: {SCHEMA_VERSION}/{SCHEMA_VERSION}" in plan
    assert "- audit_log: 0" in plan
    assert "DATABASE_URL" in plan


def test_build_migration_rehearsal_plan_masks_postgres_url(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path,
        database_url="postgresql://financeiro:valor_local@localhost:5432/basilica",
    )
    readiness = get_deployment_readiness(settings)

    plan = build_migration_rehearsal_plan(
        settings=settings,
        readiness=readiness,
        health=None,
    )

    assert "postgresql://financeiro:***@localhost:5432/basilica" in plan
    assert "valor_local" not in plan


def test_get_local_schema_inventory_exports_metadata_only(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        inventory = get_local_schema_inventory(connection)

    table_names = {table["name"] for table in inventory["tables"]}
    assert "financial_transactions" in table_names
    transaction_table = next(
        table for table in inventory["tables"] if table["name"] == "financial_transactions"
    )
    amount_column = next(
        column for column in transaction_table["columns"] if column["name"] == "amount_cents"
    )
    assert amount_column["type"] == "INTEGER"
    assert "rows" not in transaction_table
    assert all("columns" in index for index in transaction_table["indexes"])


def test_build_schema_inventory_json_is_metadata_only(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    payload = json.loads(
        build_schema_inventory_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )

    assert payload["metadata_only"] is True
    assert payload["contains_financial_rows"] is False
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "financial_transactions" in {table["name"] for table in payload["tables"]}
    assert "critical_table_counts" in payload


def test_postgres_compatibility_report_accepts_current_schema(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    report = assess_postgres_schema_compatibility(health=health, inventory=inventory)
    markdown = build_postgres_compatibility_report(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )

    assert report.ready_for_rehearsal is True
    assert all(finding.severity == "warning" for finding in report.findings)
    assert "Pronto para ensaio: sim" in markdown
    assert "Nao contem linhas financeiras" in markdown


def test_postgres_compatibility_report_blocks_non_integer_money(
    tmp_path: Path,
) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)
    transaction_table = next(
        table for table in inventory["tables"] if table["name"] == "financial_transactions"
    )
    amount_column = next(
        column for column in transaction_table["columns"] if column["name"] == "amount_cents"
    )
    amount_column["type"] = "TEXT"

    report = assess_postgres_schema_compatibility(health=health, inventory=inventory)

    assert report.ready_for_rehearsal is False
    assert report.findings[0].severity == "error"
    assert report.findings[0].location == "financial_transactions.amount_cents"


def test_postgres_schema_blueprint_is_metadata_only(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    blueprint = build_postgres_schema_blueprint(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )

    assert "-- Nao contem dados financeiros" in blueprint
    assert 'CREATE TABLE IF NOT EXISTS "financial_transactions"' in blueprint
    assert '"amount_cents" BIGINT NOT NULL' in blueprint
    assert "FOREIGN KEY" in blueprint
    assert "INSERT INTO" not in blueprint


def test_postgres_schema_blueprint_includes_index_columns(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_test_transactions_effective_date "
            "ON financial_transactions(effective_date)"
        )
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    blueprint = build_postgres_schema_blueprint(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )

    assert (
        'CREATE INDEX IF NOT EXISTS "idx_test_transactions_effective_date" '
        'ON "financial_transactions" ("effective_date");'
    ) in blueprint


def test_postgres_load_plan_orders_tables_by_foreign_keys(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
    inventory = {
        "tables": [
            _inventory_table("children", foreign_table="parents"),
            _inventory_table("parents"),
        ]
    }

    load_plan = build_postgres_load_plan(health=health, inventory=inventory)
    payload = json.loads(
        build_postgres_load_plan_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )

    assert [step.table_name for step in load_plan.steps] == ["parents", "children"]
    assert load_plan.ready_for_load_rehearsal is True
    assert payload["steps"][1]["depends_on"] == ["parents"]
    assert payload["contains_financial_rows"] is False


def test_postgres_load_plan_blocks_cycles(tmp_path: Path) -> None:
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
    inventory = {
        "tables": [
            _inventory_table("a", foreign_table="b"),
            _inventory_table("b", foreign_table="a"),
        ]
    }

    load_plan = build_postgres_load_plan(health=health, inventory=inventory)

    assert load_plan.ready_for_load_rehearsal is False
    assert load_plan.steps == []
    assert load_plan.unresolved_tables == ["a", "b"]


def test_postgres_adapter_contract_describes_table_strategy(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    payload = json.loads(
        build_postgres_adapter_contract_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )
    transaction_table = next(
        table for table in payload["tables"] if table["table"] == "financial_transactions"
    )
    amount_column = next(
        column for column in transaction_table["columns"] if column["name"] == "amount_cents"
    )

    assert payload["metadata_only"] is True
    assert payload["executes_migration"] is False
    assert transaction_table["insert_strategy"] == "preserve_primary_keys_then_reset_identity"
    assert amount_column["postgres_type"] == "BIGINT"
    assert any(check["table"] == "financial_transactions" for check in payload["post_load_checks"])
    assert "INSERT INTO" not in json.dumps(payload)


def test_postgres_rehearsal_execution_plan_is_parameterized(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    payload = json.loads(
        build_postgres_rehearsal_execution_plan_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )
    load_phase = next(phase for phase in payload["phases"] if phase["name"] == "load")
    transaction_operation = next(
        operation
        for operation in load_phase["operations"]
        if operation["table"] == "financial_transactions"
    )

    assert payload["metadata_only"] is True
    assert payload["executes_migration"] is False
    assert transaction_operation["operation"] == "insert_rows"
    assert transaction_operation["uses_parameter_binding"] is True
    assert ":amount_cents" in transaction_operation["parameters"]
    assert "INSERT INTO" not in json.dumps(payload)


def test_postgres_rehearsal_preflight_is_offline_and_ready_for_review(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    payload = json.loads(
        build_postgres_rehearsal_preflight_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )
    checks = {check["code"]: check for check in payload["checks"]}

    assert payload["metadata_only"] is True
    assert payload["contains_financial_rows"] is False
    assert payload["contains_credentials"] is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_migration"] is False
    assert payload["runner_mode"] == "offline_preflight_only"
    assert payload["ready_to_run"] is True
    assert checks["sqlite_health"]["status"] == "ok"
    assert checks["execution_plan_guard"]["status"] == "ok"
    assert checks["target_database_guard"]["status"] == "warning"


def test_postgres_rehearsal_preflight_masks_target_url(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    payload = json.loads(
        build_postgres_rehearsal_preflight_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
            target_database_url=("postgresql://financeiro:valor_local@localhost:5432/basilica_hml"),
        )
    )

    assert payload["target_database_configured"] is True
    assert (
        payload["target_database_location"]
        == "postgresql://financeiro:***@localhost:5432/basilica_hml"
    )
    assert "valor_local" not in json.dumps(payload)


def test_postgres_rehearsal_runner_readiness_blocks_by_default(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    execution_readiness = get_postgres_rehearsal_execution_readiness(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )
    payload = json.loads(
        build_postgres_rehearsal_runner_readiness_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )

    assert execution_readiness.ready is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_migration"] is False
    assert payload["execution_enabled"] is False
    assert payload["ready_for_opt_in_runner"] is False
    assert "POSTGRES_REHEARSAL_ENABLE_EXECUTION" in " ".join(payload["reasons"])


def test_postgres_rehearsal_runner_readiness_masks_target_url(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path,
        postgres_rehearsal_database_url=(
            "postgresql://financeiro:valor_local@localhost:5432/basilica_hml"
        ),
    )
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    payload = json.loads(
        build_postgres_rehearsal_runner_readiness_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )

    assert (
        payload["target_database_location"]
        == "postgresql://financeiro:***@localhost:5432/basilica_hml"
    )
    assert "valor_local" not in json.dumps(payload)


def test_postgres_rehearsal_runner_readiness_blocks_without_driver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "basilica_financeiro.services.deployment._postgres_driver_available",
        lambda: False,
    )
    settings = _settings(
        tmp_path,
        postgres_rehearsal_database_url=(
            "postgresql://financeiro:valor_local@localhost:5432/basilica_hml"
        ),
        postgres_rehearsal_enable_execution=True,
    )
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    payload = json.loads(
        build_postgres_rehearsal_runner_readiness_json(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
        )
    )

    assert payload["postgresql_driver_available"] is False
    assert payload["ready_for_opt_in_runner"] is False
    assert "psycopg" in " ".join(payload["reasons"])
    assert "valor_local" not in json.dumps(payload)


def test_execute_postgres_rehearsal_uses_injected_transport_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "basilica_financeiro.services.deployment._postgres_driver_available",
        lambda: True,
    )
    settings = _settings(
        tmp_path,
        postgres_rehearsal_database_url=(
            "postgresql://financeiro:valor_local@localhost:5432/basilica_hml"
        ),
        postgres_rehearsal_enable_execution=True,
    )
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)
    calls: list[dict[str, object]] = []

    def transport(
        *,
        target_database_url: str,
        execution_plan: dict[str, object],
        timeout_seconds: int,
    ) -> dict[str, object]:
        calls.append(
            {
                "target_database_url": target_database_url,
                "opens_external_connection": execution_plan["opens_external_connection"],
                "executes_migration": execution_plan["executes_migration"],
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"status": "succeeded", "executed_steps": 5}

    result = execute_postgres_rehearsal(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
        transport=transport,
    )

    assert result.status == "succeeded"
    assert result.executed_steps == 5
    assert result.target_database_location == (
        "postgresql://financeiro:***@localhost:5432/basilica_hml"
    )
    assert calls == [
        {
            "target_database_url": (
                "postgresql://financeiro:valor_local@localhost:5432/basilica_hml"
            ),
            "opens_external_connection": False,
            "executes_migration": False,
            "timeout_seconds": 60,
        }
    ]


def test_postgres_rehearsal_package_files_are_safe_metadata(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

    files = build_postgres_rehearsal_package_files(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )
    manifest = json.loads(files["manifesto-homologacao.json"])

    assert set(files) == {
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
    assert manifest["metadata_only"] is True
    assert manifest["contains_financial_rows"] is False
    assert manifest["contains_credentials"] is False
    assert manifest["opens_external_connection"] is False
    assert manifest["executes_migration"] is False
    assert "INSERT INTO" not in files["blueprint-postgresql.sql"]
    assert "valor_local" not in "\n".join(files.values())


def test_write_postgres_rehearsal_package_includes_hash_manifest(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)
    output_path = tmp_path / "homologacao-postgresql.zip"

    write_postgres_rehearsal_package(
        output_path=output_path,
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )

    with zipfile.ZipFile(output_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifesto-homologacao.json").decode("utf-8"))
        blueprint = archive.read("blueprint-postgresql.sql")

    assert "blueprint-postgresql.sql" in names
    assert "plano-carga-postgresql.json" in names
    assert "contrato-adapter-postgresql.json" in names
    assert "plano-execucao-homologacao-postgresql.json" in names
    assert "preflight-runner-homologacao-postgresql.json" in names
    assert "prontidao-runner-homologacao-postgresql.json" in names
    assert "manifesto-homologacao.json" in names
    assert manifest["files"]["blueprint-postgresql.sql"]["bytes"] == len(blueprint)
    assert len(manifest["files"]["blueprint-postgresql.sql"]["sha256"]) == 64


def test_verify_postgres_rehearsal_package_accepts_safe_zip(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)
    output_path = tmp_path / "homologacao-postgresql.zip"
    write_postgres_rehearsal_package(
        output_path=output_path,
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )

    payload = json.loads(
        build_postgres_rehearsal_package_verification_json(
            package_path=output_path,
        )
    )

    assert payload["ready_for_review"] is True
    assert payload["expected_files_present"] is True
    assert payload["safe_flags_valid"] is True
    assert payload["hashes_valid"] is True
    assert payload["contains_disallowed_markers"] is False
    assert payload["opens_external_connection"] is False
    assert payload["executes_migration"] is False


def test_verify_postgres_rehearsal_package_rejects_tampered_zip(tmp_path: Path) -> None:
    package_path = tmp_path / "tampered-postgresql.zip"
    with zipfile.ZipFile(package_path, mode="w") as archive:
        archive.writestr(
            "manifesto-homologacao.json",
            json.dumps(
                {
                    "metadata_only": True,
                    "contains_financial_rows": False,
                    "contains_credentials": False,
                    "opens_external_connection": False,
                    "executes_migration": False,
                    "files": {},
                },
            ),
        )
        archive.writestr("segredo.txt", "BACKUP_ENCRYPTION_KEY=valor_local")

    payload = json.loads(
        build_postgres_rehearsal_package_verification_json(
            package_path=package_path,
        )
    )

    assert payload["ready_for_review"] is False
    assert payload["expected_files_present"] is False
    assert payload["contains_disallowed_markers"] is True
    assert "segredo.txt" in payload["unexpected_files"]


def test_postgres_rehearsal_review_summary_is_safe_markdown(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)
    package_path = tmp_path / "homologacao-postgresql.zip"
    write_postgres_rehearsal_package(
        output_path=package_path,
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
    )

    content = build_postgres_rehearsal_review_summary_markdown(
        package_path=package_path,
    )

    assert "Status: **pronto para revisao tecnica**" in content
    assert "- [x] Hashes conferidos" in content
    assert "BACKUP_ENCRYPTION_KEY=" not in content
    assert "valor_local" not in content


def _inventory_table(table_name: str, *, foreign_table: str | None = None) -> dict[str, object]:
    foreign_keys = (
        [
            {
                "id": 0,
                "seq": 0,
                "table": foreign_table,
                "from": "parent_id",
                "to": "id",
                "on_update": "NO ACTION",
                "on_delete": "NO ACTION",
            }
        ]
        if foreign_table is not None
        else []
    )
    return {
        "name": table_name,
        "columns": [
            {
                "name": "id",
                "type": "INTEGER",
                "not_null": True,
                "default": None,
                "primary_key_position": 1,
            }
        ],
        "foreign_keys": foreign_keys,
        "indexes": [],
    }


def _settings(
    tmp_path: Path,
    *,
    database_url: str = "sqlite:///data/test.sqlite3",
    postgres_rehearsal_database_url: str | None = None,
    postgres_rehearsal_enable_execution: bool = False,
) -> Settings:
    return Settings(
        app_env="test",
        secret_key="test-secret-value",
        database_url=database_url,
        session_timeout_minutes=30,
        log_level="INFO",
        backup_encryption_key=None,
        backup_auto_daily=True,
        default_admin_username="admin",
        default_admin_password="SenhaForte123!",
        asaas_env="sandbox",
        asaas_api_key=None,
        asaas_enable_write_operations=False,
        pdv_database_url=None,
        google_client_secret_path=None,
        google_token_path=None,
        paths=AppPaths.from_workspace(tmp_path),
        postgres_rehearsal_database_url=postgres_rehearsal_database_url,
        postgres_rehearsal_enable_execution=postgres_rehearsal_enable_execution,
    )
