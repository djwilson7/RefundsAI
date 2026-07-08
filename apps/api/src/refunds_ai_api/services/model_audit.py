"""Read service for model audit sessions and events."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class ModelAuditReadRepositoryProtocol(Protocol):
    """Repository operations required by admin audit read APIs."""

    def list_sessions(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return audit sessions, optionally capped by a caller-supplied limit."""
        ...

    def get_session(self, session_id: UUID) -> dict[str, Any]:
        """Return one audit session."""
        ...

    def list_events(self, session_id: UUID) -> list[dict[str, Any]]:
        """Return ordered audit events for one session."""
        ...

    def listen_events(
        self,
        *,
        session_id: UUID | None = None,
        timeout_seconds: int = 15,
    ) -> Iterator[dict[str, Any]]:
        """Yield realtime audit event notifications."""
        ...


@dataclass(frozen=True)
class ModelAuditReadService:
    """Coordinate read-only admin access to model audit data."""

    repository: ModelAuditReadRepositoryProtocol

    def list_sessions(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return audit sessions, optionally capped by a caller-supplied limit."""
        sessions = self.repository.list_sessions(limit=limit, offset=offset)
        return [
            enrich_session_summary(
                session,
                self.repository.list_events(session["id"]),
            )
            for session in sessions
        ]

    def get_session(self, session_id: UUID) -> dict[str, Any]:
        """Return one audit session."""
        session = self.repository.get_session(session_id)
        return enrich_session_summary(session, self.repository.list_events(session_id))

    def list_events(self, session_id: UUID) -> list[dict[str, Any]]:
        """Return ordered events after confirming the session exists."""
        self.repository.get_session(session_id)
        return [enrich_event_lifecycle(event) for event in self.repository.list_events(session_id)]

    def stream_events(self, *, session_id: UUID | None = None) -> Iterator[str]:
        """Yield server-sent event frames for database-broadcast audit events."""
        for event in self.repository.listen_events(session_id=session_id):
            yield format_sse_event(event)


def format_sse_event(event: dict[str, Any]) -> str:
    """Format one audit notification as a server-sent event frame."""
    if event.get("type") == "keepalive":
        return ": keepalive\n\n"
    payload = json.dumps(event, default=str, sort_keys=True)
    return f"event: model_audit_event\ndata: {payload}\n\n"


def enrich_session_summary(
    session: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate authoritative session totals from lifecycle events."""
    enriched_events = [enrich_event_lifecycle(event) for event in events]
    model_events = unique_lifecycle_events([
        event for event in enriched_events if event.get("model_call_id") is not None
    ], "model_call_id")
    tool_events = unique_lifecycle_events([
        event
        for event in enriched_events
        if event.get("tool_call_id") is not None
        and event.get("status") in {"completed", "failed"}
    ], "tool_call_id")
    return {
        **session,
        "reasoning_tokens": sum_metric(model_events, "reasoning_tokens"),
        "total_model_calls": len(model_events),
        "total_tool_calls": len(tool_events),
        "total_prompt_tokens": sum_metric(model_events, "prompt_tokens"),
        "total_completion_tokens": sum_metric(model_events, "completion_tokens"),
        "total_reasoning_tokens": sum_metric(model_events, "reasoning_tokens"),
        "total_tokens": sum_metric(model_events, "total_tokens"),
        "total_model_latency_ms": sum_metric(model_events, "latency_ms"),
        "total_tool_latency_ms": sum_metric(tool_events, "latency_ms"),
        "total_model_input_tokens_estimated": sum_metric(
            model_events,
            "input_tokens_estimated",
        ),
        "total_model_output_tokens_estimated": sum_metric(
            model_events,
            "output_tokens_estimated",
        ),
        "total_tool_input_tokens_estimated": sum_metric(
            tool_events,
            "input_tokens_estimated",
        ),
        "total_tool_output_tokens_estimated": sum_metric(
            tool_events,
            "output_tokens_estimated",
        ),
        "total_workflow_latency_ms": session.get("latency_ms"),
        "total_workflow_steps": len(events),
        "backend_read_count": count_backend_category(tool_events, "backend_read"),
        "backend_validation_count": count_backend_category(
            tool_events,
            "backend_validation",
        ),
        "backend_verification_count": count_backend_category(
            tool_events,
            "backend_verification",
        ),
        "backend_mutation_count": count_backend_category(
            tool_events,
            "backend_mutation",
        ),
        "external_api_call_count": count_backend_category(
            tool_events,
            "external_api",
        ),
    }


def enrich_event_lifecycle(event: dict[str, Any]) -> dict[str, Any]:
    """Flatten lifecycle metadata into the admin event API record."""
    metadata = event.get("metadata_json")
    lifecycle = metadata.get("lifecycle") if isinstance(metadata, dict) else None
    if not isinstance(lifecycle, dict):
        if event.get("event_key") not in {"TOOL_COMPLETED", "MUTATION_COMPLETED"}:
            return event
        return {
            **event,
            "tool_call_id": str(event.get("id")),
            "status": "completed",
            "backend_category": (
                "mutation"
                if event.get("event_key") == "MUTATION_COMPLETED"
                else "read"
            ),
        }
    return {
        **event,
        "model_call_id": lifecycle.get("model_call_id"),
        "phase": lifecycle.get("phase"),
        "prompt_tokens": lifecycle.get("prompt_tokens"),
        "completion_tokens": lifecycle.get("completion_tokens"),
        "reasoning_tokens": lifecycle.get("reasoning_tokens"),
        "total_tokens": lifecycle.get("total_tokens"),
        "latency_ms": lifecycle.get("latency_ms"),
        "status": lifecycle.get("status"),
        "started_at": lifecycle.get("started_at"),
        "completed_at": lifecycle.get("completed_at"),
        "tool_call_id": lifecycle.get("tool_call_id"),
        "source": lifecycle.get("source"),
        "operation": lifecycle.get("operation"),
        "backend_category": lifecycle.get("backend_category"),
        "available_tools_count": lifecycle.get("available_tools_count"),
        "tool_results_provided": lifecycle.get("tool_results_provided"),
        "conversation_state_summary": lifecycle.get(
            "conversation_state_summary"
        ),
        "input_tokens_estimated": lifecycle.get("input_tokens_estimated"),
        "output_tokens_estimated": lifecycle.get("output_tokens_estimated"),
        "tokenizer": lifecycle.get("tokenizer"),
        "raw_context_tokens": lifecycle.get("raw_context_tokens"),
        "projected_context_tokens": lifecycle.get("projected_context_tokens"),
        "token_savings_estimated": lifecycle.get("token_savings_estimated"),
        "prompt_module_tokens": lifecycle.get("prompt_module_tokens"),
        "tool_schema_tokens": lifecycle.get("tool_schema_tokens"),
        "tool_result_tokens": lifecycle.get("tool_result_tokens"),
        "conversation_state_tokens": lifecycle.get("conversation_state_tokens"),
        "projection_reason": lifecycle.get("projection_reason"),
        "request_category": lifecycle.get("request_category"),
        "token_budget": lifecycle.get("token_budget"),
        "input_summary": lifecycle.get("input_summary"),
        "output_summary": lifecycle.get("output_summary"),
        "customer_id": lifecycle.get("customer_id"),
        "purchase_id": lifecycle.get("purchase_id"),
    }


def sum_metric(events: list[dict[str, Any]], key: str) -> int:
    return sum(
        value
        for event in events
        if isinstance((value := event.get(key)), int)
    )


def count_backend_category(
    events: list[dict[str, Any]],
    category: str,
) -> int:
    return sum(event.get("backend_category") == category for event in events)


def unique_lifecycle_events(
    events: list[dict[str, Any]],
    id_key: str,
) -> list[dict[str, Any]]:
    """Return one terminal lifecycle record per operation id."""
    by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        operation_id = event.get(id_key)
        if isinstance(operation_id, str):
            by_id[operation_id] = event
    return list(by_id.values())
