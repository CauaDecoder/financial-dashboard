import sqlite3
from pathlib import Path
from typing import Any

import pytest

from basilica_financeiro.config import Settings
from basilica_financeiro.database import connect, migrate
from basilica_financeiro.paths import AppPaths
from basilica_financeiro.services.deployment import (
    get_deployment_readiness,
    get_local_database_health,
    get_local_schema_inventory,
)
from basilica_financeiro.services.postgres_rehearsal import (
    SqlAlchemyPostgresRehearsalTarget,
    execute_postgres_rehearsal_with_sqlalchemy,
    run_postgres_rehearsal_admin_action,
    run_postgres_rehearsal_from_sqlite,
)


class RecordingTarget:
    def __init__(self) -> None:
        self.empty_checked: list[str] = []
        self.blueprint_sql: str | None = None
        self.rows_by_table: dict[str, list[dict[str, Any]]] = {}
        self.identity_resets: list[tuple[str, list[str]]] = []

    def ensure_empty(self, table_names: list[str]) -> None:
        self.empty_checked = table_names

    def apply_blueprint(self, blueprint_sql: str) -> None:
        self.blueprint_sql = blueprint_sql

    def insert_rows(
        self,
        *,
        table_name: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> None:
        self.rows_by_table[table_name] = [
            {column: row[column] for column in columns} for row in rows
        ]

    def reset_identity(self, *, table_name: str, primary_keys: list[str]) -> None:
        self.identity_resets.append((table_name, primary_keys))

    def count_rows(self, table_name: str) -> int:
        return len(self.rows_by_table.get(table_name, []))


class MismatchedCountTarget(RecordingTarget):
    def count_rows(self, table_name: str) -> int:
        return super().count_rows(table_name) + 1


class FakeScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class FakeConnection:
    def __init__(self, counts: dict[str, int] | None = None) -> None:
        self.counts = counts or {}
        self.calls: list[tuple[str, object | None]] = []

    def execute(
        self,
        statement: object,
        parameters: object | None = None,
    ) -> FakeScalarResult:
        sql = str(statement)
        self.calls.append((sql, parameters))
        if sql.startswith("SELECT COUNT(*) FROM "):
            table_name = sql.removeprefix("SELECT COUNT(*) FROM ").strip('"')
            return FakeScalarResult(self.counts.get(table_name, 0))
        if sql.startswith("INSERT INTO "):
            table_name = sql.removeprefix("INSERT INTO ").split(" ", 1)[0].strip('"')
            self.counts[table_name] = self.counts.get(table_name, 0) + len(
                parameters if isinstance(parameters, list) else []
            )
        return FakeScalarResult(0)


class FakeBegin:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    def __enter__(self) -> FakeConnection:
        return self._connection

    def __exit__(self, *_exc_info: object) -> None:
        return None


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def begin(self) -> FakeBegin:
        return FakeBegin(self.connection)


def test_run_postgres_rehearsal_loads_sqlite_rows_into_injected_target() -> None:
    connection = _sqlite_source()
    target = RecordingTarget()

    result = run_postgres_rehearsal_from_sqlite(
        sqlite_connection=connection,
        target=target,
        blueprint_sql='CREATE TABLE "parents" ("id" BIGINT);',
        execution_plan=_execution_plan(),
    )

    assert result.status == "succeeded"
    assert result.loaded_tables == ["parents", "children"]
    assert result.validated_tables == ["parents", "children"]
    assert result.inserted_rows == 3
    assert target.empty_checked == ["parents", "children"]
    assert target.blueprint_sql == 'CREATE TABLE "parents" ("id" BIGINT);'
    assert target.rows_by_table["parents"] == [
        {"id": 1, "name": "Matriz"},
    ]
    assert target.rows_by_table["children"] == [
        {"id": 10, "parent_id": 1, "amount_cents": 12345},
        {"id": 11, "parent_id": 1, "amount_cents": 987},
    ]
    assert target.identity_resets == [
        ("parents", ["id"]),
        ("children", ["id"]),
    ]


def test_run_postgres_rehearsal_blocks_count_mismatch() -> None:
    with pytest.raises(ValueError, match="Contagem divergente em parents"):
        run_postgres_rehearsal_from_sqlite(
            sqlite_connection=_sqlite_source(),
            target=MismatchedCountTarget(),
            blueprint_sql='CREATE TABLE "parents" ("id" BIGINT);',
            execution_plan=_execution_plan(),
        )


def test_run_postgres_rehearsal_requires_parameter_binding() -> None:
    execution_plan = _execution_plan()
    execution_plan["phases"][0]["operations"][0]["uses_parameter_binding"] = False

    with pytest.raises(ValueError, match="parametros nomeados"):
        run_postgres_rehearsal_from_sqlite(
            sqlite_connection=_sqlite_source(),
            target=RecordingTarget(),
            blueprint_sql='CREATE TABLE "parents" ("id" BIGINT);',
            execution_plan=execution_plan,
        )


def test_sqlalchemy_target_blocks_non_empty_target() -> None:
    target = SqlAlchemyPostgresRehearsalTarget(FakeConnection({"parents": 1}))  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="parents"):
        target.ensure_empty(["parents", "children"])


def test_sqlalchemy_target_uses_parameterized_insert_and_identity_reset() -> None:
    connection = FakeConnection()
    target = SqlAlchemyPostgresRehearsalTarget(connection)  # type: ignore[arg-type]

    target.insert_rows(
        table_name="children",
        columns=["id", "amount_cents"],
        rows=[{"id": 1, "amount_cents": 1234}],
    )
    target.reset_identity(table_name="children", primary_keys=["id"])

    assert connection.calls[0] == (
        'INSERT INTO "children" ("id", "amount_cents") VALUES (:id, :amount_cents)',
        [{"id": 1, "amount_cents": 1234}],
    )
    assert "pg_get_serial_sequence" in connection.calls[1][0]
    assert connection.calls[1][1] == {
        "table_name": "children",
        "primary_key": "id",
    }


def test_sqlalchemy_target_splits_reviewed_blueprint_statements() -> None:
    connection = FakeConnection()
    target = SqlAlchemyPostgresRehearsalTarget(connection)  # type: ignore[arg-type]

    target.apply_blueprint(
        """
        -- comentario de revisao
        BEGIN;
        CREATE TABLE "parents" ("id" BIGINT);
        COMMIT;
        """
    )

    assert [call[0] for call in connection.calls] == [
        "BEGIN",
        'CREATE TABLE "parents" ("id" BIGINT)',
        "COMMIT",
    ]


def test_execute_postgres_rehearsal_with_sqlalchemy_uses_env_url_and_masks_result(
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
    fake_engine = FakeEngine()
    seen_urls: list[str] = []
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

        result = execute_postgres_rehearsal_with_sqlalchemy(
            settings=settings,
            readiness=readiness,
            health=health,
            inventory=inventory,
            sqlite_connection=connection,
            engine_factory=lambda database_url: _record_engine_url(
                seen_urls,
                database_url,
                fake_engine,
            ),  # type: ignore[arg-type]
        )

    assert seen_urls == ["postgresql://financeiro:valor_local@localhost:5432/basilica_hml"]
    assert result.status == "succeeded"
    assert result.target_database_location == (
        "postgresql://financeiro:***@localhost:5432/basilica_hml"
    )
    assert "valor_local" not in result.target_database_location
    assert result.inserted_rows > 0
    assert result.executed_steps > 0
    assert any(call[0].startswith("INSERT INTO ") for call in fake_engine.connection.calls)


def test_execute_postgres_rehearsal_with_sqlalchemy_blocks_before_engine(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    readiness = get_deployment_readiness(settings)
    engine_called = False
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

        def engine_factory(_database_url: str) -> FakeEngine:
            nonlocal engine_called
            engine_called = True
            return FakeEngine()

        with pytest.raises(ValueError, match="POSTGRES_REHEARSAL_ENABLE_EXECUTION"):
            execute_postgres_rehearsal_with_sqlalchemy(
                settings=settings,
                readiness=readiness,
                health=health,
                inventory=inventory,
                sqlite_connection=connection,
                engine_factory=engine_factory,  # type: ignore[arg-type]
            )

    assert engine_called is False


def test_execute_postgres_rehearsal_with_sqlalchemy_blocks_without_driver(
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
    engine_called = False
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)
        health = get_local_database_health(connection)
        inventory = get_local_schema_inventory(connection)

        def engine_factory(_database_url: str) -> FakeEngine:
            nonlocal engine_called
            engine_called = True
            return FakeEngine()

        with pytest.raises(ValueError, match="psycopg"):
            execute_postgres_rehearsal_with_sqlalchemy(
                settings=settings,
                readiness=readiness,
                health=health,
                inventory=inventory,
                sqlite_connection=connection,
                engine_factory=engine_factory,  # type: ignore[arg-type]
            )

    assert engine_called is False


def test_run_postgres_rehearsal_admin_action_writes_safe_local_report(
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
    fake_engine = FakeEngine()
    output_path = tmp_path / "reports" / "homologacao-postgresql.md"
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        report = run_postgres_rehearsal_admin_action(
            settings=settings,
            sqlite_connection=connection,
            output_path=output_path,
            engine_factory=lambda database_url: _record_engine_url(
                [],
                database_url,
                fake_engine,
            ),  # type: ignore[arg-type]
        )

    content = output_path.read_text(encoding="utf-8")

    assert report.output_path == output_path
    assert report.result.status == "succeeded"
    assert "# Relatorio local de homologacao PostgreSQL" in content
    assert "postgresql://financeiro:***@localhost:5432/basilica_hml" in content
    assert "valor_local" not in content
    assert "Linhas carregadas:" in content
    assert "## Tabelas validadas" in content


def test_run_postgres_rehearsal_admin_action_blocks_without_report(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    output_path = tmp_path / "reports" / "homologacao-postgresql.md"
    engine_called = False
    with connect(tmp_path / "financeiro.sqlite3") as connection:
        migrate(connection)

        def engine_factory(_database_url: str) -> FakeEngine:
            nonlocal engine_called
            engine_called = True
            return FakeEngine()

        with pytest.raises(ValueError, match="POSTGRES_REHEARSAL_ENABLE_EXECUTION"):
            run_postgres_rehearsal_admin_action(
                settings=settings,
                sqlite_connection=connection,
                output_path=output_path,
                engine_factory=engine_factory,  # type: ignore[arg-type]
            )

    assert engine_called is False
    assert not output_path.exists()


def _sqlite_source() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE parents (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    connection.execute(
        """
        CREATE TABLE children (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER NOT NULL,
            amount_cents INTEGER NOT NULL,
            FOREIGN KEY (parent_id) REFERENCES parents(id)
        )
        """
    )
    connection.execute("INSERT INTO parents (id, name) VALUES (1, 'Matriz')")
    connection.execute("INSERT INTO children (id, parent_id, amount_cents) VALUES (10, 1, 12345)")
    connection.execute("INSERT INTO children (id, parent_id, amount_cents) VALUES (11, 1, 987)")
    return connection


def _record_engine_url(
    seen_urls: list[str],
    database_url: str,
    engine: FakeEngine,
) -> FakeEngine:
    seen_urls.append(database_url)
    return engine


def _settings(
    tmp_path: Path,
    *,
    postgres_rehearsal_database_url: str | None = None,
    postgres_rehearsal_enable_execution: bool = False,
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
        asaas_api_key=None,
        asaas_enable_write_operations=False,
        pdv_database_url=None,
        google_client_secret_path=None,
        google_token_path=None,
        paths=AppPaths.from_workspace(tmp_path),
        postgres_rehearsal_database_url=postgres_rehearsal_database_url,
        postgres_rehearsal_enable_execution=postgres_rehearsal_enable_execution,
    )


def _execution_plan() -> dict[str, Any]:
    return {
        "metadata_only": True,
        "contains_credentials": False,
        "opens_external_connection": False,
        "executes_migration": False,
        "ready_for_execution_rehearsal": True,
        "phases": [
            {
                "name": "load",
                "operations": [
                    {
                        "operation": "insert_rows",
                        "table": "parents",
                        "columns": ["id", "name"],
                        "uses_parameter_binding": True,
                    },
                    {
                        "operation": "insert_rows",
                        "table": "children",
                        "columns": ["id", "parent_id", "amount_cents"],
                        "uses_parameter_binding": True,
                    },
                ],
            },
            {
                "name": "identity",
                "operations": [
                    {
                        "operation": "reset_identity_sequence",
                        "table": "parents",
                        "primary_keys": ["id"],
                    },
                    {
                        "operation": "reset_identity_sequence",
                        "table": "children",
                        "primary_keys": ["id"],
                    },
                ],
            },
            {
                "name": "validation",
                "operations": [
                    {
                        "operation": "compare_row_count",
                        "table": "parents",
                        "source_count": 1,
                    },
                    {
                        "operation": "compare_row_count",
                        "table": "children",
                        "source_count": 2,
                    },
                ],
            },
        ],
    }
