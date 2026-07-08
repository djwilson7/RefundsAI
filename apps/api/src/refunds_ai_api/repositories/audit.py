"""Repository operations for model audit sessions and events."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from refunds_ai_api.config import Settings
from refunds_ai_api.repositories.application import (
    EntityNotFoundError,
    RepositoryConfigurationError,
    RepositoryConflictError,
)

MODEL_AUDIT_EVENTS_CHANNEL = "model_audit_events"
_AUDIT_POOLS: dict[tuple[str, int], ConnectionPool] = {}


class ConnectionProvider(Protocol):
    """Opens backend-owned database connections for audit repository operations."""

    @contextmanager
    def open(self) -> Iterator[Connection]:
        """Yield an open database connection."""
        ...


@dataclass(frozen=True)
class PsycopgPoolAuditConnectionProvider:
    """Reuse pooled psycopg connections using backend Supabase configuration."""

    settings: Settings
    max_size: int = 4

    @contextmanager
    def open(self) -> Iterator[Connection]:
        """Yield a configured pooled psycopg connection."""
        if not self.settings.supabase_db_url:
            raise RepositoryConfigurationError("SUPABASE_DB_URL is not configured.")

        pool = get_audit_connection_pool(
            self.settings.supabase_db_url,
            connect_timeout=self.settings.database_connect_timeout_seconds,
            max_size=self.max_size,
        )
        with pool.connection() as connection:
            yield connection


PsycopgAuditConnectionProvider = PsycopgPoolAuditConnectionProvider


def get_audit_connection_pool(
    db_url: str,
    *,
    connect_timeout: int,
    max_size: int,
) -> ConnectionPool:
    """Return the shared audit connection pool for one database URL."""
    key = (db_url, connect_timeout)
    pool = _AUDIT_POOLS.get(key)
    if pool is None or pool.closed:
        pool = ConnectionPool(
            db_url,
            kwargs={
                "connect_timeout": connect_timeout,
                "row_factory": dict_row,
            },
            min_size=0,
            max_size=max_size,
            open=True,
        )
        _AUDIT_POOLS[key] = pool
    return pool


def close_audit_connection_pools() -> None:
    """Close all shared audit connection pools."""
    for pool in _AUDIT_POOLS.values():
        pool.close()
    _AUDIT_POOLS.clear()


@dataclass(frozen=True)
class ModelAuditRepository:
    """Persist model audit session headers and ordered event timeline rows."""

    connection_provider: ConnectionProvider

    def create_session(
        self,
        *,
        session_id: UUID,
        trace_id: UUID,
        model_name: str,
        status: str,
        conversation_id: UUID | None = None,
        customer_id: UUID | None = None,
        request_id: str | None = None,
        started_at: datetime | None = None,
    ) -> None:
        """Insert one parent audit session row."""
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.model_audit_sessions (
                        id,
                        trace_id,
                        conversation_id,
                        customer_id,
                        request_id,
                        model_name,
                        status,
                        started_at
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()))
                    """,
                    (
                        session_id,
                        trace_id,
                        conversation_id,
                        customer_id,
                        request_id,
                        model_name,
                        status,
                        started_at,
                    ),
                )

    def append_event(
        self,
        *,
        event_id: UUID,
        session_id: UUID,
        trace_id: UUID,
        sequence_number: int,
        event_key: str,
        workflow_kind: str | None = None,
        tool_name: str | None = None,
        summary: str | None = None,
        input_json: dict[str, Any] | None = None,
        output_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Insert one ordered audit event row."""
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.model_audit_events (
                        id,
                        session_id,
                        trace_id,
                        sequence_number,
                        event_key,
                        workflow_kind,
                        tool_name,
                        summary,
                        input_json,
                        output_json,
                        metadata_json,
                        created_at
                    )
                    values (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        coalesce(%s, now())
                    )
                    """,
                    (
                        event_id,
                        session_id,
                        trace_id,
                        sequence_number,
                        event_key,
                        workflow_kind,
                        tool_name,
                        summary,
                        adapt_jsonb(input_json),
                        adapt_jsonb(output_json),
                        adapt_jsonb(metadata_json),
                        created_at,
                    ),
                )

    def complete_session(
        self,
        *,
        session_id: UUID,
        status: str,
        completed_at: datetime,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Mark one audit session finished with token and latency metrics."""
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.model_audit_sessions
                    set status = %s,
                        prompt_tokens = %s,
                        completion_tokens = %s,
                        total_tokens = %s,
                        completed_at = %s,
                        latency_ms = %s,
                        updated_at = now()
                    where id = %s
                    """,
                    (
                        status,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        completed_at,
                        latency_ms,
                        session_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RepositoryConflictError("Model audit session could not be completed.")

    def list_sessions(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return audit sessions for the admin audit list."""
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                statement = """
                    select
                        s.id,
                        s.trace_id,
                        s.conversation_id,
                        s.customer_id,
                        s.request_id,
                        s.model_name,
                        s.status,
                        s.prompt_tokens,
                        s.completion_tokens,
                        s.total_tokens,
                        s.started_at,
                        s.completed_at,
                        s.latency_ms,
                        s.created_at,
                        s.updated_at,
                        count(e.id)::integer as event_count
                    from public.model_audit_sessions s
                    left join public.model_audit_events e on e.session_id = s.id
                    group by s.id
                    order by s.started_at desc
                    """
                params: tuple[Any, ...] = ()
                if limit is not None:
                    statement += " limit %s"
                    params = (limit,)
                if offset > 0:
                    statement += " offset %s"
                    params = (*params, offset)
                cursor.execute(statement, params)
                return list(cursor.fetchall())

    def get_session(self, session_id: UUID) -> dict[str, Any]:
        """Return one audit session summary with event count."""
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        s.id,
                        s.trace_id,
                        s.conversation_id,
                        s.customer_id,
                        s.request_id,
                        s.model_name,
                        s.status,
                        s.prompt_tokens,
                        s.completion_tokens,
                        s.total_tokens,
                        s.started_at,
                        s.completed_at,
                        s.latency_ms,
                        s.created_at,
                        s.updated_at,
                        count(e.id)::integer as event_count
                    from public.model_audit_sessions s
                    left join public.model_audit_events e on e.session_id = s.id
                    where s.id = %s
                    group by s.id
                    """,
                    (session_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise AuditSessionNotFoundError("Model audit session was not found.")
                return dict(row)

    def list_events(self, session_id: UUID) -> list[dict[str, Any]]:
        """Return ordered audit events for one session with lookup metadata."""
        with self.connection_provider.open() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        e.id,
                        e.session_id,
                        e.trace_id,
                        e.sequence_number,
                        e.event_key,
                        l.display_name,
                        l.category,
                        l.description,
                        l.display_order,
                        e.workflow_kind,
                        e.tool_name,
                        e.summary,
                        e.input_json,
                        e.output_json,
                        e.metadata_json,
                        e.created_at
                    from public.model_audit_events e
                    join public.model_audit_event_lookup l on l.event_key = e.event_key
                    where e.session_id = %s
                    order by e.sequence_number asc
                    """,
                    (session_id,),
                )
                return list(cursor.fetchall())

    def listen_events(
        self,
        *,
        session_id: UUID | None = None,
        timeout_seconds: int = 15,
    ) -> Iterator[dict[str, Any]]:
        """Yield database-broadcast audit events from the PostgreSQL notify channel."""
        with self.connection_provider.open() as connection:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(f"listen {MODEL_AUDIT_EVENTS_CHANNEL}")

            while True:
                received_notification = False
                for notification in connection.notifies(timeout=timeout_seconds):
                    received_notification = True
                    event = json.loads(notification.payload)
                    if session_id is not None and event.get("session_id") != str(session_id):
                        continue
                    yield event

                if not received_notification:
                    yield {"type": "keepalive"}


class AuditSessionNotFoundError(EntityNotFoundError):
    """Raised when an audit session id does not resolve."""


def adapt_jsonb(value: dict[str, Any] | None) -> Jsonb | None:
    """Adapt optional dictionaries for psycopg JSONB parameters."""
    return Jsonb(serialize_json_value(value)) if value is not None else None


def serialize_json_value(value: Any) -> Any:
    """Return a JSON-compatible value for audit payload persistence."""
    if isinstance(value, dict):
        return {key: serialize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_json_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value
