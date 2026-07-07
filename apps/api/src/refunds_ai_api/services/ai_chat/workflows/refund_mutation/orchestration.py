"""Confirmed refund mutation execution and persistence validation."""

from __future__ import annotations

import logging
from typing import Any

from refunds_ai_api.services.ai_chat.logging import log_trace_step
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.resolution import resolve_purchase_by_id
from refunds_ai_api.services.ai_chat.scopes import update_conversation_state_for_page_reference
from refunds_ai_api.services.ai_chat.workflows.context import WorkflowContext
from refunds_ai_api.services.refund_policy import RefundWorkflowError

from ..tool_routing import _forced_tool_call_id
from .logging import (
    _log_confirmation_command_event,
    _log_mutation_event,
    _mutation_log_payload,
)
from .state import (
    _active_mutation_workflow_state,
    _active_refund_context_from_workflow,
    _build_refund_mutation_success_response,
    _build_refund_validation_failed_response,
    _expected_refund_stage_for_mutation,
    _mutation_persistence_matches,
    _validate_refund_mutation_allowed,
)


def _execute_confirmed_refund_action(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
    pending_action: dict[str, Any],
) -> ChatGraphState:
    """Execute one already-confirmed refund mutation through backend services."""
    action = pending_action["action"]
    purchase_id = pending_action["purchase_id"]
    if runtime.application_service is None or context.customer_id is None:
        return _blocked_refund_mutation_response(
            state,
            context,
            {
                **conversation_state,
                "pending_refund_action": None,
            },
            response="Please load a mock customer before continuing the refund process.",
            reason="customer_context_required",
        )

    resolved_purchase = resolve_purchase_by_id(
        runtime.application_service,
        context.customer_id,
        purchase_id,
    )
    if resolved_purchase is None:
        return _blocked_refund_mutation_response(
            state,
            context,
            {
                **conversation_state,
                "pending_refund_action": None,
            },
            response=(
                "I could not verify that refund request against the active "
                "customer account, so I have not changed the refund process."
            ),
            reason="pending_refund_action_unverified",
        )

    workflow = runtime.application_service.get_refund_workflow(purchase_id)
    allowed, denial_response = _validate_refund_mutation_allowed(
        action,
        {
            "purchase_id": resolved_purchase["id"],
            "product_name": resolved_purchase["product_name"],
            "purchase_type": resolved_purchase["purchase_type"],
        },
        workflow,
    )
    if not allowed:
        return _blocked_refund_mutation_response(
            state,
            context,
            {
                **conversation_state,
                "pending_refund_action": None,
            },
            response=denial_response,
            reason=f"{action}_not_allowed",
            workflow=workflow,
        )

    pending_action = {
        **pending_action,
        "purchase_id": resolved_purchase["id"],
        "product_name": resolved_purchase["product_name"],
        "purchase_type": resolved_purchase["purchase_type"],
        "required_action": workflow.get("required_action"),
        "refundable_amount_cents": workflow.get("refundable_amount_cents"),
        "refund_outcome": workflow.get("refund_outcome"),
    }
    purchase_id = pending_action["purchase_id"]
    expected_stage = _expected_refund_stage_for_mutation(action)
    state = _log_mutation_event(
        state,
        context,
        "mutation_requested",
        "Refund workflow mutation requested after canonical confirmation.",
        pending_action=pending_action,
        workflow=workflow,
        expected_status_or_stage=expected_stage,
        received_command=state.get("message"),
        level=logging.INFO,
    )
    state = _log_mutation_event(
        state,
        context,
        "mutation_target_resolved",
        "Resolved refund mutation target.",
        pending_action=pending_action,
        workflow=workflow,
        expected_status_or_stage=expected_stage,
        received_command=state.get("message"),
        level=logging.INFO,
    )
    state = _log_mutation_event(
        state,
        context,
        "mutation_permission_validated",
        "Validated refund mutation permission against current workflow.",
        pending_action=pending_action,
        workflow=workflow,
        expected_status_or_stage=expected_stage,
        received_command=state.get("message"),
        level=logging.INFO,
    )
    state = log_trace_step(
        state,
        message="Executing confirmed refund workflow mutation.",
        event_type="mutation_executed",
        data=_mutation_log_payload(
            context,
            pending_action=pending_action,
            workflow=workflow,
            expected_status_or_stage=expected_stage,
            received_command=state.get("message"),
        ),
        level=logging.INFO,
    )
    try:
        if action == "request_refund":
            result = runtime.application_service.request_refund(purchase_id)
            tool_name = "request_refund"
        else:
            result = runtime.application_service.issue_refund(purchase_id)
            tool_name = "issue_refund"
    except RefundWorkflowError as exc:
        next_state = update_conversation_state_for_page_reference(
            {
                **conversation_state,
                "pending_refund_action": None,
            },
            context.page_reference,
        )
        state = log_trace_step(
            state,
            message="Confirmed refund workflow mutation was rejected by policy.",
            event_type="workflow.mutation_conflict",
            data={
                "kind": context.kind.value,
                "action": action,
                "purchase_id": purchase_id,
                "reason": str(exc),
            },
            level=logging.WARNING,
        )
        return {
            **state,
            "tool_results": [],
            "assistant_response": (
                "I could not complete that refund request because the current "
                f"refund status no longer allows it: {exc}"
            ),
            "conversation_state": next_state,
            "page_reference": context.page_reference,
        }

    state = _log_mutation_event(
        state,
        context,
        "mutation_persistence_validation_started",
        "Validating persisted refund workflow state after mutation.",
        pending_action=pending_action,
        workflow=result,
        expected_status_or_stage=expected_stage,
        received_command=state.get("message"),
        level=logging.INFO,
    )
    persisted_result = runtime.application_service.get_refund_workflow(purchase_id)
    validation_succeeded = _mutation_persistence_matches(
        action,
        persisted_result,
    )
    if not validation_succeeded:
        state = _log_mutation_event(
            state,
            context,
            "mutation_persistence_validation_failed",
            "Persisted refund workflow state did not match mutation expectation.",
            pending_action=pending_action,
            workflow=persisted_result,
            expected_status_or_stage=expected_stage,
            persisted_status_or_stage=persisted_result.get("refund_stage"),
            received_command=state.get("message"),
            level=logging.ERROR,
        )
        next_state = update_conversation_state_for_page_reference(
            {
                **conversation_state,
                "pending_refund_action": None,
                "active_purchase": {
                    "purchase_id": purchase_id,
                    "product_name": pending_action["product_name"],
                    "purchase_type": pending_action["purchase_type"],
                },
                "active_refund_context": _active_refund_context_from_workflow(
                    pending_action,
                    persisted_result,
                ),
                "active_workflow": _active_mutation_workflow_state(
                    state,
                    context,
                    action,
                    pending_action,
                    persisted_result,
                    last_tool_name=tool_name,
                ),
            },
            context.page_reference,
        )
        return {
            **state,
            "tool_results": [],
            "assistant_response": _build_refund_validation_failed_response(action),
            "conversation_state": next_state,
            "page_reference": context.page_reference,
        }

    state = _log_mutation_event(
        state,
        context,
        "mutation_persistence_validation_succeeded",
        "Persisted refund workflow state matched mutation expectation.",
        pending_action=pending_action,
        workflow=persisted_result,
        expected_status_or_stage=expected_stage,
        persisted_status_or_stage=persisted_result.get("refund_stage"),
        received_command=state.get("message"),
        level=logging.INFO,
    )
    result = persisted_result
    tool_results = [
        {
            "tool_call_id": _forced_tool_call_id(tool_name),
            "name": tool_name,
            "result": result,
        }
    ]
    next_state = update_conversation_state_for_page_reference(
        {
            **conversation_state,
            "pending_refund_action": None,
            "active_purchase": {
                "purchase_id": purchase_id,
                "product_name": pending_action["product_name"],
                "purchase_type": pending_action["purchase_type"],
            },
            "active_refund_context": _active_refund_context_from_workflow(
                pending_action,
                result,
            ),
            "active_workflow": _active_mutation_workflow_state(
                state,
                context,
                action,
                pending_action,
                result,
                last_tool_name=tool_name,
            ),
        },
        context.page_reference,
    )
    response = _build_refund_mutation_success_response(action, pending_action, result)
    state = log_trace_step(
        state,
        message="Confirmed refund workflow mutation completed.",
        event_type="tool_call.completed",
        data={
            "tool_name": tool_name,
            "result": result,
        },
    )
    state = log_trace_step(
        state,
        message="Confirmed refund workflow mutation completed.",
        event_type="workflow.mutation_completed",
        data=_mutation_log_payload(
            context,
            pending_action=pending_action,
            workflow=result,
            expected_status_or_stage=expected_stage,
            persisted_status_or_stage=result.get("refund_stage"),
            received_command=state.get("message"),
        ),
    )
    state = _log_mutation_event(
        state,
        context,
        "mutation_completed",
        "Refund mutation completed after persistence validation.",
        pending_action=pending_action,
        workflow=result,
        expected_status_or_stage=expected_stage,
        persisted_status_or_stage=result.get("refund_stage"),
        received_command=state.get("message"),
        level=logging.INFO,
    )
    state = _log_confirmation_command_event(
        state,
        context,
        event_type="workflow.refund_mutation_completed",
        message="Refund mutation completed after canonical command boundary.",
        active_refund_context=next_state.get("active_refund_context"),
        received_command=state.get("message"),
        pending_action=pending_action,
        workflow=result,
        level=logging.INFO,
    )
    return {
        **state,
        "tool_results": tool_results,
        "assistant_response": response,
        "conversation_state": next_state,
        "page_reference": context.page_reference,
        "side_effects": [
            {
                "type": "purchase_data_changed",
                "customer_id": context.customer_id,
                "purchase_ids": [purchase_id],
                "reason": "refund_mutation_completed",
            }
        ],
    }

def _blocked_refund_mutation_response(
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
    *,
    response: str,
    reason: str,
    workflow: dict[str, Any] | None = None,
) -> ChatGraphState:
    """Return a deterministic mutation-blocked response."""
    state = log_trace_step(
        state,
        message="Refund workflow mutation blocked before execution.",
        event_type="workflow.blocked",
        data={
            "kind": context.kind.value,
            "reason": reason,
            "workflow": workflow,
        },
        level=logging.WARNING,
    )
    return {
        **state,
        "tool_results": [],
        "assistant_response": response,
        "blocked_intent": context.blocked_refund_intent,
        "conversation_state": update_conversation_state_for_page_reference(
            conversation_state,
            context.page_reference,
        ),
        "page_reference": context.page_reference,
    }
