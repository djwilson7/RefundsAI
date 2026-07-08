"""Audit instrumentation helpers for AI chat trace events."""

from __future__ import annotations

from datetime import date, datetime, UTC
import logging
from typing import Any
import uuid

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
        # Build structured event fields as requested by Objective 10
        workflow_name = extract_workflow_kind(data) or state.get("workflow_kind")
        tool_name = extract_tool_name(data)
        
        # State before vs after
        state_before = summarize_conversation_state_dict(data.get("conversation_state") or state.get("conversation_state"))
        state_after = summarize_conversation_state_dict(state.get("conversation_state"))
        
        decision = data.get("reason") or data.get("action")
        reason = data.get("reason")

        structured_event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "workflow": workflow_name,
            "intent": event_type,
            "tool": tool_name,
            "state_before": state_before,
            "state_after": state_after,
            "decision": decision,
            "reason": reason,
        }

        # Clean payloads to store identifiers instead of entire objects
        input_payload = sanitize_audit_payload(event_payload_for_input(event_type, data))
        output_payload = sanitize_audit_payload(event_payload_for_output(event_type, data))
        metadata_payload = sanitize_audit_payload({
            "trace_event_type": event_type,
            "file": event.get("file"),
            "line": event.get("line"),
            "structured_event": structured_event,
        })

        audit_writer.record_event(
            session=audit_session,
            sequence_number=int(event.get("step", 1)),
            event_key=event_key,
            workflow_kind=workflow_name,
            tool_name=tool_name,
            summary=str(event.get("message") or "") or None,
            input_json=input_payload,
            output_json=output_payload,
            metadata_json=metadata_payload,
        )
    except Exception as exc:
        logger.warning(
            "audit.write_failed: %s",
            exc,
            extra={
                "event": {
                    "type": "audit.write_failed",
                    "reason": exc.__class__.__name__,
                    "detail": str(exc),
                    "trace_event_type": event_type,
                }
            },
        )


def sanitize_audit_payload(obj: Any) -> Any:
    """Recursively clean objects to be JSON-serializable and strip out large payloads, keeping only identifiers and counts."""
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            # If the key is likely to contain a large object list or nested payload, summarize it
            if k in {"purchases", "purchase_history", "messages", "tools", "result", "tool_results", "data", "transitions"}:
                if isinstance(v, list):
                    cleaned[k] = {"count": len(v), "ids": [extract_id(item) for item in v[:5]]}
                elif isinstance(v, dict):
                    cleaned[k] = {"id": extract_id(v), "summary": summarize_dict(v)}
                else:
                    cleaned[k] = str(v)[:200]
            elif k in {"conversation_state", "model_context"}:
                cleaned[k] = summarize_conversation_state_dict(v)
            else:
                cleaned[k] = sanitize_audit_payload(v)
        return cleaned
    if isinstance(obj, list):
        return [sanitize_audit_payload(item) for item in obj[:10]]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return str(obj)[:500]


def extract_id(item: Any) -> str | None:
    if isinstance(item, dict):
        for k in ("id", "purchase_id", "customer_id", "session_id"):
            if k in item and item[k]:
                return str(item[k])
    return None


def summarize_dict(item: dict[str, Any]) -> dict[str, Any]:
    summary = {}
    for k in ("status", "purchase_type", "amount_cents", "refund_stage", "required_action", "product_name"):
        if k in item:
            summary[k] = item[k]
    return summary


def summarize_conversation_state_dict(v: Any) -> dict[str, Any]:
    if not isinstance(v, dict):
        return {}
    return {
        "selected_purchase_id": v.get("selected_purchase_id"),
        "selected_purchase_ids": v.get("selected_purchase_ids"),
        "active_purchase": v.get("active_purchase"),
        "active_refund_context": v.get("active_refund_context"),
        "pending_refund_action": v.get("pending_refund_action"),
        "current_page": v.get("current_page"),
    }


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
