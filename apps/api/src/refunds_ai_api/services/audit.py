"""Backend writer service for model audit sessions and events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4


class ModelAuditRepositoryProtocol(Protocol):
    """Repository operations required by the model audit writer."""

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
        """Persist one audit session."""
        ...

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
        """Persist one ordered audit event."""
        ...

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
        """Persist final session status and metrics."""
        ...


class ModelAuditEventKey:
    """Stable audit event keys stored in model_audit_event_lookup."""

    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    GRAPH_STARTED = "GRAPH_STARTED"
    WORKFLOW_CLASSIFIED = "WORKFLOW_CLASSIFIED"
    CONTEXT_RESOLVED = "CONTEXT_RESOLVED"
    TOOL_REQUESTED = "TOOL_REQUESTED"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    MUTATION_STARTED = "MUTATION_STARTED"
    MUTATION_COMPLETED = "MUTATION_COMPLETED"
    RESPONSE_GENERATED = "RESPONSE_GENERATED"
    RESPONSE_RETURNED = "RESPONSE_RETURNED"
    ERROR_RAISED = "ERROR_RAISED"


MODEL_AUDIT_EVENT_KEYS = frozenset(
    value
    for name, value in vars(ModelAuditEventKey).items()
    if name.isupper() and isinstance(value, str)
)

MODEL_AUDIT_STATUSES = frozenset({"running", "succeeded", "failed"})


@dataclass(frozen=True)
class ModelAuditSession:
    """Identifiers and timing for one active audit session."""

    id: UUID
    trace_id: UUID
    started_at: datetime


@dataclass(frozen=True)
class TokenUsage:
    """Token usage metrics captured for a completed model request."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ModelAuditWriterService:
    """Write audit sessions and ordered events through the repository boundary."""

    repository: ModelAuditRepositoryProtocol

    def start_session(
        self,
        *,
        model_name: str,
        trace_id: UUID | None = None,
        session_id: UUID | None = None,
        conversation_id: UUID | None = None,
        customer_id: UUID | None = None,
        request_id: str | None = None,
        started_at: datetime | None = None,
    ) -> ModelAuditSession:
        """Create a running audit session for one chat request."""
        effective_session_id = session_id or uuid4()
        effective_trace_id = trace_id or uuid4()
        effective_started_at = started_at or datetime.now(UTC)
        self.repository.create_session(
            session_id=effective_session_id,
            trace_id=effective_trace_id,
            conversation_id=conversation_id,
            customer_id=customer_id,
            request_id=request_id,
            model_name=model_name,
            status="running",
            started_at=effective_started_at,
        )
        return ModelAuditSession(
            id=effective_session_id,
            trace_id=effective_trace_id,
            started_at=effective_started_at,
        )

    def record_event(
        self,
        *,
        session: ModelAuditSession,
        sequence_number: int,
        event_key: str,
        workflow_kind: str | None = None,
        tool_name: str | None = None,
        summary: str | None = None,
        input_json: dict[str, Any] | None = None,
        output_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> UUID:
        """Append one ordered event to an audit session."""
        assert_known_event_key(event_key)
        if sequence_number < 1:
            raise ValueError("Model audit event sequence_number must be greater than zero.")

        event_id = uuid4()
        self.repository.append_event(
            event_id=event_id,
            session_id=session.id,
            trace_id=session.trace_id,
            sequence_number=sequence_number,
            event_key=event_key,
            workflow_kind=workflow_kind,
            tool_name=tool_name,
            summary=summary,
            input_json=input_json,
            output_json=output_json,
            metadata_json=metadata_json,
            created_at=created_at,
        )
        return event_id

    def complete_session(
        self,
        *,
        session: ModelAuditSession,
        status: str = "succeeded",
        token_usage: TokenUsage | None = None,
        completed_at: datetime | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Mark a session succeeded or failed with final metrics."""
        assert_known_status(status, allow_running=False)
        effective_completed_at = completed_at or datetime.now(UTC)
        effective_latency_ms = (
            latency_ms
            if latency_ms is not None
            else max(0, int((effective_completed_at - session.started_at).total_seconds() * 1000))
        )
        effective_token_usage = token_usage or TokenUsage()
        self.repository.complete_session(
            session_id=session.id,
            status=status,
            prompt_tokens=effective_token_usage.prompt_tokens,
            completion_tokens=effective_token_usage.completion_tokens,
            total_tokens=effective_token_usage.total_tokens,
            completed_at=effective_completed_at,
            latency_ms=effective_latency_ms,
        )

    def fail_session(
        self,
        *,
        session: ModelAuditSession,
        token_usage: TokenUsage | None = None,
        completed_at: datetime | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Mark a session failed with final metrics."""
        self.complete_session(
            session=session,
            status="failed",
            token_usage=token_usage,
            completed_at=completed_at,
            latency_ms=latency_ms,
        )


def assert_known_event_key(event_key: str) -> None:
    """Reject event keys not backed by model_audit_event_lookup seed data."""
    if event_key not in MODEL_AUDIT_EVENT_KEYS:
        raise ValueError(f"Unknown model audit event key: {event_key}.")


def assert_known_status(status: str, *, allow_running: bool) -> None:
    """Reject invalid audit session status values."""
    if status not in MODEL_AUDIT_STATUSES or (status == "running" and not allow_running):
        raise ValueError(f"Invalid model audit session status: {status}.")
