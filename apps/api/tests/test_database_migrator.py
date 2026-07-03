import importlib
from types import ModuleType, SimpleNamespace

import pytest

from refunds_ai_api.config import Settings
from refunds_ai_api.database import seeds
from refunds_ai_api.database.migrator import (
    Migration,
    MigrationConfigurationError,
    MigrationError,
    apply_migrations,
    connect,
    discover_migrations,
    format_status,
    get_applied_migration_ids,
    get_migration_statuses,
    record_migration,
    run_seed_steps,
)
from refunds_ai_api.database.seeds import SeedDataError

schema_foundation = importlib.import_module(
    "refunds_ai_api.database.migrations.000_schema_foundation"
)
create_users = importlib.import_module("refunds_ai_api.database.migrations.001_create_users")
create_roles = importlib.import_module("refunds_ai_api.database.migrations.002_create_roles")
create_user_roles = importlib.import_module(
    "refunds_ai_api.database.migrations.003_create_user_roles"
)


class StubCursor:
    def __init__(self, connection: "StubConnection") -> None:
        self.connection = connection
        self.result_rows: list[dict[str, str]] = []

    def __enter__(self) -> "StubCursor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, statement: str, params=None) -> None:
        self.connection.executed.append((statement, params))

        normalized = " ".join(statement.split()).lower()
        if normalized.startswith("select migration_id from schema_migrations"):
            self.result_rows = [
                {"migration_id": migration_id}
                for migration_id in sorted(self.connection.applied_migration_ids)
            ]
            return

        if normalized.startswith("insert into schema_migrations"):
            assert params is not None
            self.connection.applied_migration_ids.add(params[0])

    def fetchall(self) -> list[dict[str, str]]:
        return self.result_rows


class StubTransaction:
    def __init__(self, connection: "StubConnection") -> None:
        self.connection = connection

    def __enter__(self) -> "StubTransaction":
        self.connection.transaction_entries += 1
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class StubConnection:
    def __init__(self, applied_migration_ids: set[str] | None = None) -> None:
        self.applied_migration_ids = applied_migration_ids or set()
        self.executed: list[tuple[str, tuple[str, str] | None]] = []
        self.transaction_entries = 0

    def __enter__(self) -> "StubConnection":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def cursor(self) -> StubCursor:
        return StubCursor(self)

    def transaction(self) -> StubTransaction:
        return StubTransaction(self)


def build_migration(migration_id: str, calls: list[str]) -> Migration:
    module = ModuleType(migration_id)
    module.upgrade = lambda connection: calls.append(migration_id)
    return Migration(
        migration_id=migration_id,
        description=f"Migration {migration_id}",
        module=module,
    )


def test_connect_requires_supabase_url() -> None:
    with pytest.raises(MigrationConfigurationError, match="SUPABASE_DB_URL is not configured"):
        connect(Settings(SUPABASE_DB_URL=None, DATABASE_CONNECT_TIMEOUT_SECONDS=5))


def test_connect_uses_backend_database_settings(monkeypatch) -> None:
    calls = []

    def psycopg_connect(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace()

    monkeypatch.setattr("refunds_ai_api.database.migrator.psycopg.connect", psycopg_connect)

    connection = connect(
        Settings(
            SUPABASE_DB_URL="postgresql://user:password@example.supabase.co:5432/postgres",
            DATABASE_CONNECT_TIMEOUT_SECONDS=9,
        )
    )

    assert connection == SimpleNamespace()
    assert calls[0][0] == ("postgresql://user:password@example.supabase.co:5432/postgres",)
    assert calls[0][1]["connect_timeout"] == 9


def test_discover_migrations_returns_ordered_modules() -> None:
    migration_ids = [migration.migration_id for migration in discover_migrations()]

    assert migration_ids == sorted(migration_ids)
    assert migration_ids[:4] == [
        "000_schema_foundation",
        "001_create_users",
        "002_create_roles",
        "003_create_user_roles",
    ]


def test_discover_migrations_rejects_invalid_modules(monkeypatch) -> None:
    invalid_module = ModuleType("refunds_ai_api.database.migrations.999_invalid")
    invalid_module.DESCRIPTION = "Missing migration id."
    invalid_module.upgrade = lambda connection: None

    monkeypatch.setattr(
        "refunds_ai_api.database.migrator.pkgutil.iter_modules",
        lambda *args: [SimpleNamespace(ispkg=False, name=invalid_module.__name__)],
    )
    monkeypatch.setattr(
        "refunds_ai_api.database.migrator.importlib.import_module",
        lambda module_name: invalid_module,
    )

    with pytest.raises(MigrationError, match="must define MIGRATION_ID"):
        discover_migrations()


def test_get_applied_migration_ids_creates_foundation_table_first() -> None:
    connection = StubConnection(applied_migration_ids={"000_schema_foundation"})

    applied_ids = get_applied_migration_ids(connection)

    assert applied_ids == {"000_schema_foundation"}
    assert "create table if not exists schema_migrations" in connection.executed[0][0]


def test_record_migration_is_idempotent() -> None:
    connection = StubConnection()
    migration = build_migration("001_create_customers", [])

    record_migration(connection, migration)
    record_migration(connection, migration)

    assert connection.applied_migration_ids == {"001_create_customers"}


def test_apply_migrations_runs_only_pending_migrations_in_order() -> None:
    calls: list[str] = []
    connection = StubConnection(applied_migration_ids={"001_first"})
    available_migrations = [
        build_migration("001_first", calls),
        build_migration("002_second", calls),
        build_migration("003_third", calls),
    ]

    applied = apply_migrations(connection, available_migrations)

    assert [migration.migration_id for migration in applied] == ["002_second", "003_third"]
    assert calls == ["002_second", "003_third"]
    assert connection.applied_migration_ids == {"001_first", "002_second", "003_third"}
    assert connection.transaction_entries == 2


def test_get_migration_statuses_marks_applied_and_pending() -> None:
    connection = StubConnection(applied_migration_ids={"001_first"})
    available_migrations = [
        build_migration("001_first", []),
        build_migration("002_second", []),
    ]

    statuses = get_migration_statuses(connection, available_migrations)

    assert [(status.migration_id, status.applied) for status in statuses] == [
        ("001_first", True),
        ("002_second", False),
    ]


def test_format_status_outputs_cli_friendly_lines() -> None:
    connection = StubConnection(applied_migration_ids={"001_first"})
    available_migrations = [
        build_migration("001_first", []),
        build_migration("002_second", []),
    ]
    statuses = get_migration_statuses(connection, available_migrations)

    output = format_status(statuses)

    assert "001_first: applied - Migration 001_first" in output
    assert "002_second: pending - Migration 002_second" in output


def test_run_seed_steps_delegates_to_seed_module(monkeypatch) -> None:
    connection = StubConnection()

    monkeypatch.setattr(
        "refunds_ai_api.database.migrator.seeds.seed",
        lambda received_connection: ["customers"],
    )

    assert run_seed_steps(connection) == ["customers"]


def test_identity_seed_fixture_matches_documented_shape() -> None:
    seed_data = seeds.load_identity_seed_data()

    assert {role["key"] for role in seed_data["roles"]} == {"customer", "admin"}
    assert len(seed_data["users"]) == 16
    assert len(seed_data["user_roles"]) == 16
    assert sum(1 for row in seed_data["user_roles"] if row["role_key"] == "customer") == 15
    assert sum(1 for row in seed_data["user_roles"] if row["role_key"] == "admin") == 1


def test_validate_identity_seed_data_rejects_invalid_shape() -> None:
    with pytest.raises(SeedDataError, match="customer and admin roles"):
        seeds.validate_identity_seed_data(
            {
                "roles": [],
                "users": [],
                "user_roles": [],
            }
        )


def test_seed_entry_point_seeds_identity_data() -> None:
    connection = StubConnection()

    completed_steps = seeds.seed(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert completed_steps == ["identity"]
    assert executed_sql.count("insert into public.roles") == 2
    assert executed_sql.count("insert into public.users") == 16
    assert executed_sql.count("insert into public.user_roles") == 16
    assert "on conflict (key) do update" in executed_sql
    assert "on conflict (id) do update" in executed_sql
    assert "on conflict (user_id, role_id) do nothing" in executed_sql


def test_schema_foundation_migration_creates_extensions_metadata_and_index() -> None:
    connection = StubConnection()

    schema_foundation.upgrade(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert 'create extension if not exists "pgcrypto"' in executed_sql
    assert "create table if not exists schema_migrations" in executed_sql
    assert "migration_id text primary key" in executed_sql
    assert "description text not null" in executed_sql
    assert "applied_at timestamptz not null default now()" in executed_sql
    assert "create index if not exists idx_schema_migrations_applied_at" in executed_sql
    assert "on schema_migrations (applied_at)" in executed_sql


def test_create_users_migration_creates_requested_columns_and_security() -> None:
    connection = StubConnection()

    create_users.upgrade(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert "create table if not exists public.users" in executed_sql
    assert "id uuid primary key" in executed_sql
    assert "first_name text not null" in executed_sql
    assert "last_name text not null" in executed_sql
    assert "created_at timestamptz not null default now()" in executed_sql
    assert "alter table public.users enable row level security" in executed_sql
    assert "create policy users_service_role_all" in executed_sql
    assert "to service_role" in executed_sql
    assert "using (true)" in executed_sql
    assert "with check (true)" in executed_sql


def test_main_apply_command_reports_applied_migrations(monkeypatch, capsys) -> None:
    connection = StubConnection()
    monkeypatch.setattr("refunds_ai_api.database.migrator.connect", lambda settings: connection)

    from refunds_ai_api.database import migrator

    exit_code = migrator.main(["apply"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Applied 000_schema_foundation" in output
    assert "Applied 001_create_users" in output
    assert "Applied 002_create_roles" in output
    assert "Applied 003_create_user_roles" in output


def test_main_status_command_reports_migration_state(monkeypatch, capsys) -> None:
    connection = StubConnection(applied_migration_ids={"000_schema_foundation"})
    monkeypatch.setattr("refunds_ai_api.database.migrator.connect", lambda settings: connection)

    from refunds_ai_api.database import migrator

    exit_code = migrator.main(["status"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "000_schema_foundation: applied" in output
    assert "001_create_users: pending" in output


def test_main_seed_command_reports_identity_seed_step(monkeypatch, capsys) -> None:
    connection = StubConnection()
    monkeypatch.setattr("refunds_ai_api.database.migrator.connect", lambda settings: connection)

    from refunds_ai_api.database import migrator

    exit_code = migrator.main(["seed"])

    assert exit_code == 0
    assert "Seeded identity" in capsys.readouterr().out


def test_create_roles_migration_creates_requested_columns_and_security() -> None:
    connection = StubConnection()

    create_roles.upgrade(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert "create table if not exists public.roles" in executed_sql
    assert "id uuid primary key" in executed_sql
    assert "key text unique not null" in executed_sql
    assert "name text not null" in executed_sql
    assert "alter table public.roles enable row level security" in executed_sql
    assert "create policy roles_service_role_all" in executed_sql
    assert "to service_role" in executed_sql
    assert "using (true)" in executed_sql
    assert "with check (true)" in executed_sql


def test_create_user_roles_migration_creates_relationships_indexes_and_security() -> None:
    connection = StubConnection()

    create_user_roles.upgrade(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert "create table if not exists public.user_roles" in executed_sql
    assert "user_id uuid references public.users(id) on delete cascade" in executed_sql
    assert "role_id uuid references public.roles(id) on delete cascade" in executed_sql
    assert "created_at timestamptz not null default now()" in executed_sql
    assert "primary key (user_id, role_id)" in executed_sql
    assert "create index if not exists idx_user_roles_role_id" in executed_sql
    assert "on public.user_roles (role_id)" in executed_sql
    assert "alter table public.user_roles enable row level security" in executed_sql
    assert "create policy user_roles_service_role_all" in executed_sql
    assert "to service_role" in executed_sql
    assert "using (true)" in executed_sql
    assert "with check (true)" in executed_sql
