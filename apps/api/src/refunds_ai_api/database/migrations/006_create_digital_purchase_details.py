"""Create digital purchase details."""

from psycopg import Connection

MIGRATION_ID = "006_create_digital_purchase_details"
DESCRIPTION = "Create digital purchase details table and backend-only security policy."


def upgrade(connection: Connection) -> None:
    """Apply the digital purchase details table migration."""
    create_table(connection)
    create_indexes(connection)
    enable_rls(connection)
    create_policies(connection)


def create_table(connection: Connection) -> None:
    """Create mutable state for digital purchase fulfillment."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.digital_purchase_details (
                id uuid primary key,
                purchase_id uuid unique not null
                    references public.purchases(id) on delete cascade,
                issued_code text unique not null,
                code_redeemed boolean not null default false,
                code_redeemed_at timestamptz null,
                code_invalidated_at timestamptz null,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now()
            )
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create one-to-one and issued-code lookup indexes."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create unique index if not exists digital_purchase_details_purchase_id_idx
            on public.digital_purchase_details (purchase_id)
            """
        )
        cursor.execute(
            """
            create unique index if not exists digital_purchase_details_issued_code_idx
            on public.digital_purchase_details (issued_code)
            """
        )


def enable_rls(connection: Connection) -> None:
    """Enable row-level security for digital purchase details."""
    with connection.cursor() as cursor:
        cursor.execute("alter table public.digital_purchase_details enable row level security")


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
                        and tablename = 'digital_purchase_details'
                        and policyname = 'digital_purchase_details_service_role_all'
                ) then
                    create policy digital_purchase_details_service_role_all
                    on public.digital_purchase_details
                    for all
                    to service_role
                    using (true)
                    with check (true);
                end if;
            end
            $$;
            """
        )
