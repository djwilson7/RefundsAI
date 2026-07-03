"""Create user-to-role assignments for the identity layer."""

from psycopg import Connection

MIGRATION_ID = "003_create_user_roles"
DESCRIPTION = "Create user_roles table and backend-only security policy."


def upgrade(connection: Connection) -> None:
    """Apply the user_roles table migration."""
    create_table(connection)
    create_indexes(connection)
    enable_rls(connection)
    create_policies(connection)


def create_table(connection: Connection) -> None:
    """Create many-to-many role assignments separate from user identity."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.user_roles (
                user_id uuid references public.users(id) on delete cascade,
                role_id uuid references public.roles(id) on delete cascade,
                created_at timestamptz not null default now(),
                primary key (user_id, role_id)
            )
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create the role lookup index not covered by the composite primary key."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create index if not exists idx_user_roles_role_id
            on public.user_roles (role_id)
            """
        )


def enable_rls(connection: Connection) -> None:
    """Enable row-level security for user role assignments."""
    with connection.cursor() as cursor:
        cursor.execute("alter table public.user_roles enable row level security")


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
                        and tablename = 'user_roles'
                        and policyname = 'user_roles_service_role_all'
                ) then
                    create policy user_roles_service_role_all
                    on public.user_roles
                    for all
                    to service_role
                    using (true)
                    with check (true);
                end if;
            end
            $$;
            """
        )
