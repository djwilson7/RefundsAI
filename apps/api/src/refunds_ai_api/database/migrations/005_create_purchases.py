"""Create customer purchases."""

from psycopg import Connection

MIGRATION_ID = "005_create_purchases"
DESCRIPTION = "Create purchases table and backend-only security policy."


def upgrade(connection: Connection) -> None:
    """Apply the purchases table migration."""
    create_table(connection)
    create_indexes(connection)
    enable_rls(connection)
    create_policies(connection)


def create_table(connection: Connection) -> None:
    """Create customer-owned purchase history records."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.purchases (
                id uuid primary key,
                user_id uuid not null references public.users(id) on delete cascade,
                product_id uuid not null references public.products(id),
                order_number text not null,
                purchase_type text not null,
                amount_cents integer not null,
                purchased_at timestamptz not null,
                status text not null default 'completed',
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now(),
                constraint purchases_purchase_type_check
                    check (purchase_type in ('physical', 'digital', 'subscription')),
                constraint purchases_status_check
                    check (status in (
                        'completed',
                        'refund_pending',
                        'refunded',
                        'cancelled'
                    )),
                constraint purchases_amount_cents_check
                    check (amount_cents >= 0)
            )
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create purchase lookup and history indexes."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create unique index if not exists purchases_order_number_idx
            on public.purchases (order_number)
            """
        )
        cursor.execute(
            """
            create index if not exists purchases_user_id_idx
            on public.purchases (user_id)
            """
        )
        cursor.execute(
            """
            create index if not exists purchases_product_id_idx
            on public.purchases (product_id)
            """
        )
        cursor.execute(
            """
            create index if not exists purchases_purchase_type_idx
            on public.purchases (purchase_type)
            """
        )
        cursor.execute(
            """
            create index if not exists purchases_status_idx
            on public.purchases (status)
            """
        )
        cursor.execute(
            """
            create index if not exists purchases_purchased_at_idx
            on public.purchases (purchased_at desc)
            """
        )
        cursor.execute(
            """
            create index if not exists purchases_user_purchased_at_idx
            on public.purchases (user_id, purchased_at desc)
            """
        )


def enable_rls(connection: Connection) -> None:
    """Enable row-level security for customer purchases."""
    with connection.cursor() as cursor:
        cursor.execute("alter table public.purchases enable row level security")


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
                        and tablename = 'purchases'
                        and policyname = 'purchases_service_role_all'
                ) then
                    create policy purchases_service_role_all
                    on public.purchases
                    for all
                    to service_role
                    using (true)
                    with check (true);
                end if;
            end
            $$;
            """
        )
