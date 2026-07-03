"""Add refund workflow preparation state."""

from psycopg import Connection

MIGRATION_ID = "011_add_refund_workflow_state"
DESCRIPTION = "Add refund workflow status and physical return preparation fields."


def upgrade(connection: Connection) -> None:
    """Apply refund workflow state expansion."""
    expand_purchase_status(connection)
    add_physical_preparation_fields(connection)
    backfill_purchase_statuses(connection)
    create_indexes(connection)


def expand_purchase_status(connection: Connection) -> None:
    """Allow purchase status to summarize refund workflow state."""
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
                check (status in (
                    'completed',
                    'subscribed',
                    'redeemed',
                    'refund_pending',
                    'refunded',
                    'cancelled'
                ))
            """
        )


def add_physical_preparation_fields(connection: Connection) -> None:
    """Add simulated return label/barcode preparation state."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            alter table public.physical_purchase_details
                add column if not exists return_barcode_generated boolean not null default false,
                add column if not exists return_label_created_at timestamptz null
            """
        )


def backfill_purchase_statuses(connection: Connection) -> None:
    """Derive workflow summary status from existing seeded detail state."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            update public.purchases purchases
            set status = 'redeemed',
                updated_at = now()
            from public.digital_purchase_details details
            where details.purchase_id = purchases.id
                and purchases.purchase_type = 'digital'
                and details.code_redeemed = true
                and purchases.status = 'completed'
            """
        )
        cursor.execute(
            """
            update public.purchases purchases
            set status = 'subscribed',
                updated_at = now()
            from public.subscription_purchase_details details
            where details.purchase_id = purchases.id
                and purchases.purchase_type = 'subscription'
                and details.period_start <= now()
                and details.period_end >= now()
                and details.cancelled_at is null
                and purchases.status = 'completed'
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create lookup indexes for physical return preparation state."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create index if not exists physical_purchase_details_return_label_created_at_idx
            on public.physical_purchase_details (return_label_created_at)
            """
        )
