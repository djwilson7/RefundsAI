from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from refunds_ai_api.repositories.application import RepositoryConflictError
from refunds_ai_api.repositories.audit import ModelAuditRepository
from refunds_ai_api.services.audit import (
    ModelAuditEventKey,
    ModelAuditSession,
    ModelAuditWriterService,
    TokenUsage,
)

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
        self.rowcount = 0 if self.connection.force_conflict else 1


class StubConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []
        self.force_conflict = False

    def cursor(self) -> StubCursor:
        return StubCursor(self)


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


def test_model_audit_repository_completes_session() -> None:
    connection = StubConnection()
    repository = ModelAuditRepository(StubConnectionProvider(connection))

    repository.complete_session(
        session_id=SESSION_ID,
        status="succeeded",
        prompt_tokens=12,
        completion_tokens=7,
        total_tokens=19,
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
