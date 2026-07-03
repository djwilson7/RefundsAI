"""Expand purchase detail tables with authoritative refund lifecycle fields."""

from psycopg import Connection

MIGRATION_ID = "009_expand_purchase_details_for_refund_state"
DESCRIPTION = "Add refund lifecycle fields to purchase detail tables."


def upgrade(connection: Connection) -> None:
    """Apply refund lifecycle detail-table expansion."""
    narrow_purchase_status(connection)
    alter_digital_purchase_details(connection)
    alter_physical_purchase_details(connection)
    alter_subscription_purchase_details(connection)
    create_indexes(connection)


def narrow_purchase_status(connection: Connection) -> None:
    """Keep refund lifecycle state out of the shared purchases table."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            alter table public.purchases
                drop constraint if exists purchases_status_check
            """
        )
        cursor.execute(
            """
            alter table public.purchases
                add constraint purchases_status_check
                check (status in ('completed', 'cancelled'))
            """
        )


def alter_digital_purchase_details(connection: Connection) -> None:
    """Add digital entitlement and refund-blocking state."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            alter table public.digital_purchase_details
                add column if not exists code_delivered_at timestamptz null,
                add column if not exists refund_lock_reason text null
            """
        )
        cursor.execute(
            """
            do $$
            begin
                if not exists (
                    select 1
                    from pg_constraint
                    where conname = 'digital_purchase_details_redeemed_at_check'
                ) then
                    alter table public.digital_purchase_details
                        add constraint digital_purchase_details_redeemed_at_check
                        check (
                            code_redeemed = false
                            or code_redeemed_at is not null
                        );
                end if;
            end
            $$;
            """
        )


def alter_physical_purchase_details(connection: Connection) -> None:
    """Add physical return lifecycle state."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            alter table public.physical_purchase_details
                add column if not exists return_requested_at timestamptz null,
                add column if not exists return_authorized_at timestamptz null,
                add column if not exists return_received_at timestamptz null,
                add column if not exists return_rejected_at timestamptz null,
                add column if not exists return_rejection_reason text null
            """
        )
        cursor.execute(
            """
            alter table public.physical_purchase_details
                drop constraint if exists physical_purchase_details_return_status_check
            """
        )
        cursor.execute(
            """
            alter table public.physical_purchase_details
                add constraint physical_purchase_details_return_status_check
                check (return_status in (
                    'not_requested',
                    'requested',
                    'authorized',
                    'accepted_by_carrier',
                    'received',
                    'rejected',
                    'cancelled'
                ))
            """
        )
        cursor.execute(
            """
            do $$
            begin
                if not exists (
                    select 1
                    from pg_constraint
                    where conname = 'physical_purchase_details_rejection_check'
                ) then
                    alter table public.physical_purchase_details
                        add constraint physical_purchase_details_rejection_check
                        check (
                            return_status <> 'rejected'
                            or (
                                return_rejected_at is not null
                                and return_rejection_reason is not null
                            )
                        );
                end if;
            end
            $$;
            """
        )


def alter_subscription_purchase_details(connection: Connection) -> None:
    """Add subscription cancellation and refund-proration state."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            alter table public.subscription_purchase_details
                add column if not exists service_ended_at timestamptz null,
                add column if not exists auto_renew boolean not null default true,
                add column if not exists refund_proration_mode text not null default 'none'
            """
        )
        cursor.execute(
            """
            do $$
            begin
                if not exists (
                    select 1
                    from pg_constraint
                    where conname = 'subscription_purchase_details_proration_check'
                ) then
                    alter table public.subscription_purchase_details
                        add constraint subscription_purchase_details_proration_check
                        check (refund_proration_mode in ('none', 'full', 'prorated'));
                end if;
            end
            $$;
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create lookup indexes for refund lifecycle state."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create index if not exists digital_purchase_details_refund_lock_reason_idx
            on public.digital_purchase_details (refund_lock_reason)
            """
        )
        cursor.execute(
            """
            create index if not exists physical_purchase_details_return_requested_at_idx
            on public.physical_purchase_details (return_requested_at)
            """
        )
        cursor.execute(
            """
            create index if not exists subscription_purchase_details_proration_mode_idx
            on public.subscription_purchase_details (refund_proration_mode)
            """
        )
