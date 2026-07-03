"""Add persisted refund issue facts to purchases."""

from psycopg import Connection

MIGRATION_ID = "012_add_refund_issued_facts"
DESCRIPTION = "Add refund request and issued refund facts to purchases."


def upgrade(connection: Connection) -> None:
    """Apply refund issue fact columns and constraints."""
    add_refund_fact_fields(connection)
    add_constraints(connection)
    create_indexes(connection)


def add_refund_fact_fields(connection: Connection) -> None:
    """Add purchase-level refund workflow timestamps and issued amount facts."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            alter table public.purchases
                add column if not exists refund_requested_at timestamptz null,
                add column if not exists refunded_at timestamptz null,
                add column if not exists refund_amount_cents integer null,
                add column if not exists refund_outcome text null
            """
        )


def add_constraints(connection: Connection) -> None:
    """Constrain persisted issued refund facts."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            alter table public.purchases
                drop constraint if exists purchases_refund_amount_cents_check
            """
        )
        cursor.execute(
            """
            alter table public.purchases
                add constraint purchases_refund_amount_cents_check
                check (refund_amount_cents is null or refund_amount_cents >= 0)
            """
        )
        cursor.execute(
            """
            alter table public.purchases
                drop constraint if exists purchases_refund_outcome_check
            """
        )
        cursor.execute(
            """
            alter table public.purchases
                add constraint purchases_refund_outcome_check
                check (refund_outcome is null or refund_outcome in ('full', 'prorated'))
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create lookup indexes for refund workflow timestamps."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create index if not exists purchases_refund_requested_at_idx
            on public.purchases (refund_requested_at)
            """
        )
        cursor.execute(
            """
            create index if not exists purchases_refunded_at_idx
            on public.purchases (refunded_at)
            """
        )
