"""Create migration bookkeeping and required PostgreSQL extensions."""

from psycopg import Connection

MIGRATION_ID = "000_schema_foundation"
DESCRIPTION = "Create schema_migrations table and required PostgreSQL extensions."


def upgrade(connection: Connection) -> None:
    """Apply the schema foundation migration."""
    create_extensions(connection)
    create_table(connection)
    create_indexes(connection)
    enable_rls(connection)
    create_policies(connection)


def create_extensions(connection: Connection) -> None:
    """Create PostgreSQL extensions expected by future schema migrations."""
    with connection.cursor() as cursor:
        cursor.execute('create extension if not exists "pgcrypto"')


def create_table(connection: Connection) -> None:
    """Create the internal schema migration bookkeeping table."""
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


def create_indexes(connection: Connection) -> None:
    """Create lookup indexes for schema migration metadata."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create index if not exists idx_schema_migrations_applied_at
            on schema_migrations (applied_at)
            """
        )


def enable_rls(connection: Connection) -> None:
    """No-op: schema_migrations is internal metadata, not business data."""
    return None


def create_policies(connection: Connection) -> None:
    """No-op: schema_migrations is internal metadata, not business data."""
    return None
