"""Create mock-interface role definitions."""

from psycopg import Connection

MIGRATION_ID = "002_create_roles"
DESCRIPTION = "Create role definitions table and backend-only security policy."


def upgrade(connection: Connection) -> None:
    """Apply the roles table migration."""
    create_table(connection)
    create_indexes(connection)
    enable_rls(connection)
    create_policies(connection)


def create_table(connection: Connection) -> None:
    """Create lightweight role definitions, not a permissions matrix."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.roles (
                id uuid primary key,
                key text unique not null,
                name text not null
            )
            """
        )


def create_indexes(connection: Connection) -> None:
    """No-op: primary key and unique role key constraints create required indexes."""
    return None


def enable_rls(connection: Connection) -> None:
    """Enable row-level security for application roles."""
    with connection.cursor() as cursor:
        cursor.execute("alter table public.roles enable row level security")


def create_policies(connection: Connection) -> None:
    """Allow backend service-role access while denying direct anonymous access."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            do $$
            begin
                if not exists (
                    select 1
                    from pg_policies
                    where schemaname = 'public'
                        and tablename = 'roles'
                        and policyname = 'roles_service_role_all'
                ) then
                    create policy roles_service_role_all
                    on public.roles
                    for all
                    to service_role
                    using (true)
                    with check (true);
                end if;
            end
            $$;
            """
        )
