"""Create model audit session, event, and event lookup tables."""

from psycopg import Connection

MIGRATION_ID = "014_create_model_audit_tables"
DESCRIPTION = "Create model audit tables and stable event lookup keys."

EVENT_LOOKUP_ROWS = (
    (
        "REQUEST_RECEIVED",
        "Request received",
        "request",
        "Customer chat request accepted by the backend.",
    ),
    (
        "GRAPH_STARTED",
        "Graph started",
        "routing",
        "AI orchestration graph execution started.",
    ),
    (
        "WORKFLOW_CLASSIFIED",
        "Workflow classified",
        "routing",
        "Conversation object, operation, and workflow family were resolved.",
    ),
    (
        "CONTEXT_RESOLVED",
        "Context resolved",
        "routing",
        "Page, purchase, policy, or result-set context was selected.",
    ),
    (
        "TOOL_REQUESTED",
        "Tool requested",
        "tool",
        "The model or deterministic router requested backend tool data.",
    ),
    (
        "TOOL_STARTED",
        "Tool started",
        "tool",
        "Backend tool execution started.",
    ),
    (
        "TOOL_COMPLETED",
        "Tool completed",
        "tool",
        "Backend tool execution completed.",
    ),
    (
        "VALIDATION_PASSED",
        "Validation passed",
        "validation",
        "A deterministic validation or guard check passed.",
    ),
    (
        "VALIDATION_FAILED",
        "Validation failed",
        "validation",
        "A deterministic validation or guard check failed.",
    ),
    (
        "MUTATION_STARTED",
        "Mutation started",
        "mutation",
        "A confirmation-gated backend mutation started.",
    ),
    (
        "MUTATION_COMPLETED",
        "Mutation completed",
        "mutation",
        "A confirmation-gated backend mutation completed.",
    ),
    (
        "RESPONSE_GENERATED",
        "Response generated",
        "response",
        "The assistant response was generated.",
    ),
    (
        "RESPONSE_RETURNED",
        "Response returned",
        "response",
        "The backend returned the assistant response to the frontend.",
    ),
    (
        "ERROR_RAISED",
        "Error raised",
        "error",
        "An error occurred during audit-tracked execution.",
    ),
)


def upgrade(connection: Connection) -> None:
    """Apply model audit tables, constraints, indexes, policies, and lookup keys."""
    create_event_lookup_table(connection)
    create_sessions_table(connection)
    create_events_table(connection)
    create_indexes(connection)
    enable_rls(connection)
    create_policies(connection)
    seed_event_lookup(connection)


def create_event_lookup_table(connection: Connection) -> None:
    """Create stable event-key metadata for admin timeline rendering."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.model_audit_event_lookup (
                event_key text primary key,
                display_name text not null,
                category text not null,
                description text null,
                display_order integer not null,
                is_active boolean not null default true,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now(),
                constraint model_audit_event_lookup_category_check
                    check (
                        category in (
                            'request',
                            'routing',
                            'tool',
                            'validation',
                            'mutation',
                            'response',
                            'error'
                        )
                    ),
                constraint model_audit_event_lookup_display_order_check
                    check (display_order > 0)
            )
            """
        )


def create_sessions_table(connection: Connection) -> None:
    """Create the parent audit record for one chat request."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.model_audit_sessions (
                id uuid primary key,
                trace_id uuid not null unique,
                conversation_id uuid null,
                customer_id uuid null references public.users(id) on delete set null,
                request_id text null,
                model_name text not null,
                status text not null,
                prompt_tokens integer null,
                completion_tokens integer null,
                total_tokens integer null,
                started_at timestamptz not null default now(),
                completed_at timestamptz null,
                latency_ms integer null,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now(),
                constraint model_audit_sessions_status_check
                    check (status in ('running', 'succeeded', 'failed')),
                constraint model_audit_sessions_prompt_tokens_check
                    check (prompt_tokens is null or prompt_tokens >= 0),
                constraint model_audit_sessions_completion_tokens_check
                    check (completion_tokens is null or completion_tokens >= 0),
                constraint model_audit_sessions_total_tokens_check
                    check (total_tokens is null or total_tokens >= 0),
                constraint model_audit_sessions_latency_ms_check
                    check (latency_ms is null or latency_ms >= 0),
                constraint model_audit_sessions_completed_at_check
                    check (completed_at is null or completed_at >= started_at)
            )
            """
        )


def create_events_table(connection: Connection) -> None:
    """Create the ordered event timeline for a model audit session."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create table if not exists public.model_audit_events (
                id uuid primary key,
                session_id uuid not null
                    references public.model_audit_sessions(id) on delete cascade,
                trace_id uuid not null,
                sequence_number integer not null,
                event_key text not null
                    references public.model_audit_event_lookup(event_key),
                workflow_kind text null,
                tool_name text null,
                summary text null,
                input_json jsonb null,
                output_json jsonb null,
                metadata_json jsonb null,
                created_at timestamptz not null default now(),
                constraint model_audit_events_sequence_number_check
                    check (sequence_number > 0),
                constraint model_audit_events_session_sequence_unique
                    unique (session_id, sequence_number)
            )
            """
        )


def create_indexes(connection: Connection) -> None:
    """Create audit lookup indexes for admin read APIs and streaming."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            create index if not exists model_audit_sessions_customer_started_idx
            on public.model_audit_sessions (customer_id, started_at desc)
            """
        )
        cursor.execute(
            """
            create index if not exists model_audit_sessions_status_started_idx
            on public.model_audit_sessions (status, started_at desc)
            """
        )
        cursor.execute(
            """
            create index if not exists model_audit_sessions_conversation_idx
            on public.model_audit_sessions (conversation_id)
            """
        )
        cursor.execute(
            """
            create index if not exists model_audit_events_trace_sequence_idx
            on public.model_audit_events (trace_id, sequence_number)
            """
        )
        cursor.execute(
            """
            create index if not exists model_audit_events_session_created_idx
            on public.model_audit_events (session_id, created_at)
            """
        )
        cursor.execute(
            """
            create index if not exists model_audit_events_event_key_idx
            on public.model_audit_events (event_key)
            """
        )
        cursor.execute(
            """
            create index if not exists model_audit_event_lookup_category_order_idx
            on public.model_audit_event_lookup (category, display_order)
            """
        )
        cursor.execute(
            """
            create index if not exists model_audit_event_lookup_active_idx
            on public.model_audit_event_lookup (is_active)
            """
        )


def enable_rls(connection: Connection) -> None:
    """Enable row-level security for backend-owned audit tables."""
    with connection.cursor() as cursor:
        cursor.execute("alter table public.model_audit_sessions enable row level security")
        cursor.execute("alter table public.model_audit_events enable row level security")
        cursor.execute("alter table public.model_audit_event_lookup enable row level security")


def create_policies(connection: Connection) -> None:
    """Allow backend service-role access while denying direct anonymous access."""
    policies = (
        ("model_audit_sessions", "model_audit_sessions_service_role_all"),
        ("model_audit_events", "model_audit_events_service_role_all"),
        ("model_audit_event_lookup", "model_audit_event_lookup_service_role_all"),
    )
    with connection.cursor() as cursor:
        for table_name, policy_name in policies:
            cursor.execute(
                f"""
                do $$
                begin
                    if not exists (
                        select 1
                        from pg_policies
                        where schemaname = 'public'
                            and tablename = '{table_name}'
                            and policyname = '{policy_name}'
                    ) then
                        create policy {policy_name}
                        on public.{table_name}
                        for all
                        to service_role
                        using (true)
                        with check (true);
                    end if;
                end
                $$;
                """
            )


def seed_event_lookup(connection: Connection) -> None:
    """Seed stable event-key rows used by backend writers and admin UI mapping."""
    with connection.cursor() as cursor:
        for display_order, (event_key, display_name, category, description) in enumerate(
            EVENT_LOOKUP_ROWS,
            start=1,
        ):
            cursor.execute(
                """
                insert into public.model_audit_event_lookup (
                    event_key,
                    display_name,
                    category,
                    description,
                    display_order,
                    is_active
                )
                values (%s, %s, %s, %s, %s, true)
                on conflict (event_key) do update
                set display_name = excluded.display_name,
                    category = excluded.category,
                    description = excluded.description,
                    display_order = excluded.display_order,
                    is_active = excluded.is_active,
                    updated_at = now()
                """,
                (event_key, display_name, category, description, display_order),
            )
