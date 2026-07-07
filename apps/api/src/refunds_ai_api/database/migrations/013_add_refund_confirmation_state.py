"""Add persisted refund confirmation facts to purchase detail tables."""

from psycopg import Connection

MIGRATION_ID = "013_add_refund_confirmation_state"
DESCRIPTION = "Add refund confirmation authorization facts to purchase details."

DETAIL_TABLES = (
    "digital_purchase_details",
    "physical_purchase_details",
    "subscription_purchase_details",
)


def upgrade(connection: Connection) -> None:
    """Apply refund confirmation state columns, constraints, and indexes."""
    for table_name in DETAIL_TABLES:
        add_confirmation_fields(connection, table_name)
        add_confirmation_constraints(connection, table_name)
        create_confirmation_indexes(connection, table_name)


def add_confirmation_fields(connection: Connection, table_name: str) -> None:
    """Add persisted customer confirmation fields to one detail table."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            alter table public.{table_name}
                add column if not exists refund_confirmation_granted boolean not null default false,
                add column if not exists refund_confirmation_message text null,
                add column if not exists refund_confirmation_granted_at timestamptz null,
                add column if not exists refund_confirmation_expected_command text null,
                add column if not exists refund_confirmation_matched boolean not null default false,
                add column if not exists refund_confirmation_source text null,
                add column if not exists refund_confirmation_customer_id uuid null
                    references public.users(id),
                add column if not exists refund_confirmation_purchase_id uuid null
                    references public.purchases(id),
                add column if not exists refund_confirmation_consumed_at timestamptz null,
                add column if not exists refund_confirmation_consumed_by_action text null
            """
        )


def add_confirmation_constraints(connection: Connection, table_name: str) -> None:
    """Constrain confirmation and consumption facts for one detail table."""
    confirmation_constraint = f"{table_name}_refund_confirmation_granted_check"
    consumed_constraint = f"{table_name}_refund_confirmation_consumed_check"
    action_constraint = f"{table_name}_refund_confirmation_consumed_action_check"
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            alter table public.{table_name}
                drop constraint if exists {confirmation_constraint}
            """
        )
        cursor.execute(
            f"""
            alter table public.{table_name}
                add constraint {confirmation_constraint}
                check (
                    refund_confirmation_granted = false
                    or (
                        refund_confirmation_message is not null
                        and refund_confirmation_granted_at is not null
                        and refund_confirmation_expected_command is not null
                        and refund_confirmation_matched = true
                        and refund_confirmation_source is not null
                        and refund_confirmation_customer_id is not null
                        and refund_confirmation_purchase_id = purchase_id
                    )
                )
            """
        )
        cursor.execute(
            f"""
            alter table public.{table_name}
                drop constraint if exists {consumed_constraint}
            """
        )
        cursor.execute(
            f"""
            alter table public.{table_name}
                add constraint {consumed_constraint}
                check (
                    (
                        refund_confirmation_consumed_at is null
                        and refund_confirmation_consumed_by_action is null
                    )
                    or (
                        refund_confirmation_consumed_at is not null
                        and refund_confirmation_consumed_by_action is not null
                    )
                )
            """
        )
        cursor.execute(
            f"""
            alter table public.{table_name}
                drop constraint if exists {action_constraint}
            """
        )
        cursor.execute(
            f"""
            alter table public.{table_name}
                add constraint {action_constraint}
                check (
                    refund_confirmation_consumed_by_action is null
                    or refund_confirmation_consumed_by_action in (
                        'request_refund',
                        'issue_refund'
                    )
                )
            """
        )


def create_confirmation_indexes(connection: Connection, table_name: str) -> None:
    """Create lookup indexes for persisted confirmation state."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            create index if not exists {table_name}_refund_confirmation_customer_idx
            on public.{table_name} (refund_confirmation_customer_id)
            """
        )
        cursor.execute(
            f"""
            create index if not exists {table_name}_refund_confirmation_purchase_idx
            on public.{table_name} (refund_confirmation_purchase_id)
            """
        )
        cursor.execute(
            f"""
            create index if not exists {table_name}_refund_confirmation_granted_idx
            on public.{table_name} (refund_confirmation_granted, refund_confirmation_matched)
            """
        )
