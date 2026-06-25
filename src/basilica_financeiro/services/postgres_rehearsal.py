from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from basilica_financeiro.config import Settings
from basilica_financeiro.services.deployment import (
    DeploymentReadiness,
    LocalDatabaseHealth,
    build_postgres_rehearsal_execution_plan_json,
    build_postgres_schema_blueprint,
    get_deployment_readiness,
    get_local_database_health,
    get_local_schema_inventory,
    get_postgres_rehearsal_execution_readiness,
)


class PostgresRehearsalTarget(Protocol):
    def ensure_empty(self, table_names: list[str]) -> None:
        pass

    def apply_blueprint(self, blueprint_sql: str) -> None:
        pass

    def insert_rows(
        self,
        *,
        table_name: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> None:
        pass

    def reset_identity(self, *, table_name: str, primary_keys: list[str]) -> None:
        pass

    def count_rows(self, table_name: str) -> int:
        pass


class PostgresRehearsalEngineFactory(Protocol):
    def __call__(self, database_url: str) -> Engine:
        pass


class SqlAlchemyPostgresRehearsalTarget:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def ensure_empty(self, table_names: list[str]) -> None:
        non_empty_tables = [
            table_name for table_name in table_names if self.count_rows(table_name) > 0
        ]
        if non_empty_tables:
            raise ValueError(
                "Banco alvo de homologacao precisa estar vazio: " + ", ".join(non_empty_tables)
            )

    def apply_blueprint(self, blueprint_sql: str) -> None:
        for statement in _split_sql_statements(blueprint_sql):
            self._connection.execute(text(statement))

    def insert_rows(
        self,
        *,
        table_name: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> None:
        if not rows:
            return
        statement = text(
            f"INSERT INTO {_quote_postgres_identifier(table_name)} "  # noqa: S608
            f"({_postgres_identifier_list(columns)}) "
            f"VALUES ({_postgres_parameter_list(columns)})"
        )
        self._connection.execute(statement, rows)

    def reset_identity(self, *, table_name: str, primary_keys: list[str]) -> None:
        if not primary_keys:
            return
        primary_key = primary_keys[0]
        statement_sql = (
            "SELECT setval("  # noqa: S608
            "pg_get_serial_sequence(:table_name, :primary_key), "
            f"COALESCE((SELECT MAX({_quote_postgres_identifier(primary_key)}) "
            f"FROM {_quote_postgres_identifier(table_name)}), 1), "
            f"EXISTS(SELECT 1 FROM {_quote_postgres_identifier(table_name)})"
            ")"
        )
        statement = text(statement_sql)
        self._connection.execute(
            statement,
            {"table_name": table_name, "primary_key": primary_key},
        )

    def count_rows(self, table_name: str) -> int:
        result = self._connection.execute(
            text(f"SELECT COUNT(*) FROM {_quote_postgres_identifier(table_name)}")  # noqa: S608
        )
        return int(result.scalar_one())


@dataclass(frozen=True)
class PostgresRehearsalRunResult:
    status: str
    loaded_tables: list[str]
    validated_tables: list[str]
    inserted_rows: int
    executed_steps: int


@dataclass(frozen=True)
class PostgresSqlAlchemyRehearsalResult:
    status: str
    target_database_location: str
    loaded_tables: list[str]
    validated_tables: list[str]
    inserted_rows: int
    executed_steps: int


@dataclass(frozen=True)
class PostgresRehearsalAdminReport:
    output_path: Path
    result: PostgresSqlAlchemyRehearsalResult


def _create_rehearsal_engine(database_url: str) -> Engine:
    return create_engine(database_url)


def run_postgres_rehearsal_admin_action(
    *,
    settings: Settings,
    sqlite_connection: sqlite3.Connection,
    output_path: Path,
    engine_factory: PostgresRehearsalEngineFactory = _create_rehearsal_engine,
) -> PostgresRehearsalAdminReport:
    readiness = get_deployment_readiness(settings)
    health = get_local_database_health(sqlite_connection)
    inventory = get_local_schema_inventory(sqlite_connection)
    result = execute_postgres_rehearsal_with_sqlalchemy(
        settings=settings,
        readiness=readiness,
        health=health,
        inventory=inventory,
        sqlite_connection=sqlite_connection,
        engine_factory=engine_factory,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _postgres_rehearsal_admin_report_markdown(
            settings=settings,
            readiness=readiness,
            health=health,
            result=result,
        ),
        encoding="utf-8",
    )
    return PostgresRehearsalAdminReport(output_path=output_path, result=result)


def execute_postgres_rehearsal_with_sqlalchemy(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    inventory: dict[str, Any],
    sqlite_connection: sqlite3.Connection,
    engine_factory: PostgresRehearsalEngineFactory = _create_rehearsal_engine,
) -> PostgresSqlAlchemyRehearsalResult:
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

    engine = engine_factory(settings.postgres_rehearsal_database_url)
    with engine.begin() as connection:
        result = run_postgres_rehearsal_from_sqlite(
            sqlite_connection=sqlite_connection,
            target=SqlAlchemyPostgresRehearsalTarget(connection),
            blueprint_sql=build_postgres_schema_blueprint(
                settings=settings,
                readiness=readiness,
                health=health,
                inventory=inventory,
            ),
            execution_plan=_json_payload(
                build_postgres_rehearsal_execution_plan_json(
                    settings=settings,
                    readiness=readiness,
                    health=health,
                    inventory=inventory,
                )
            ),
        )
    return PostgresSqlAlchemyRehearsalResult(
        status=result.status,
        target_database_location=execution_readiness.target_database_location or "",
        loaded_tables=result.loaded_tables,
        validated_tables=result.validated_tables,
        inserted_rows=result.inserted_rows,
        executed_steps=result.executed_steps,
    )


def _postgres_rehearsal_admin_report_markdown(
    *,
    settings: Settings,
    readiness: DeploymentReadiness,
    health: LocalDatabaseHealth,
    result: PostgresSqlAlchemyRehearsalResult,
) -> str:
    loaded_tables = [f"- {table_name}" for table_name in result.loaded_tables] or [
        "- Nenhuma tabela carregada."
    ]
    validated_tables = [f"- {table_name}" for table_name in result.validated_tables] or [
        "- Nenhuma tabela validada."
    ]
    return "\n".join(
        [
            "# Relatorio local de homologacao PostgreSQL",
            "",
            "## Escopo",
            "",
            "- Acao administrativa opt-in para ambiente descartavel.",
            "- Nao contem linhas financeiras, usuarios, documentos ou auditoria.",
            "- Nao contem credenciais, tokens, senhas ou URL sem mascara.",
            "- O banco operacional permanece separado da homologacao.",
            "",
            "## Origem",
            "",
            f"- Ambiente: {settings.app_env}",
            f"- Backend operacional: {readiness.database_backend}",
            f"- Origem mascarada: {readiness.database_location}",
            f"- Schema: {health.schema_version}/{health.expected_schema_version}",
            "",
            "## Destino",
            "",
            f"- URL mascarada: {result.target_database_location}",
            "",
            "## Resultado",
            "",
            f"- Status: {result.status}",
            f"- Linhas carregadas: {result.inserted_rows}",
            f"- Passos executados: {result.executed_steps}",
            "",
            "## Tabelas carregadas",
            "",
            *loaded_tables,
            "",
            "## Tabelas validadas",
            "",
            *validated_tables,
            "",
        ]
    )


def run_postgres_rehearsal_from_sqlite(
    *,
    sqlite_connection: sqlite3.Connection,
    target: PostgresRehearsalTarget,
    blueprint_sql: str,
    execution_plan: dict[str, Any],
) -> PostgresRehearsalRunResult:
    _validate_execution_plan(execution_plan)
    load_operations = _phase_operations(execution_plan, "load")
    validation_operations = _phase_operations(execution_plan, "validation")

    target.ensure_empty([str(operation["table"]) for operation in load_operations])
    target.apply_blueprint(blueprint_sql)

    loaded_tables: list[str] = []
    inserted_rows = 0
    for operation in load_operations:
        table_name = str(operation["table"])
        columns = [str(column) for column in operation["columns"]]
        rows = _read_sqlite_rows(sqlite_connection, table_name=table_name, columns=columns)
        target.insert_rows(table_name=table_name, columns=columns, rows=rows)
        loaded_tables.append(table_name)
        inserted_rows += len(rows)

    for operation in _phase_operations(execution_plan, "identity"):
        target.reset_identity(
            table_name=str(operation["table"]),
            primary_keys=[str(primary_key) for primary_key in operation["primary_keys"]],
        )

    validated_tables: list[str] = []
    for operation in validation_operations:
        table_name = str(operation["table"])
        expected_count = int(operation["source_count"])
        actual_count = target.count_rows(table_name)
        if actual_count != expected_count:
            raise ValueError(
                f"Contagem divergente em {table_name}: "
                f"esperado {expected_count}, obtido {actual_count}"
            )
        validated_tables.append(table_name)

    return PostgresRehearsalRunResult(
        status="succeeded",
        loaded_tables=loaded_tables,
        validated_tables=validated_tables,
        inserted_rows=inserted_rows,
        executed_steps=(
            2
            + len(load_operations)
            + len(_phase_operations(execution_plan, "identity"))
            + len(validation_operations)
        ),
    )


def _validate_execution_plan(execution_plan: dict[str, Any]) -> None:
    if not execution_plan.get("ready_for_execution_rehearsal"):
        raise ValueError("Plano de execucao ainda nao esta pronto para homologacao")
    if execution_plan.get("contains_credentials"):
        raise ValueError("Plano de execucao nao pode conter credenciais")
    if not execution_plan.get("metadata_only"):
        raise ValueError("Plano de execucao precisa ser derivado de metadados")
    if execution_plan.get("opens_external_connection") or execution_plan.get("executes_migration"):
        raise ValueError("Plano de execucao nao pode abrir conexao nem migrar sozinho")
    for operation in _phase_operations(execution_plan, "load"):
        if not operation.get("uses_parameter_binding"):
            raise ValueError("Carga PostgreSQL exige parametros nomeados")


def _json_payload(content: str) -> dict[str, Any]:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("Payload JSON de homologacao invalido")
    return payload


def _phase_operations(execution_plan: dict[str, Any], phase_name: str) -> list[dict[str, Any]]:
    phases = execution_plan.get("phases")
    if not isinstance(phases, list):
        raise ValueError("Plano de execucao invalido: fases ausentes")
    phase = next(
        (
            candidate
            for candidate in phases
            if isinstance(candidate, dict) and candidate.get("name") == phase_name
        ),
        None,
    )
    if not isinstance(phase, dict) or not isinstance(phase.get("operations"), list):
        raise ValueError(f"Plano de execucao invalido: fase {phase_name} ausente")
    return [operation for operation in phase["operations"] if isinstance(operation, dict)]


def _read_sqlite_rows(
    sqlite_connection: sqlite3.Connection,
    *,
    table_name: str,
    columns: list[str],
) -> list[dict[str, Any]]:
    query = f"SELECT {_sqlite_identifier_list(columns)} FROM {_quote_sqlite_identifier(table_name)}"  # noqa: S608
    rows = sqlite_connection.execute(query).fetchall()
    return [{column: row[column] for column in columns} for row in rows]


def _sqlite_identifier_list(identifiers: list[str]) -> str:
    return ", ".join(_quote_sqlite_identifier(identifier) for identifier in identifiers)


def _quote_sqlite_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def _split_sql_statements(sql: str) -> list[str]:
    uncommented = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    return [statement.strip() for statement in uncommented.split(";") if statement.strip()]


def _postgres_identifier_list(identifiers: list[str]) -> str:
    return ", ".join(_quote_postgres_identifier(identifier) for identifier in identifiers)


def _postgres_parameter_list(identifiers: list[str]) -> str:
    return ", ".join(f":{identifier}" for identifier in identifiers)


def _quote_postgres_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'
