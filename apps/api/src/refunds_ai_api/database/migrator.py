"""Small psycopg-based migration runner for Supabase PostgreSQL."""

from __future__ import annotations

import argparse
import importlib
import pkgutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from types import ModuleType

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from refunds_ai_api.config import Settings, get_settings
from refunds_ai_api.database import migrations, seeds


class MigrationConfigurationError(RuntimeError):
    """Raised when database migration configuration is missing or invalid."""


class MigrationError(RuntimeError):
    """Raised when migration modules are invalid or migration execution fails."""


@dataclass(frozen=True)
class Migration:
    """A discovered schema migration module."""

    migration_id: str
    description: str
    module: ModuleType

    def upgrade(self, connection: Connection) -> None:
        """Apply this migration to the provided database connection."""
        self.module.upgrade(connection)


@dataclass(frozen=True)
class MigrationStatus:
    """Current applied state for a schema migration."""

    migration_id: str
    description: str
    applied: bool


def discover_migrations() -> list[Migration]:
    """Return migration modules in deterministic migration id order."""
    discovered: list[Migration] = []

    for module_info in pkgutil.iter_modules(migrations.__path__, migrations.__name__ + "."):
        if module_info.ispkg or module_info.name.rsplit(".", maxsplit=1)[-1].startswith("_"):
            continue

        module = importlib.import_module(module_info.name)
        migration_id = getattr(module, "MIGRATION_ID", None)
        description = getattr(module, "DESCRIPTION", None)
        upgrade = getattr(module, "upgrade", None)

        if not isinstance(migration_id, str) or not migration_id:
            raise MigrationError(f"{module_info.name} must define MIGRATION_ID.")
        if not isinstance(description, str) or not description:
            raise MigrationError(f"{module_info.name} must define DESCRIPTION.")
        if not callable(upgrade):
            raise MigrationError(f"{module_info.name} must define callable upgrade(connection).")

        discovered.append(
            Migration(
                migration_id=migration_id,
                description=description,
                module=module,
            )
        )

    return sorted(discovered, key=lambda migration: migration.migration_id)


def connect(settings: Settings) -> Connection:
    """Open a database connection using backend-owned Supabase configuration."""
    if not settings.supabase_db_url:
        raise MigrationConfigurationError("SUPABASE_DB_URL is not configured.")

    return psycopg.connect(
        settings.supabase_db_url,
        connect_timeout=settings.database_connect_timeout_seconds,
        row_factory=dict_row,
    )


def ensure_migration_table(connection: Connection) -> None:
    """Create migration bookkeeping table before migration status checks."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists schema_migrations (
                migration_id text primary key,
                description text not null,
                applied_at timestamptz not null default now()
            )
            """
        )


def get_applied_migration_ids(connection: Connection) -> set[str]:
    """Return migration ids already recorded in schema_migrations."""
    ensure_migration_table(connection)
    with connection.cursor() as cursor:
        cursor.execute("select migration_id from schema_migrations")
        return {row["migration_id"] for row in cursor.fetchall()}


def record_migration(connection: Connection, migration: Migration) -> None:
    """Record a successfully applied migration."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into schema_migrations (migration_id, description)
            values (%s, %s)
            on conflict (migration_id) do nothing
            """,
            (migration.migration_id, migration.description),
        )


def apply_migrations(
    connection: Connection,
    available_migrations: Sequence[Migration] | None = None,
) -> list[Migration]:
    """Apply pending migrations once, in order, and return the migrations applied."""
    migrations_to_apply = list(available_migrations or discover_migrations())
    applied_ids = get_applied_migration_ids(connection)
    applied_now: list[Migration] = []

    for migration in migrations_to_apply:
        if migration.migration_id in applied_ids:
            continue

        with connection.transaction():
            migration.upgrade(connection)
            record_migration(connection, migration)

        applied_ids.add(migration.migration_id)
        applied_now.append(migration)

    return applied_now


def get_migration_statuses(
    connection: Connection,
    available_migrations: Sequence[Migration] | None = None,
) -> list[MigrationStatus]:
    """Return status rows for all discovered migrations."""
    migrations_to_report = list(available_migrations or discover_migrations())
    applied_ids = get_applied_migration_ids(connection)

    return [
        MigrationStatus(
            migration_id=migration.migration_id,
            description=migration.description,
            applied=migration.migration_id in applied_ids,
        )
        for migration in migrations_to_report
    ]


def run_seed_steps(connection: Connection) -> list[str]:
    """Run all configured idempotent seed steps."""
    return seeds.seed(connection)


def reset_demo_database(connection: Connection) -> tuple[list[Migration], list[str]]:
    """Apply migrations, then destructively reset and reseed demo data."""
    applied = apply_migrations(connection)
    with connection.transaction():
        completed_steps = seeds.reset_demo_database(connection)
    return applied, completed_steps


def format_status(statuses: Iterable[MigrationStatus]) -> str:
    """Format migration status rows for CLI output."""
    lines = []
    for status in statuses:
        marker = "applied" if status.applied else "pending"
        lines.append(f"{status.migration_id}: {marker} - {status.description}")
    return "\n".join(lines) if lines else "No migrations discovered."


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for database migration operations."""
    parser = argparse.ArgumentParser(description="Manage RefundsAI database migrations.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("apply", help="Apply pending schema migrations.")
    subparsers.add_parser("status", help="Show migration application status.")
    subparsers.add_parser("seed", help="Run idempotent seed data steps.")
    subparsers.add_parser(
        "reset-demo",
        help=(
            "Development-only destructive reset: apply migrations, purge demo data, "
            "and reseed from today's date. Requires REFUNDSAI_ALLOW_DEMO_DB_RESET=true."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the migration CLI."""
    args = build_parser().parse_args(argv)

    with connect(get_settings()) as connection:
        if args.command == "apply":
            applied = apply_migrations(connection)
            if applied:
                for migration in applied:
                    print(f"Applied {migration.migration_id}: {migration.description}")
            else:
                print("No pending migrations.")
            return 0

        if args.command == "status":
            print(format_status(get_migration_statuses(connection)))
            return 0

        if args.command == "seed":
            completed_steps = run_seed_steps(connection)
            if completed_steps:
                for step in completed_steps:
                    print(f"Seeded {step}")
            else:
                print("No seed steps configured.")
            return 0

        if args.command == "reset-demo":
            applied, completed_steps = reset_demo_database(connection)
            if applied:
                for migration in applied:
                    print(f"Applied {migration.migration_id}: {migration.description}")
            else:
                print("No pending migrations.")
            for step in completed_steps:
                print(f"Demo reset {step}")
            return 0

    raise MigrationError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
