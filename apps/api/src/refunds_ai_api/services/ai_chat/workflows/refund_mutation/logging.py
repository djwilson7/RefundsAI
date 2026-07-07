"""Structured trace logging for refund mutation gates."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.logging import log_trace_step
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.workflows.context import WorkflowContext


def _log_mutation_event(
    state: ChatGraphState,
    context: WorkflowContext,
    event_type: str,
    message: str,
    *,
    pending_action: dict[str, Any],
    workflow: dict[str, Any] | None,
    expected_status_or_stage: str,
    persisted_status_or_stage: str | None = None,
    received_command: str | None,
    level: int,
) -> ChatGraphState:
    return log_trace_step(
        state,
        message=message,
        event_type=event_type,
        data=_mutation_log_payload(
            context,
            pending_action=pending_action,
            workflow=workflow,
            expected_status_or_stage=expected_status_or_stage,
            persisted_status_or_stage=persisted_status_or_stage,
            received_command=received_command,
        ),
        level=level,
    )

def _mutation_log_payload(
    context: WorkflowContext,
    *,
    pending_action: dict[str, Any],
    workflow: dict[str, Any] | None,
    expected_status_or_stage: str | None,
    persisted_status_or_stage: str | None = None,
    received_command: str | None = None,
) -> dict[str, Any]:
    workflow = workflow or {}
    pending_action_id = "|".join(
        str(value)
        for value in (
            pending_action.get("action"),
            pending_action.get("purchase_id"),
            pending_action.get("purchase_type"),
        )
        if value
    )
    return {
        "kind": context.kind.value,
        "customer_id": context.customer_id,
        "purchase_id": pending_action.get("purchase_id"),
        "product_name": pending_action.get("product_name"),
        "purchase_type": pending_action.get("purchase_type"),
        "mutation_action": pending_action.get("action"),
        "action": pending_action.get("action"),
        "expected_status_or_stage": expected_status_or_stage,
        "persisted_status_or_stage": persisted_status_or_stage
        or workflow.get("refund_stage"),
        "refund_amount": workflow.get("refundable_amount_cents")
        or pending_action.get("refundable_amount_cents"),
        "refund_stage": workflow.get("refund_stage"),
        "refund_outcome": workflow.get("refund_outcome")
        or pending_action.get("refund_outcome"),
        "pending_refund_action": {
            "id": pending_action_id,
            "type": pending_action.get("action"),
            "purchase_id": pending_action.get("purchase_id"),
            "purchase_type": pending_action.get("purchase_type"),
        },
        "confirmation_command_used": received_command,
        "confirmation_command": received_command,
        "required_action": workflow.get("required_action")
        or pending_action.get("required_action"),
    }

def _log_confirmation_event(
    state: ChatGraphState,
    context: WorkflowContext,
    *,
    reason: str,
    pending_action: dict[str, Any],
    workflow: dict[str, Any] | None = None,
    level: int,
) -> ChatGraphState:
    """Log one confirmation gate decision."""
    state = log_trace_step(
        state,
        message="Refund workflow mutation requires explicit customer confirmation.",
        event_type="workflow.confirmation_requested",
        data={
            "kind": context.kind.value,
            "reason": reason,
            "pending_action": pending_action,
            "workflow": workflow,
        },
        level=level,
    )
    if reason == "refund_mutation_confirmation_required":
        return log_trace_step(
            state,
            message="Workflow transition blocked until customer confirmation.",
            event_type="workflow.blocked",
            data={
                "kind": context.kind.value,
                "reason": reason,
                "pending_action": pending_action,
            },
            level=level,
        )
    return state

def _log_confirmation_command_event(
    state: ChatGraphState,
    context: WorkflowContext,
    *,
    event_type: str,
    message: str,
    active_refund_context: dict[str, Any] | None,
    expected_command: str | None = None,
    received_command: str | None = None,
    matched_command: str | None = None,
    pending_action: dict[str, Any] | None = None,
    workflow: dict[str, Any] | None = None,
    level: int,
) -> ChatGraphState:
    """Log canonical refund confirmation-command boundary events."""
    return log_trace_step(
        state,
        message=message,
        event_type=event_type,
        data={
            "kind": context.kind.value,
            "purchase_type": active_refund_context.get("purchase_type")
            if isinstance(active_refund_context, dict)
            else None,
            "purchase_id": active_refund_context.get("purchase_id")
            if isinstance(active_refund_context, dict)
            else None,
            "active_refund_stage": active_refund_context.get("stage")
            if isinstance(active_refund_context, dict)
            else None,
            "expected_command": expected_command,
            "received_command": received_command,
            "matched_command": matched_command,
            "pending_action": pending_action,
            "workflow": workflow,
        },
        level=level,
    )
