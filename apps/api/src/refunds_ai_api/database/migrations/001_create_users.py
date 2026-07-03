"""Create identity-anchor users."""

from psycopg import Connection

MIGRATION_ID = "001_create_users"
DESCRIPTION = "Create identity-anchor users table and backend-only security policy."


def upgrade(connection: Connection) -> None:
    """Apply the users table migration."""
    create_table(connection)
    create_indexes(connection)
    enable_rls(connection)
    create_policies(connection)


def create_table(connection: Connection) -> None:
    """Create the human identity anchor without auth or CRM metadata."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.users (
                id uuid primary key,
                first_name text not null,
                last_name text not null,
                created_at timestamptz not null default now()
            )
            """
        )


def create_indexes(connection: Connection) -> None:
    """No-op: the primary key already creates the required users lookup index."""
    return None


def enable_rls(connection: Connection) -> None:
    """Enable row-level security for application users."""
    with connection.cursor() as cursor:
        cursor.execute("alter table public.users enable row level security")


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
                        and tablename = 'users'
                        and policyname = 'users_service_role_all'
                ) then
                    create policy users_service_role_all
                    on public.users
                    for all
                    to service_role
                    using (true)
                    with check (true);
                end if;
            end
            $$;
            """
        )
