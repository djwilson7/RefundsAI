"""Create physical purchase details."""

from psycopg import Connection

MIGRATION_ID = "007_create_physical_purchase_details"
DESCRIPTION = "Create physical purchase details table and backend-only security policy."


def upgrade(connection: Connection) -> None:
    """Apply the physical purchase details table migration."""
    create_table(connection)
    create_indexes(connection)
    create_delivery_window_trigger(connection)
    enable_rls(connection)
    create_policies(connection)


def create_table(connection: Connection) -> None:
    """Create mutable state for physical delivery and return flow."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.physical_purchase_details (
                id uuid primary key,
                purchase_id uuid unique not null
                    references public.purchases(id) on delete cascade,
                scheduled_delivery_at timestamptz not null,
                delivered_at timestamptz null,
                return_status text not null default 'not_requested',
                carrier text null,
                tracking_number text null,
                accepted_by_carrier_at timestamptz null,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now(),
                constraint physical_purchase_details_return_status_check
                    check (return_status in (
                        'not_requested',
                        'requested',
                        'accepted_by_carrier',
                        'cancelled'
                    ))
            )
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create one-to-one and return-status lookup indexes."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create unique index if not exists physical_purchase_details_purchase_id_idx
            on public.physical_purchase_details (purchase_id)
            """
        )
        cursor.execute(
            """
            create index if not exists physical_purchase_details_return_status_idx
            on public.physical_purchase_details (return_status)
            """
        )


def create_delivery_window_trigger(connection: Connection) -> None:
    """Validate delivery timestamps against the owning purchase timestamp."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create or replace function
                public.validate_physical_purchase_details_delivery_window()
            returns trigger
            language plpgsql
            security definer
            set search_path = public
            as $$
            declare
                purchase_purchased_at timestamptz;
            begin
                select purchases.purchased_at
                into purchase_purchased_at
                from public.purchases
                where purchases.id = new.purchase_id;

                if purchase_purchased_at is null then
                    raise exception
                        'Physical purchase detail references an unknown purchase.';
                end if;

                if new.scheduled_delivery_at <= purchase_purchased_at then
                    raise exception
                        'scheduled_delivery_at must be after purchased_at.';
                end if;

                if new.scheduled_delivery_at < purchase_purchased_at + interval '2 days'
                    or new.scheduled_delivery_at > purchase_purchased_at + interval '7 days'
                then
                    raise exception
                        'scheduled_delivery_at must be 2 to 7 days after purchased_at.';
                end if;

                if new.delivered_at is not null
                    and new.delivered_at <= purchase_purchased_at
                then
                    raise exception
                        'delivered_at must be after purchased_at when present.';
                end if;

                if new.delivered_at is not null
                    and new.delivered_at > new.scheduled_delivery_at
                then
                    raise exception
                        'delivered_at must be on or before scheduled_delivery_at when present.';
                end if;

                if new.delivered_at is not null and new.delivered_at > now() then
                    raise exception 'delivered_at cannot be in the future.';
                end if;

                return new;
            end;
            $$;
            """
        )
        cursor.execute(
            """
            drop trigger if exists validate_physical_purchase_details_delivery_window
            on public.physical_purchase_details
            """
        )
        cursor.execute(
            """
            create trigger validate_physical_purchase_details_delivery_window
            before insert or update of purchase_id, scheduled_delivery_at, delivered_at
            on public.physical_purchase_details
            for each row
            execute function public.validate_physical_purchase_details_delivery_window()
            """
        )


def enable_rls(connection: Connection) -> None:
    """Enable row-level security for physical purchase details."""
    with connection.cursor() as cursor:
        cursor.execute("alter table public.physical_purchase_details enable row level security")


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
                        and tablename = 'physical_purchase_details'
                        and policyname = 'physical_purchase_details_service_role_all'
                ) then
                    create policy physical_purchase_details_service_role_all
                    on public.physical_purchase_details
                    for all
                    to service_role
                    using (true)
                    with check (true);
                end if;
            end
            $$;
            """
        )
