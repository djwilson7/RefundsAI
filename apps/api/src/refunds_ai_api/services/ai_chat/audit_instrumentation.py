"""Audit instrumentation helpers for AI chat trace events."""

from __future__ import annotations

import logging
from typing import Any

from refunds_ai_api.services.audit import ModelAuditEventKey, TokenUsage

logger = logging.getLogger("refunds_ai_api.chat")


def record_audit_trace_event(
    state: dict[str, Any],
    *,
    event: dict[str, Any],
) -> None:
    """Persist a trace event when an audit session is present in graph state."""
    audit_session = state.get("audit_session")
    audit_writer = state.get("audit_writer")
    if audit_session is None or audit_writer is None:
        return

    event_type = str(event.get("type", ""))
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    event_key = audit_event_key_for_trace_type(event_type)

    try:
        audit_writer.record_event(
            session=audit_session,
            sequence_number=int(event.get("step", 1)),
            event_key=event_key,
            workflow_kind=extract_workflow_kind(data),
            tool_name=extract_tool_name(data),
            summary=str(event.get("message") or "") or None,
            input_json=event_payload_for_input(event_type, data),
            output_json=event_payload_for_output(event_type, data),
            metadata_json={
                "trace_event_type": event_type,
                "file": event.get("file"),
                "line": event.get("line"),
                "data": data,
            },
        )
    except Exception as exc:
        logger.warning(
            "ai.chat.audit_event_failed: %s",
            exc,
            extra={
                "event": {
                    "type": "audit.event_failed",
                    "reason": exc.__class__.__name__,
                    "detail": str(exc),
                    "trace_event_type": event_type,
                }
            },
        )


def audit_event_key_for_trace_type(event_type: str) -> str:
    """Map detailed chat trace event types onto stable audit lookup keys."""
    if event_type == "message.received":
        return ModelAuditEventKey.REQUEST_RECEIVED
    if event_type == "graph.started":
        return ModelAuditEventKey.GRAPH_STARTED
    if event_type == "route.response_returned":
        return ModelAuditEventKey.RESPONSE_RETURNED
    if event_type == "response.generated":
        return ModelAuditEventKey.RESPONSE_GENERATED
    if event_type in {"model.failure", "model.invalid_tool_output"}:
        return ModelAuditEventKey.ERROR_RAISED
    if event_type == "model.requested":
        return ModelAuditEventKey.TOOL_REQUESTED
    if event_type in {
        "tool_call.requested",
        "tool_call.forced",
        "tool_call.overridden",
        "workflow.tool_overridden",
    }:
        return ModelAuditEventKey.TOOL_REQUESTED
    if event_type == "tool_call.executing":
        return ModelAuditEventKey.TOOL_STARTED
    if event_type == "tool_call.completed":
        return ModelAuditEventKey.TOOL_COMPLETED
    if event_type in {"tool_call.ignored", "tool_call.skipped", "response.blocked"}:
        return ModelAuditEventKey.VALIDATION_FAILED
    if event_type in {
        "workflow.confirmation_validation_failed",
        "workflow.confirmation_command_invalid",
        "workflow.confirmation_context_incomplete",
        "workflow.confirmation_pending_action_missing",
        "workflow.confirmation_target_resolution_failed",
        "workflow.mutation_conflict",
        "workflow.blocked",
        "graph.stopped",
    }:
        return ModelAuditEventKey.VALIDATION_FAILED
    if event_type in {
        "workflow.confirmation_validated",
        "workflow.confirmation_command_verified",
    }:
        return ModelAuditEventKey.VALIDATION_PASSED
    if event_type in {"workflow.refund_mutation_started", "workflow.mutation_executing"}:
        return ModelAuditEventKey.MUTATION_STARTED
    if event_type in {
        "workflow.refund_mutation_completed",
        "workflow.refund_mutation_lifecycle",
        "workflow.mutation_completed",
    }:
        return ModelAuditEventKey.MUTATION_COMPLETED
    if event_type == "workflow.context_resolved":
        return ModelAuditEventKey.CONTEXT_RESOLVED
    if event_type.startswith("workflow."):
        return ModelAuditEventKey.WORKFLOW_CLASSIFIED
    return ModelAuditEventKey.CONTEXT_RESOLVED


def event_payload_for_input(event_type: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the input-side payload for request, model, tool, and validation events."""
    if event_type in {
        "message.received",
        "model.requested",
        "tool_call.requested",
        "tool_call.executing",
    } or event_type.startswith("workflow."):
        return data
    return None


def event_payload_for_output(event_type: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the output-side payload for completed tool, mutation, and response events."""
    if event_type in {
        "tool_call.completed",
        "response.generated",
        "route.response_returned",
    }:
        return data
    if event_type in {
        "workflow.refund_mutation_completed",
        "workflow.refund_mutation_lifecycle",
        "workflow.mutation_completed",
    }:
        return data
    return None


def extract_workflow_kind(data: dict[str, Any]) -> str | None:
    """Extract the workflow kind most likely to help filter an audit event."""
    if isinstance(data.get("kind"), str):
        return data["kind"]
    active_workflow = data.get("active_workflow")
    if isinstance(active_workflow, dict) and isinstance(active_workflow.get("kind"), str):
        return active_workflow["kind"]
    workflow = data.get("workflow")
    if isinstance(workflow, dict) and isinstance(workflow.get("kind"), str):
        return workflow["kind"]
    return None


def extract_tool_name(data: dict[str, Any]) -> str | None:
    """Extract the tool name most likely to help filter an audit event."""
    for key in ("tool_name", "requested_tool_name"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value

    tool_calls = data.get("tool_calls")
    if isinstance(tool_calls, list):
        for tool_call in tool_calls:
            if isinstance(tool_call, dict) and isinstance(tool_call.get("name"), str):
                return tool_call["name"]
    return None


def merge_token_usage(
    current: TokenUsage | None,
    additional: TokenUsage | None,
) -> TokenUsage | None:
    """Return cumulative token usage for model calls that report metrics."""
    if additional is None:
        return current
    if current is None:
        return additional
    return TokenUsage(
        prompt_tokens=sum_optional(current.prompt_tokens, additional.prompt_tokens),
        completion_tokens=sum_optional(
            current.completion_tokens,
            additional.completion_tokens,
        ),
        total_tokens=sum_optional(current.total_tokens, additional.total_tokens),
    )


def sum_optional(first: int | None, second: int | None) -> int | None:
    """Sum optional integer metrics while preserving unknown totals."""
    if first is None and second is None:
        return None
    return (first or 0) + (second or 0)
