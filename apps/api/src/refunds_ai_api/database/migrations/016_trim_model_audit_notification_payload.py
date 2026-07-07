"""Trim model audit notification payloads for reliable realtime delivery."""

from psycopg import Connection

MIGRATION_ID = "016_trim_model_audit_notification_payload"
DESCRIPTION = "Trim model audit pg_notify payloads to metadata fields."

MODEL_AUDIT_EVENTS_CHANNEL = "model_audit_events"


def upgrade(connection: Connection) -> None:
    """Replace the audit event broadcaster with a compact notification payload."""
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
                    'created_at', new.created_at
                );

                perform pg_notify('{MODEL_AUDIT_EVENTS_CHANNEL}', payload::text);
                return new;
            end
            $$;
            """
        )
