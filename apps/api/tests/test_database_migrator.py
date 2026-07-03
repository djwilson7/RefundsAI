import importlib
from datetime import datetime
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
create_products = importlib.import_module("refunds_ai_api.database.migrations.004_create_products")
create_purchases = importlib.import_module(
    "refunds_ai_api.database.migrations.005_create_purchases"
)
create_digital_purchase_details = importlib.import_module(
    "refunds_ai_api.database.migrations.006_create_digital_purchase_details"
)
create_physical_purchase_details = importlib.import_module(
    "refunds_ai_api.database.migrations.007_create_physical_purchase_details"
)
create_subscription_purchase_details = importlib.import_module(
    "refunds_ai_api.database.migrations.008_create_subscription_purchase_details"
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
    assert migration_ids[:9] == [
        "000_schema_foundation",
        "001_create_users",
        "002_create_roles",
        "003_create_user_roles",
        "004_create_products",
        "005_create_purchases",
        "006_create_digital_purchase_details",
        "007_create_physical_purchase_details",
        "008_create_subscription_purchase_details",
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


def test_purchase_seed_fixture_matches_documented_catalog_shape() -> None:
    seed_data = seeds.load_purchase_seed_data()
    product_types = [product["product_type"] for product in seed_data["products"]]

    assert len(seed_data["products"]) == 30
    assert product_types.count("physical") == 14
    assert product_types.count("digital") == 10
    assert product_types.count("subscription") == 6
    assert seed_data["purchase_plan"]["customer_count"] == 15
    assert seed_data["purchase_plan"]["purchases_per_customer"] == 12
    assert seed_data["purchase_plan"]["type_distribution"] == {
        "physical": 90,
        "digital": 54,
        "subscription": 36,
    }
    assert seed_data["purchase_plan"]["first_purchase_at"] == "2026-05-20T14:00:00Z"
    assert seed_data["purchase_plan"]["last_purchase_at"] == "2026-07-03T14:00:00Z"
    assert seed_data["purchase_plan"]["status"] == "completed"


def test_build_purchase_seed_rows_matches_documented_distribution() -> None:
    purchase_seed_data = seeds.load_purchase_seed_data()
    identity_seed_data = seeds.load_identity_seed_data()

    purchases = seeds.build_purchase_seed_rows(purchase_seed_data, identity_seed_data)
    purchase_types = [purchase["purchase_type"] for purchase in purchases]

    assert len(purchases) == 180
    assert purchase_types.count("physical") == 90
    assert purchase_types.count("digital") == 54
    assert purchase_types.count("subscription") == 36
    assert len({purchase["order_number"] for purchase in purchases}) == 180
    assert purchases[0]["order_number"] == "RAI-10001"
    assert {purchase["status"] for purchase in purchases} == {"completed"}

    purchased_at_values = [
        datetime.fromisoformat(purchase["purchased_at"].replace("Z", "+00:00"))
        for purchase in purchases
    ]
    assert min(purchased_at_values).isoformat() == "2026-05-20T14:00:00+00:00"
    assert max(purchased_at_values).date().isoformat() == "2026-07-03"
    assert (max(purchased_at_values).date() - min(purchased_at_values).date()).days == 44


def test_validate_identity_seed_data_rejects_invalid_shape() -> None:
    with pytest.raises(SeedDataError, match="customer and admin roles"):
        seeds.validate_identity_seed_data(
            {
                "roles": [],
                "users": [],
                "user_roles": [],
            }
        )


def test_validate_purchase_seed_data_rejects_invalid_shape() -> None:
    with pytest.raises(SeedDataError, match="exactly 30 products"):
        seeds.validate_purchase_seed_data(
            {
                "products": [],
                "purchase_plan": {},
            }
        )


def test_seed_entry_point_seeds_identity_data() -> None:
    connection = StubConnection()

    completed_steps = seeds.seed(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert completed_steps == ["identity", "purchase_catalog"]
    assert executed_sql.count("insert into public.roles") == 2
    assert executed_sql.count("insert into public.users") == 16
    assert executed_sql.count("insert into public.user_roles") == 16
    assert executed_sql.count("insert into public.products") == 30
    assert executed_sql.count("insert into public.purchases") == 180
    assert "on conflict (key) do update" in executed_sql
    assert "on conflict (id) do update" in executed_sql
    assert "on conflict (user_id, role_id) do nothing" in executed_sql
    assert "on conflict (sku) do update" in executed_sql
    assert "on conflict (order_number) do update" in executed_sql


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
    output = capsys.readouterr().out
    assert "Seeded identity" in output
    assert "Seeded purchase_catalog" in output


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


def test_create_products_migration_creates_constraints_indexes_and_security() -> None:
    connection = StubConnection()

    create_products.upgrade(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert "create table if not exists public.products" in executed_sql
    assert "id uuid primary key" in executed_sql
    assert "name text not null" in executed_sql
    assert "sku text not null" in executed_sql
    assert "product_type text not null" in executed_sql
    assert "base_price_cents integer not null" in executed_sql
    assert "created_at timestamptz not null default now()" in executed_sql
    assert "updated_at timestamptz not null default now()" in executed_sql
    assert "check (product_type in ('physical', 'digital', 'subscription'))" in executed_sql
    assert "check (base_price_cents >= 0)" in executed_sql
    assert "create unique index if not exists products_sku_idx" in executed_sql
    assert "on public.products (sku)" in executed_sql
    assert "create index if not exists products_product_type_idx" in executed_sql
    assert "on public.products (product_type)" in executed_sql
    assert "alter table public.products enable row level security" in executed_sql
    assert "create policy products_service_role_all" in executed_sql


def test_create_purchases_migration_creates_relationships_indexes_and_security() -> None:
    connection = StubConnection()

    create_purchases.upgrade(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert "create table if not exists public.purchases" in executed_sql
    assert "id uuid primary key" in executed_sql
    assert "user_id uuid not null references public.users(id) on delete cascade" in executed_sql
    assert "product_id uuid not null references public.products(id)" in executed_sql
    assert "order_number text not null" in executed_sql
    assert "purchase_type text not null" in executed_sql
    assert "amount_cents integer not null" in executed_sql
    assert "purchased_at timestamptz not null" in executed_sql
    assert "status text not null default 'completed'" in executed_sql
    assert "check (purchase_type in ('physical', 'digital', 'subscription'))" in executed_sql
    assert "'refund_pending'" in executed_sql
    assert "check (amount_cents >= 0)" in executed_sql
    assert "create unique index if not exists purchases_order_number_idx" in executed_sql
    assert "create index if not exists purchases_user_id_idx" in executed_sql
    assert "create index if not exists purchases_product_id_idx" in executed_sql
    assert "create index if not exists purchases_purchase_type_idx" in executed_sql
    assert "create index if not exists purchases_status_idx" in executed_sql
    assert "create index if not exists purchases_purchased_at_idx" in executed_sql
    assert "on public.purchases (purchased_at desc)" in executed_sql
    assert "create index if not exists purchases_user_purchased_at_idx" in executed_sql
    assert "on public.purchases (user_id, purchased_at desc)" in executed_sql
    assert "alter table public.purchases enable row level security" in executed_sql
    assert "create policy purchases_service_role_all" in executed_sql


def test_create_digital_purchase_details_migration_creates_one_to_one_extension() -> None:
    connection = StubConnection()

    create_digital_purchase_details.upgrade(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert "create table if not exists public.digital_purchase_details" in executed_sql
    assert "id uuid primary key" in executed_sql
    assert "purchase_id uuid unique not null" in executed_sql
    assert "references public.purchases(id) on delete cascade" in executed_sql
    assert "issued_code text unique not null" in executed_sql
    assert "code_redeemed boolean not null default false" in executed_sql
    assert "code_redeemed_at timestamptz null" in executed_sql
    assert "code_invalidated_at timestamptz null" in executed_sql
    assert (
        "create unique index if not exists digital_purchase_details_purchase_id_idx"
        in executed_sql
    )
    assert "on public.digital_purchase_details (purchase_id)" in executed_sql
    assert (
        "create unique index if not exists digital_purchase_details_issued_code_idx"
        in executed_sql
    )
    assert "on public.digital_purchase_details (issued_code)" in executed_sql
    assert "alter table public.digital_purchase_details enable row level security" in executed_sql
    assert "create policy digital_purchase_details_service_role_all" in executed_sql


def test_create_physical_purchase_details_migration_creates_one_to_one_extension() -> None:
    connection = StubConnection()

    create_physical_purchase_details.upgrade(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert "create table if not exists public.physical_purchase_details" in executed_sql
    assert "id uuid primary key" in executed_sql
    assert "purchase_id uuid unique not null" in executed_sql
    assert "references public.purchases(id) on delete cascade" in executed_sql
    assert "scheduled_delivery_at timestamptz not null" in executed_sql
    assert "delivered_at timestamptz null" in executed_sql
    assert "return_status text not null default 'not_requested'" in executed_sql
    assert "carrier text null" in executed_sql
    assert "tracking_number text null" in executed_sql
    assert "accepted_by_carrier_at timestamptz null" in executed_sql
    assert "'accepted_by_carrier'" in executed_sql
    assert (
        "create unique index if not exists physical_purchase_details_purchase_id_idx"
        in executed_sql
    )
    assert "on public.physical_purchase_details (purchase_id)" in executed_sql
    assert "create index if not exists physical_purchase_details_return_status_idx" in executed_sql
    assert "on public.physical_purchase_details (return_status)" in executed_sql
    assert (
        "public.validate_physical_purchase_details_delivery_window()"
        in executed_sql
    )
    assert "select purchases.purchased_at" in executed_sql
    assert "where purchases.id = new.purchase_id" in executed_sql
    assert "new.scheduled_delivery_at <= purchase_purchased_at" in executed_sql
    assert "purchase_purchased_at + interval '2 days'" in executed_sql
    assert "purchase_purchased_at + interval '7 days'" in executed_sql
    assert "new.delivered_at <= purchase_purchased_at" in executed_sql
    assert "new.delivered_at > new.scheduled_delivery_at" in executed_sql
    assert "new.delivered_at > now()" in executed_sql
    assert (
        "drop trigger if exists validate_physical_purchase_details_delivery_window"
        in executed_sql
    )
    assert "create trigger validate_physical_purchase_details_delivery_window" in executed_sql
    assert (
        "before insert or update of purchase_id, scheduled_delivery_at, delivered_at"
        in executed_sql
    )
    assert (
        "execute function public.validate_physical_purchase_details_delivery_window()"
        in executed_sql
    )
    assert "alter table public.physical_purchase_details enable row level security" in executed_sql
    assert "create policy physical_purchase_details_service_role_all" in executed_sql


def test_create_subscription_purchase_details_migration_creates_one_to_one_extension() -> None:
    connection = StubConnection()

    create_subscription_purchase_details.upgrade(connection)

    executed_sql = "\n".join(statement for statement, _params in connection.executed).lower()
    assert "create table if not exists public.subscription_purchase_details" in executed_sql
    assert "id uuid primary key" in executed_sql
    assert "purchase_id uuid unique not null" in executed_sql
    assert "references public.purchases(id) on delete cascade" in executed_sql
    assert "period_start timestamptz not null" in executed_sql
    assert "period_end timestamptz not null" in executed_sql
    assert "cancelled_at timestamptz null" in executed_sql
    assert "check (period_end > period_start)" in executed_sql
    assert (
        "create unique index if not exists subscription_purchase_details_purchase_id_idx"
        in executed_sql
    )
    assert "on public.subscription_purchase_details (purchase_id)" in executed_sql
    assert "create index if not exists subscription_purchase_details_period_idx" in executed_sql
    assert "on public.subscription_purchase_details (period_start, period_end)" in executed_sql
    assert (
        "alter table public.subscription_purchase_details enable row level security"
        in executed_sql
    )
    assert "create policy subscription_purchase_details_service_role_all" in executed_sql
