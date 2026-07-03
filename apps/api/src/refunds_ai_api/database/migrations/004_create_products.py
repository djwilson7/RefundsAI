"""Create catalog products."""

from psycopg import Connection

MIGRATION_ID = "004_create_products"
DESCRIPTION = "Create products catalog table and backend-only security policy."


def upgrade(connection: Connection) -> None:
    """Apply the products table migration."""
    create_table(connection)
    create_indexes(connection)
    enable_rls(connection)
    create_policies(connection)


def create_table(connection: Connection) -> None:
    """Create catalog reference data for items that can be purchased."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.products (
                id uuid primary key,
                name text not null,
                sku text not null,
                product_type text not null,
                base_price_cents integer not null,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now(),
                constraint products_product_type_check
                    check (product_type in ('physical', 'digital', 'subscription')),
                constraint products_base_price_cents_check
                    check (base_price_cents >= 0)
            )
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create product lookup indexes."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create unique index if not exists products_sku_idx
            on public.products (sku)
            """
        )
        cursor.execute(
            """
            create index if not exists products_product_type_idx
            on public.products (product_type)
            """
        )


def enable_rls(connection: Connection) -> None:
    """Enable row-level security for catalog products."""
    with connection.cursor() as cursor:
        cursor.execute("alter table public.products enable row level security")


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
                        and tablename = 'products'
                        and policyname = 'products_service_role_all'
                ) then
                    create policy products_service_role_all
                    on public.products
                    for all
                    to service_role
                    using (true)
                    with check (true);
                end if;
            end
            $$;
            """
        )
