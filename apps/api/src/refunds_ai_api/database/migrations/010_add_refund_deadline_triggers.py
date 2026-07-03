"""Add database-managed refund deadline triggers."""

from psycopg import Connection

MIGRATION_ID = "010_add_refund_deadline_triggers"
DESCRIPTION = "Add refund deadline fields and triggers to purchase detail tables."


def upgrade(connection: Connection) -> None:
    """Apply database-managed refund deadline automation."""
    add_deadline_columns(connection)
    create_trigger_functions(connection)
    backfill_deadline_columns(connection)
    require_deadline_columns(connection)
    create_triggers(connection)
    create_indexes(connection)


def add_deadline_columns(connection: Connection) -> None:
    """Add deadline columns before backfilling existing detail records."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            alter table public.digital_purchase_details
                add column if not exists refund_window_expires_at timestamptz null
            """
        )
        cursor.execute(
            """
            alter table public.physical_purchase_details
                add column if not exists refund_window_expires_at timestamptz null
            """
        )
        cursor.execute(
            """
            alter table public.subscription_purchase_details
                add column if not exists full_refund_window_expires_at timestamptz null,
                add column if not exists refund_window_expires_at timestamptz null
            """
        )


def create_trigger_functions(connection: Connection) -> None:
    """Create trigger functions that derive refund fields from purchase state."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create or replace function public.set_digital_purchase_refund_fields()
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
                    raise exception 'Digital purchase detail references an unknown purchase.';
                end if;

                new.refund_window_expires_at := purchase_purchased_at + interval '15 days';
                new.code_delivered_at := coalesce(
                    new.code_delivered_at,
                    purchase_purchased_at + interval '5 minutes'
                );

                if new.code_redeemed then
                    new.refund_lock_reason := coalesce(
                        new.refund_lock_reason,
                        'code_redeemed'
                    );
                elsif new.refund_lock_reason = 'code_redeemed' then
                    new.refund_lock_reason := null;
                end if;

                return new;
            end;
            $$;
            """
        )
        cursor.execute(
            """
            create or replace function public.set_physical_purchase_refund_fields()
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
                    raise exception 'Physical purchase detail references an unknown purchase.';
                end if;

                new.refund_window_expires_at := purchase_purchased_at + interval '30 days';

                return new;
            end;
            $$;
            """
        )
        cursor.execute(
            """
            create or replace function public.set_subscription_purchase_refund_fields()
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
                    raise exception 'Subscription purchase detail references an unknown purchase.';
                end if;

                new.full_refund_window_expires_at :=
                    purchase_purchased_at + interval '48 hours';
                new.refund_window_expires_at := new.period_end;

                if new.cancelled_at is not null then
                    new.auto_renew := false;
                    new.service_ended_at := coalesce(new.service_ended_at, new.cancelled_at);
                end if;

                return new;
            end;
            $$;
            """
        )


def backfill_deadline_columns(connection: Connection) -> None:
    """Backfill generated fields for existing seeded detail records."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            update public.digital_purchase_details details
            set refund_window_expires_at = purchases.purchased_at + interval '15 days',
                code_delivered_at = coalesce(
                    details.code_delivered_at,
                    purchases.purchased_at + interval '5 minutes'
                ),
                refund_lock_reason = case
                    when details.code_redeemed then coalesce(
                        details.refund_lock_reason,
                        'code_redeemed'
                    )
                    when details.refund_lock_reason = 'code_redeemed' then null
                    else details.refund_lock_reason
                end
            from public.purchases
            where purchases.id = details.purchase_id
            """
        )
        cursor.execute(
            """
            update public.physical_purchase_details details
            set refund_window_expires_at = purchases.purchased_at + interval '30 days'
            from public.purchases
            where purchases.id = details.purchase_id
            """
        )
        cursor.execute(
            """
            update public.subscription_purchase_details details
            set full_refund_window_expires_at = purchases.purchased_at + interval '48 hours',
                refund_window_expires_at = details.period_end,
                auto_renew = case
                    when details.cancelled_at is not null then false
                    else details.auto_renew
                end,
                service_ended_at = case
                    when details.cancelled_at is not null then coalesce(
                        details.service_ended_at,
                        details.cancelled_at
                    )
                    else details.service_ended_at
                end
            from public.purchases
            where purchases.id = details.purchase_id
            """
        )


def require_deadline_columns(connection: Connection) -> None:
    """Require deadline columns after existing data is backfilled."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            alter table public.digital_purchase_details
                alter column refund_window_expires_at set not null,
                alter column code_delivered_at set not null
            """
        )
        cursor.execute(
            """
            alter table public.physical_purchase_details
                alter column refund_window_expires_at set not null
            """
        )
        cursor.execute(
            """
            alter table public.subscription_purchase_details
                alter column full_refund_window_expires_at set not null,
                alter column refund_window_expires_at set not null
            """
        )


def create_triggers(connection: Connection) -> None:
    """Attach deadline trigger functions to each purchase detail table."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            drop trigger if exists set_digital_purchase_refund_fields
            on public.digital_purchase_details
            """
        )
        cursor.execute(
            """
            create trigger set_digital_purchase_refund_fields
            before insert or update of
                purchase_id,
                code_redeemed,
                code_delivered_at,
                refund_lock_reason
            on public.digital_purchase_details
            for each row
            execute function public.set_digital_purchase_refund_fields()
            """
        )
        cursor.execute(
            """
            drop trigger if exists set_physical_purchase_refund_fields
            on public.physical_purchase_details
            """
        )
        cursor.execute(
            """
            create trigger set_physical_purchase_refund_fields
            before insert or update of purchase_id
            on public.physical_purchase_details
            for each row
            execute function public.set_physical_purchase_refund_fields()
            """
        )
        cursor.execute(
            """
            drop trigger if exists set_subscription_purchase_refund_fields
            on public.subscription_purchase_details
            """
        )
        cursor.execute(
            """
            create trigger set_subscription_purchase_refund_fields
            before insert or update of
                purchase_id,
                period_end,
                cancelled_at,
                service_ended_at,
                auto_renew
            on public.subscription_purchase_details
            for each row
            execute function public.set_subscription_purchase_refund_fields()
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create deadline lookup indexes for policy evaluation."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create index if not exists digital_purchase_details_refund_window_idx
            on public.digital_purchase_details (refund_window_expires_at)
            """
        )
        cursor.execute(
            """
            create index if not exists physical_purchase_details_refund_window_idx
            on public.physical_purchase_details (refund_window_expires_at)
            """
        )
        cursor.execute(
            """
            create index if not exists subscription_purchase_details_refund_window_idx
            on public.subscription_purchase_details (refund_window_expires_at)
            """
        )
        cursor.execute(
            """
            create index if not exists subscription_purchase_details_full_refund_window_idx
            on public.subscription_purchase_details (full_refund_window_expires_at)
            """
        )
