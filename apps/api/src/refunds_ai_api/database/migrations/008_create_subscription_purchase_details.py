"""Create subscription purchase details."""

from psycopg import Connection

MIGRATION_ID = "008_create_subscription_purchase_details"
DESCRIPTION = "Create subscription purchase details table and backend-only security policy."


def upgrade(connection: Connection) -> None:
    """Apply the subscription purchase details table migration."""
    create_table(connection)
    create_indexes(connection)
    enable_rls(connection)
    create_policies(connection)


def create_table(connection: Connection) -> None:
    """Create mutable state for subscription purchase periods."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.subscription_purchase_details (
                id uuid primary key,
                purchase_id uuid unique not null
                    references public.purchases(id) on delete cascade,
                period_start timestamptz not null,
                period_end timestamptz not null,
                cancelled_at timestamptz null,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now(),
                constraint subscription_purchase_details_period_check
                    check (period_end > period_start)
            )
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create one-to-one and period range lookup indexes."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create unique index if not exists subscription_purchase_details_purchase_id_idx
            on public.subscription_purchase_details (purchase_id)
            """
        )
        cursor.execute(
            """
            create index if not exists subscription_purchase_details_period_idx
            on public.subscription_purchase_details (period_start, period_end)
            """
        )


def enable_rls(connection: Connection) -> None:
    """Enable row-level security for subscription purchase details."""
    with connection.cursor() as cursor:
        cursor.execute(
            "alter table public.subscription_purchase_details enable row level security"
        )


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
                        and tablename = 'subscription_purchase_details'
                        and policyname = 'subscription_purchase_details_service_role_all'
                ) then
                    create policy subscription_purchase_details_service_role_all
                    on public.subscription_purchase_details
                    for all
                    to service_role
                    using (true)
                    with check (true);
                end if;
            end
            $$;
            """
        )
