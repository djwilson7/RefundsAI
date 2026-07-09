from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from queue import Full
from time import monotonic, sleep
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from refunds_ai_api.repositories.application import RepositoryConflictError
from refunds_ai_api.repositories.audit import (
    AuditSessionNotFoundError,
    ModelAuditRepository,
    serialize_json_value,
)
from refunds_ai_api.services.ai_chat.audit_instrumentation import model_request_payload
from refunds_ai_api.services.audit import (
    AuditQueueFullError,
    ModelAuditEventKey,
    ModelAuditSession,
    ModelAuditWriterService,
    NonBlockingModelAuditWriterService,
    TokenUsage,
)
from refunds_ai_api.services.model_audit import enrich_session_summary

SESSION_ID = UUID("70000000-0000-4000-8000-000000000001")
TRACE_ID = UUID("71000000-0000-4000-8000-000000000001")
CUSTOMER_ID = UUID("20000000-0000-4000-8000-000000000001")
CONVERSATION_ID = UUID("72000000-0000-4000-8000-000000000001")
STARTED_AT = datetime(2026, 7, 7, 14, 0, tzinfo=UTC)
COMPLETED_AT = STARTED_AT + timedelta(milliseconds=425)


class StubCursor:
    def __init__(self, connection: StubConnection) -> None:
        self.connection = connection
        self.rowcount = 1

    def __enter__(self) -> StubCursor:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, statement: str, params: tuple[Any, ...] | None = None) -> None:
        self.connection.executed.append((statement, params))
        normalized = " ".join(statement.split()).lower()
        if "from public.model_audit_sessions" in normalized:
            self.connection.result = [self.connection.session_row]
        elif "from public.model_audit_events" in normalized:
            self.connection.result = self.connection.event_rows
        else:
            self.connection.result = []
        self.rowcount = 0 if self.connection.force_conflict else 1

    def fetchone(self) -> dict[str, Any] | None:
        if self.connection.force_missing:
            return None
        return self.connection.result[0] if self.connection.result else None

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.connection.result)


class StubConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []
        self.autocommit = False
        self.force_conflict = False
        self.force_missing = False
        self.result: list[dict[str, Any]] = []
        self.notifications = [
            SimpleNamespace(
                payload=(
                    '{"id":"73000000-0000-4000-8000-000000000001",'
                    f'"session_id":"{SESSION_ID}",'
                    f'"trace_id":"{TRACE_ID}",'
                    '"sequence_number":1,'
                    '"event_key":"REQUEST_RECEIVED"}'
                )
            )
        ]
        self.session_row = {
            "id": SESSION_ID,
            "trace_id": TRACE_ID,
            "conversation_id": CONVERSATION_ID,
            "customer_id": CUSTOMER_ID,
            "request_id": "req-123",
            "model_name": "gpt-5.4-mini",
            "status": "succeeded",
            "prompt_tokens": 12,
            "completion_tokens": 7,
            "total_tokens": 19,
            "started_at": STARTED_AT,
            "completed_at": COMPLETED_AT,
            "latency_ms": 425,
            "created_at": STARTED_AT,
            "updated_at": COMPLETED_AT,
            "event_count": 1,
        }
        self.event_rows = [
            {
                "id": UUID("73000000-0000-4000-8000-000000000001"),
                "session_id": SESSION_ID,
                "trace_id": TRACE_ID,
                "sequence_number": 1,
                "event_key": ModelAuditEventKey.REQUEST_RECEIVED,
                "display_name": "Request received",
                "category": "request",
                "description": "The chat request was accepted.",
                "display_order": 10,
                "workflow_kind": "account_fact",
                "tool_name": None,
                "summary": "Request accepted.",
                "input_json": {"message_length": 19},
                "output_json": None,
                "metadata_json": {"trace_event_type": "message.received"},
                "created_at": STARTED_AT,
            }
        ]

    def cursor(self) -> StubCursor:
        return StubCursor(self)

    def notifies(self, *, timeout: int) -> list[SimpleNamespace]:
        notifications = self.notifications
        self.notifications = []
        return notifications


class StubConnectionProvider:
    def __init__(self, connection: StubConnection) -> None:
        self.connection = connection

    @contextmanager
    def open(self) -> Iterator[StubConnection]:
        yield self.connection


class RecordingAuditRepository:
    def __init__(self) -> None:
        self.created_sessions: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.completed_sessions: list[dict[str, Any]] = []

    def create_session(self, **kwargs: Any) -> None:
        self.created_sessions.append(kwargs)

    def append_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)

    def complete_session(self, **kwargs: Any) -> None:
        self.completed_sessions.append(kwargs)


class FailingAuditRepository(RecordingAuditRepository):
    def append_event(self, **kwargs: Any) -> None:
        raise RuntimeError("audit database offline")


class TrackingConnectionProvider:
    def __init__(self, connection: StubConnection) -> None:
        self.connection = connection
        self.active_connections = 0
        self.closed_connections = 0

    @contextmanager
    def open(self) -> Iterator[StubConnection]:
        self.active_connections += 1
        try:
            yield self.connection
        finally:
            self.active_connections -= 1
            self.closed_connections += 1


class AlwaysFullQueue:
    def put_nowait(self, item: Any) -> None:
        raise Full

    def qsize(self) -> int:
        return 0


def wait_for_condition(predicate) -> None:  # type: ignore[no-untyped-def]
    deadline = monotonic() + 2

    while monotonic() < deadline:
        if predicate():
            return
        sleep(0.01)

    raise AssertionError("Timed out waiting for queued audit writes.")


def test_session_summary_sums_lifecycle_events_without_double_counting() -> None:
    events = [
        {
            "event_key": "TOOL_STARTED",
            "metadata_json": {"trace_event_type": "tool_call.executing"},
        },
        {
            "event_key": "RESPONSE_GENERATED",
            "metadata_json": {
                "trace_event_type": "model.completed",
                "lifecycle": {
                    "model_call_id": "model-1",
                    "prompt_tokens": 412,
                    "completion_tokens": 31,
                    "reasoning_tokens": 7,
                    "total_tokens": 450,
                    "latency_ms": 620,
                    "status": "completed",
                    "input_tokens_estimated": 980,
                    "output_tokens_estimated": 72,
                },
            },
        },
        {
            "event_key": "TOOL_COMPLETED",
            "metadata_json": {
                "trace_event_type": "tool_call.completed",
                "lifecycle": {
                    "tool_call_id": "tool-1",
                    "status": "completed",
                    "latency_ms": 18,
                    "backend_category": "backend_read",
                    "input_tokens_estimated": 4,
                    "output_tokens_estimated": 310,
                },
            },
        },
        {
            "event_key": "RESPONSE_GENERATED",
            "metadata_json": {
                "trace_event_type": "model.completed",
                "lifecycle": {
                    "model_call_id": "model-2",
                    "prompt_tokens": 872,
                    "completion_tokens": 129,
                    "reasoning_tokens": 0,
                    "total_tokens": 1001,
                    "latency_ms": 800,
                    "status": "completed",
                    "input_tokens_estimated": 1800,
                    "output_tokens_estimated": 135,
                },
            },
        },
    ]

    summary = enrich_session_summary(
        {"latency_ms": 2080},
        events,
    )

    assert summary["total_model_calls"] == 2
    assert summary["total_tool_calls"] == 1
    assert summary["total_prompt_tokens"] == 1284
    assert summary["total_completion_tokens"] == 160
    assert summary["total_reasoning_tokens"] == 7
    assert summary["total_tokens"] == 1451
    assert summary["total_model_latency_ms"] == 1420
    assert summary["total_tool_latency_ms"] == 18
    assert summary["total_model_input_tokens_estimated"] == 2780
    assert summary["total_model_output_tokens_estimated"] == 207
    assert summary["total_tool_input_tokens_estimated"] == 4
    assert summary["total_tool_output_tokens_estimated"] == 310
    assert summary["total_workflow_latency_ms"] == 2080
    assert summary["backend_read_count"] == 1


def test_model_request_payload_separates_prompt_from_injected_context() -> None:
    payload = model_request_payload(
        {
            "model_call_id": "model-1",
            "model": "gpt-5.4-mini",
            "phase": "final_response",
            "messages": [
                {"role": "system", "content": "System instructions"},
                {"role": "user", "content": "From those, give me the first one"},
                {"role": "user", "content": "Prior result set: three purchases"},
            ],
            "tools": [{"name": "get_customer_purchase_history"}],
        }
    )

    assert payload["user_prompt"] == "From those, give me the first one"
    assert payload["has_additional_context"] is True
    assert payload["additional_context"] == [
        {"role": "user", "content": "Prior result set: three purchases"}
    ]
    assert payload["available_tools_count"] == 1


def test_model_audit_writer_creates_session_event_and_completion() -> None:
    repository = RecordingAuditRepository()
    service = ModelAuditWriterService(repository)

    session = service.start_session(
        session_id=SESSION_ID,
        trace_id=TRACE_ID,
        conversation_id=CONVERSATION_ID,
        customer_id=CUSTOMER_ID,
        request_id="req-123",
        model_name="gpt-5.4-mini",
        started_at=STARTED_AT,
    )
    event_id = service.record_event(
        session=session,
        sequence_number=1,
        event_key=ModelAuditEventKey.REQUEST_RECEIVED,
        workflow_kind="account_fact",
        tool_name="get_customer_purchase_history",
        summary="Request accepted.",
        input_json={"message_length": 19},
        output_json={"accepted": True},
        metadata_json={"surface": "purchase_history"},
        created_at=STARTED_AT,
    )
    service.complete_session(
        session=session,
        token_usage=TokenUsage(prompt_tokens=12, completion_tokens=7, total_tokens=19),
        completed_at=COMPLETED_AT,
    )

    assert session == ModelAuditSession(id=SESSION_ID, trace_id=TRACE_ID, started_at=STARTED_AT)
    assert repository.created_sessions == [
        {
            "session_id": SESSION_ID,
            "trace_id": TRACE_ID,
            "conversation_id": CONVERSATION_ID,
            "customer_id": CUSTOMER_ID,
            "request_id": "req-123",
            "model_name": "gpt-5.4-mini",
            "status": "running",
            "started_at": STARTED_AT,
        }
    ]
    assert repository.events[0]["event_id"] == event_id
    assert repository.events[0]["session_id"] == SESSION_ID
    assert repository.events[0]["trace_id"] == TRACE_ID
    assert repository.events[0]["event_key"] == "REQUEST_RECEIVED"
    assert repository.completed_sessions == [
        {
            "session_id": SESSION_ID,
            "status": "succeeded",
            "prompt_tokens": 12,
            "completion_tokens": 7,
            "total_tokens": 19,
            "input_tokens_estimated": None,
            "output_tokens_estimated": None,
            "completed_at": COMPLETED_AT,
            "latency_ms": 425,
        }
    ]


def test_model_audit_writer_marks_session_failed() -> None:
    repository = RecordingAuditRepository()
    service = ModelAuditWriterService(repository)
    session = ModelAuditSession(id=SESSION_ID, trace_id=TRACE_ID, started_at=STARTED_AT)

    service.fail_session(session=session, completed_at=COMPLETED_AT, latency_ms=500)

    assert repository.completed_sessions[0]["status"] == "failed"
    assert repository.completed_sessions[0]["latency_ms"] == 500


def test_non_blocking_model_audit_writer_queues_ordered_writes() -> None:
    repository = RecordingAuditRepository()
    service = NonBlockingModelAuditWriterService(repository)

    session = service.start_session(
        session_id=SESSION_ID,
        trace_id=TRACE_ID,
        model_name="gpt-5.4-mini",
        started_at=STARTED_AT,
    )
    event_id = service.record_event(
        session=session,
        sequence_number=1,
        event_key=ModelAuditEventKey.REQUEST_RECEIVED,
        summary="Request accepted.",
    )
    service.complete_session(
        session=session,
        token_usage=TokenUsage(total_tokens=19),
        completed_at=COMPLETED_AT,
    )

    wait_for_condition(
        lambda: repository.created_sessions
        and len(repository.events) == 1
        and repository.completed_sessions
    )
    service.stop()

    assert repository.created_sessions[0]["session_id"] == SESSION_ID
    assert repository.events[0]["event_id"] == event_id
    assert repository.events[0]["event_key"] == ModelAuditEventKey.REQUEST_RECEIVED
    assert repository.completed_sessions[0]["session_id"] == SESSION_ID
    assert repository.completed_sessions[0]["total_tokens"] == 19


def test_audit_queue_drains_events_in_order() -> None:
    repository = RecordingAuditRepository()
    service = NonBlockingModelAuditWriterService(repository)
    session = ModelAuditSession(id=SESSION_ID, trace_id=TRACE_ID, started_at=STARTED_AT)

    service.record_event(
        session=session,
        sequence_number=1,
        event_key=ModelAuditEventKey.REQUEST_RECEIVED,
    )
    service.record_event(
        session=session,
        sequence_number=2,
        event_key=ModelAuditEventKey.GRAPH_STARTED,
    )
    service.record_event(
        session=session,
        sequence_number=3,
        event_key=ModelAuditEventKey.RESPONSE_RETURNED,
    )

    wait_for_condition(lambda: len(repository.events) == 3)
    service.stop()

    assert [event["sequence_number"] for event in repository.events] == [1, 2, 3]


def test_audit_queue_full_drop_logs_warning(caplog) -> None:
    service = NonBlockingModelAuditWriterService(RecordingAuditRepository())
    object.__setattr__(service, "_queue", AlwaysFullQueue())
    session = ModelAuditSession(id=SESSION_ID, trace_id=TRACE_ID, started_at=STARTED_AT)

    with caplog.at_level("WARNING", logger="refunds_ai_api.audit"):
        event_id = service.record_event(
            session=session,
            sequence_number=1,
            event_key=ModelAuditEventKey.REQUEST_RECEIVED,
        )

    service.stop(drain=False)

    assert isinstance(event_id, UUID)
    assert caplog.records[0].event["type"] == "audit.queue_full_dropped"


def test_non_blocking_start_session_raises_when_session_enqueue_is_dropped(caplog) -> None:
    service = NonBlockingModelAuditWriterService(RecordingAuditRepository())
    object.__setattr__(service, "_queue", AlwaysFullQueue())

    with caplog.at_level("WARNING", logger="refunds_ai_api.audit"):
        with pytest.raises(AuditQueueFullError):
            service.start_session(model_name="gpt-5.4-mini")

    service.stop(drain=False)

    assert caplog.records[0].event["type"] == "audit.queue_full_dropped"


def test_audit_writer_logs_write_failure_and_continues(caplog) -> None:
    repository = FailingAuditRepository()
    service = NonBlockingModelAuditWriterService(repository)
    session = ModelAuditSession(id=SESSION_ID, trace_id=TRACE_ID, started_at=STARTED_AT)

    with caplog.at_level("WARNING", logger="refunds_ai_api.audit"):
        service.record_event(
            session=session,
            sequence_number=1,
            event_key=ModelAuditEventKey.REQUEST_RECEIVED,
        )
        wait_for_condition(
            lambda: any(
                record.event["type"] == "audit.write_failed" for record in caplog.records
            )
        )

    service.stop()

    assert caplog.records[0].event["reason"] == "RuntimeError"


def test_model_audit_writer_rejects_unknown_event_key() -> None:
    service = ModelAuditWriterService(RecordingAuditRepository())
    session = ModelAuditSession(id=SESSION_ID, trace_id=TRACE_ID, started_at=STARTED_AT)

    with pytest.raises(ValueError, match="Unknown model audit event key"):
        service.record_event(session=session, sequence_number=1, event_key="UNKNOWN_EVENT")


def test_model_audit_writer_rejects_invalid_sequence_number() -> None:
    service = ModelAuditWriterService(RecordingAuditRepository())
    session = ModelAuditSession(id=SESSION_ID, trace_id=TRACE_ID, started_at=STARTED_AT)

    with pytest.raises(ValueError, match="sequence_number"):
        service.record_event(
            session=session,
            sequence_number=0,
            event_key=ModelAuditEventKey.REQUEST_RECEIVED,
        )


def test_model_audit_writer_rejects_running_completion_status() -> None:
    service = ModelAuditWriterService(RecordingAuditRepository())
    session = ModelAuditSession(id=SESSION_ID, trace_id=TRACE_ID, started_at=STARTED_AT)

    with pytest.raises(ValueError, match="Invalid model audit session status"):
        service.complete_session(session=session, status="running", completed_at=COMPLETED_AT)


def test_model_audit_repository_inserts_session_and_event() -> None:
    connection = StubConnection()
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    repository.create_session(
        session_id=SESSION_ID,
        trace_id=TRACE_ID,
        conversation_id=CONVERSATION_ID,
        customer_id=CUSTOMER_ID,
        request_id="req-123",
        model_name="gpt-5.4-mini",
        status="running",
        started_at=STARTED_AT,
    )
    repository.append_event(
        event_id=UUID("73000000-0000-4000-8000-000000000001"),
        session_id=SESSION_ID,
        trace_id=TRACE_ID,
        sequence_number=1,
        event_key=ModelAuditEventKey.TOOL_COMPLETED,
        workflow_kind="account_fact",
        tool_name="get_customer_purchase_history",
        summary="Tool completed.",
        input_json={"customer_id": str(CUSTOMER_ID)},
        output_json={"purchase_count": 12},
        metadata_json={"latency_ms": 21},
        created_at=COMPLETED_AT,
    )

    session_sql, session_params = connection.executed[0]
    event_sql, event_params = connection.executed[1]
    assert "insert into public.model_audit_sessions" in session_sql.lower()
    assert session_params == (
        SESSION_ID,
        TRACE_ID,
        CONVERSATION_ID,
        CUSTOMER_ID,
        "req-123",
        "gpt-5.4-mini",
        "running",
        STARTED_AT,
    )
    assert "insert into public.model_audit_events" in event_sql.lower()
    assert event_params is not None
    assert event_params[:8] == (
        UUID("73000000-0000-4000-8000-000000000001"),
        SESSION_ID,
        TRACE_ID,
        1,
        "TOOL_COMPLETED",
        "account_fact",
        "get_customer_purchase_history",
        "Tool completed.",
    )
    assert event_params[8].__class__.__name__ == "Jsonb"
    assert event_params[9].__class__.__name__ == "Jsonb"
    assert event_params[10].__class__.__name__ == "Jsonb"
    assert event_params[11] == COMPLETED_AT


def test_model_audit_repository_releases_connections_after_writes() -> None:
    connection = StubConnection()
    provider = TrackingConnectionProvider(connection)
    repository = ModelAuditRepository(provider)

    repository.create_session(
        session_id=SESSION_ID,
        trace_id=TRACE_ID,
        model_name="gpt-5.4-mini",
        status="running",
        started_at=STARTED_AT,
    )
    repository.complete_session(
        session_id=SESSION_ID,
        status="succeeded",
        completed_at=COMPLETED_AT,
    )

    assert provider.active_connections == 0
    assert provider.closed_connections == 2


def test_serialize_json_value_converts_datetime_payloads() -> None:
    payload = {
        "created_at": STARTED_AT,
        "items": [{"purchased_at": COMPLETED_AT}],
        "ids": (SESSION_ID,),
    }

    assert serialize_json_value(payload) == {
        "created_at": "2026-07-07T14:00:00+00:00",
        "items": [{"purchased_at": "2026-07-07T14:00:00.425000+00:00"}],
        "ids": [str(SESSION_ID)],
    }


def test_model_audit_repository_completes_session() -> None:
    connection = StubConnection()
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    repository.complete_session(
        session_id=SESSION_ID,
        status="succeeded",
        prompt_tokens=12,
        completion_tokens=7,
        total_tokens=19,
        input_tokens_estimated=27,
        output_tokens_estimated=8,
        completed_at=COMPLETED_AT,
        latency_ms=425,
    )

    update_sql, update_params = connection.executed[0]
    assert "update public.model_audit_sessions" in update_sql.lower()
    assert update_params == (
        "succeeded",
        12,
        7,
        19,
        COMPLETED_AT,
        425,
        SESSION_ID,
    )


def test_model_audit_repository_raises_when_session_completion_misses() -> None:
    connection = StubConnection()
    connection.force_conflict = True
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    with pytest.raises(RepositoryConflictError, match="could not be completed"):
        repository.complete_session(
            session_id=SESSION_ID,
            status="failed",
            completed_at=COMPLETED_AT,
        )


def test_model_audit_repository_lists_sessions() -> None:
    connection = StubConnection()
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    sessions = repository.list_sessions(limit=25)

    query_sql, query_params = connection.executed[0]
    assert "from public.model_audit_sessions" in query_sql.lower()
    assert "left join public.model_audit_events" in query_sql.lower()
    assert "order by s.started_at desc" in query_sql.lower()
    assert query_params == (25,)
    assert sessions == [connection.session_row]


def test_model_audit_repository_lists_sessions_with_offset() -> None:
    connection = StubConnection()
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    sessions = repository.list_sessions(limit=10, offset=20)

    query_sql, query_params = connection.executed[0]
    assert "limit %s offset %s" in " ".join(query_sql.lower().split())
    assert query_params == (10, 20)
    assert sessions == [connection.session_row]


def test_model_audit_repository_lists_all_sessions_without_limit() -> None:
    connection = StubConnection()
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    sessions = repository.list_sessions()

    query_sql, query_params = connection.executed[0]
    assert "from public.model_audit_sessions" in query_sql.lower()
    assert "order by s.started_at desc" in query_sql.lower()
    assert "limit %s" not in query_sql.lower()
    assert query_params == ()
    assert sessions == [connection.session_row]


def test_model_audit_repository_gets_session() -> None:
    connection = StubConnection()
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    session = repository.get_session(SESSION_ID)

    query_sql, query_params = connection.executed[0]
    assert "where s.id = %s" in query_sql.lower()
    assert query_params == (SESSION_ID,)
    assert session == connection.session_row


def test_model_audit_repository_raises_when_session_missing() -> None:
    connection = StubConnection()
    connection.force_missing = True
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    with pytest.raises(AuditSessionNotFoundError, match="not found"):
        repository.get_session(SESSION_ID)


def test_model_audit_repository_lists_session_events_with_lookup_metadata() -> None:
    connection = StubConnection()
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    events = repository.list_events(SESSION_ID)

    query_sql, query_params = connection.executed[0]
    assert "from public.model_audit_events" in query_sql.lower()
    assert "join public.model_audit_event_lookup" in query_sql.lower()
    assert "order by e.sequence_number asc" in query_sql.lower()
    assert query_params == (SESSION_ID,)
    assert events == connection.event_rows


def test_model_audit_repository_listens_for_broadcast_events() -> None:
    connection = StubConnection()
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    event = next(repository.listen_events(session_id=SESSION_ID, timeout_seconds=1))

    listen_sql, listen_params = connection.executed[0]
    assert connection.autocommit is True
    assert listen_sql == "listen model_audit_events"
    assert listen_params is None
    assert event == {
        "id": "73000000-0000-4000-8000-000000000001",
        "session_id": str(SESSION_ID),
        "trace_id": str(TRACE_ID),
        "sequence_number": 1,
        "event_key": ModelAuditEventKey.REQUEST_RECEIVED,
    }
