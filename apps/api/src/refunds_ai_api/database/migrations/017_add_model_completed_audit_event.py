"""Add the model-call lifecycle completion audit event."""

from psycopg import Connection

MIGRATION_ID = "017_add_model_completed_audit_event"
DESCRIPTION = "Add a dedicated model-call lifecycle event lookup key."


def upgrade(connection: Connection) -> None:
    """Seed the model lifecycle event used for per-call usage and latency."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.model_audit_event_lookup (
                event_key,
                display_name,
                category,
                description,
                display_order
            )
            values (
                'MODEL_COMPLETED',
                'Model call',
                'response',
                'One model provider invocation completed with usage and latency.',
                12
            )
            on conflict (event_key) do update
            set display_name = excluded.display_name,
                category = excluded.category,
                description = excluded.description,
                display_order = excluded.display_order,
                is_active = true,
                updated_at = now()
            """
        )
