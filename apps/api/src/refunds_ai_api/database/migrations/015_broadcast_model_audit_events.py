"""Broadcast model audit events through PostgreSQL notifications."""

from psycopg import Connection

MIGRATION_ID = "015_broadcast_model_audit_events"
DESCRIPTION = "Broadcast model audit event inserts for realtime admin streams."

MODEL_AUDIT_EVENTS_CHANNEL = "model_audit_events"


def upgrade(connection: Connection) -> None:
    """Install the audit-event notification function and trigger."""
    create_broadcast_function(connection)
    create_broadcast_trigger(connection)


def create_broadcast_function(connection: Connection) -> None:
    """Create the database broadcaster for inserted model audit events."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            create or replace function public.broadcast_model_audit_event()
            returns trigger
            language plpgsql
            security definer
            set search_path = public
            as $$
            declare
                lookup_row record;
                payload jsonb;
            begin
                select
                    display_name,
                    category,
                    description,
                    display_order
                into lookup_row
                from public.model_audit_event_lookup
                where event_key = new.event_key;

                payload := jsonb_build_object(
                    'id', new.id,
                    'session_id', new.session_id,
                    'trace_id', new.trace_id,
                    'sequence_number', new.sequence_number,
                    'event_key', new.event_key,
                    'display_name', lookup_row.display_name,
                    'category', lookup_row.category,
                    'description', lookup_row.description,
                    'display_order', lookup_row.display_order,
                    'workflow_kind', new.workflow_kind,
                    'tool_name', new.tool_name,
                    'summary', new.summary,
                    'input_json', new.input_json,
                    'output_json', new.output_json,
                    'metadata_json', new.metadata_json,
                    'created_at', new.created_at
                );

                perform pg_notify('{MODEL_AUDIT_EVENTS_CHANNEL}', payload::text);
                return new;
            end
            $$;
            """
        )


def create_broadcast_trigger(connection: Connection) -> None:
    """Create an after-insert trigger that broadcasts audit events."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            drop trigger if exists model_audit_events_broadcast_after_insert
            on public.model_audit_events
            """
        )
        cursor.execute(
            """
            create trigger model_audit_events_broadcast_after_insert
            after insert on public.model_audit_events
            for each row
            execute function public.broadcast_model_audit_event()
            """
        )
