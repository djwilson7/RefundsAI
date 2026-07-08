"""Confirmed refund mutation execution and persistence validation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from refunds_ai_api.services.ai_chat.logging import log_trace_step
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.resolution import resolve_purchase_by_id
from refunds_ai_api.services.ai_chat.scopes import update_conversation_state_for_page_reference
from refunds_ai_api.services.ai_chat.state import EMPTY_CONVERSATION_STATE
from refunds_ai_api.services.ai_chat.workflows.context import WorkflowContext
from refunds_ai_api.services.refund_confirmation import (
    authorize_persisted_refund_confirmation,
    refund_confirmation_command_for_purchase_type,
)
from refunds_ai_api.services.refund_policy import RefundWorkflowError

from ..tool_routing import _complete_tool, _start_tool_lifecycle
from .logging import _log_mutation_event
from .state import (
    _active_mutation_workflow_state,
    _active_refund_context_from_workflow,
    _build_refund_mutation_success_response,
    _build_refund_validation_failed_response,
    _expected_refund_stage_for_mutation,
    _mutation_persistence_matches,
    _validate_refund_mutation_allowed,
)

AUTO_ISSUE_AFTER_PREPARATION_PURCHASE_TYPES = {"digital", "subscription"}


def _execute_confirmed_refund_action(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
    pending_action: dict[str, Any],
) -> ChatGraphState:
    """Execute an already-confirmed refund action through backend services."""
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
    allowed, denial_response, explanation_context = _validate_refund_mutation_allowed(
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
            customer_explanation_context=explanation_context,
        )

    pending_action = {
        **pending_action,
        "purchase_id": resolved_purchase["id"],
        "product_name": resolved_purchase["product_name"],
        "purchase_type": resolved_purchase["purchase_type"],
        "required_action": workflow.get("required_action"),
        "confirmation_expected_command": pending_action.get("confirmation_expected_command"),
        "refundable_amount_cents": workflow.get("refundable_amount_cents"),
        "refund_outcome": workflow.get("refund_outcome"),
    }
    purchase_id = pending_action["purchase_id"]

    if _should_issue_after_preparation(action, pending_action):
        return _execute_confirmed_prepare_and_issue_refund(
            runtime,
            state,
            context,
            conversation_state,
            pending_action,
            workflow,
        )

    return _execute_single_confirmed_refund_action(
        runtime,
        state,
        context,
        conversation_state,
        pending_action,
        workflow,
    )


def _execute_single_confirmed_refund_action(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
    pending_action: dict[str, Any],
    workflow: dict[str, Any],
) -> ChatGraphState:
    """Execute and finish one confirmed refund mutation."""
    action = pending_action["action"]
    purchase_id = pending_action["purchase_id"]
    (
        state,
        result,
        tool_name,
        blocked_response,
        transition,
        tool_call_id,
    ) = _execute_refund_mutation_step(
        runtime,
        state,
        context,
        conversation_state,
        pending_action,
        workflow,
    )
    if blocked_response is not None:
        return blocked_response

    return _complete_confirmed_refund_action(
        state,
        context,
        conversation_state,
        action,
        pending_action,
        result,
        tool_name,
        tool_results=[
            {
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "result": result,
            }
        ],
        purchase_id=purchase_id,
        transitions=[transition] if transition is not None else [],
    )


def _execute_confirmed_prepare_and_issue_refund(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
    pending_action: dict[str, Any],
    workflow: dict[str, Any],
) -> ChatGraphState:
    """Prepare, verify, issue, and verify an immediate refund after confirmation."""
    purchase_id = pending_action["purchase_id"]
    (
        state,
        prepared_result,
        request_tool_name,
        blocked_response,
        prepared_transition,
        prepared_tool_call_id,
    ) = _execute_refund_mutation_step(
        runtime,
        state,
        context,
        conversation_state,
        pending_action,
        workflow,
    )
    if blocked_response is not None:
        return blocked_response

    mutation_target = {
        "purchase_id": purchase_id,
        "product_name": pending_action["product_name"],
        "purchase_type": pending_action["purchase_type"],
    }
    allowed, denial_response, explanation_context = _validate_refund_mutation_allowed(
        "issue_refund",
        mutation_target,
        prepared_result,
    )
    if not allowed:
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
                    prepared_result,
                ),
                "active_workflow": _active_mutation_workflow_state(
                    state,
                    context,
                    pending_action["action"],
                    pending_action,
                    prepared_result,
                    last_tool_name=request_tool_name,
                ),
                "customer_explanation_context": explanation_context,
            },
            context.page_reference,
        )
        return {
            **state,
            "tool_results": [
                {
                    "tool_call_id": prepared_tool_call_id,
                    "name": request_tool_name,
                    "result": prepared_result,
                }
            ],
            "assistant_response": denial_response,
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

    issue_pending_action = {
        **pending_action,
        "action": "issue_refund",
        "required_action": prepared_result.get("required_action"),
        "refundable_amount_cents": prepared_result.get("refundable_amount_cents"),
        "refund_outcome": prepared_result.get("refund_outcome"),
    }
    (
        state,
        issued_result,
        issue_tool_name,
        blocked_response,
        issued_transition,
        issued_tool_call_id,
    ) = _execute_refund_mutation_step(
        runtime,
        state,
        context,
        conversation_state,
        issue_pending_action,
        prepared_result,
    )
    if blocked_response is not None:
        return blocked_response

    return _complete_confirmed_refund_action(
        state,
        context,
        conversation_state,
        "issue_refund",
        issue_pending_action,
        issued_result,
        issue_tool_name,
        tool_results=[
            {
                "tool_call_id": prepared_tool_call_id,
                "name": request_tool_name,
                "result": prepared_result,
            },
            {
                "tool_call_id": issued_tool_call_id,
                "name": issue_tool_name,
                "result": issued_result,
            },
        ],
        purchase_id=purchase_id,
        transitions=[
            transition
            for transition in (prepared_transition, issued_transition)
            if transition is not None
        ],
    )


def _execute_refund_mutation_step(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
    pending_action: dict[str, Any],
    workflow: dict[str, Any],
) -> tuple[
    ChatGraphState,
    dict[str, Any],
    str,
    ChatGraphState | None,
    dict[str, Any] | None,
    str | None,
]:
    """Execute one backend mutation and verify the expected persisted stage."""
    action = pending_action["action"]
    purchase_id = pending_action["purchase_id"]
    expected_stage = _expected_refund_stage_for_mutation(action)
    expected_command = _expected_confirmation_command(pending_action)
    authorization = authorize_persisted_refund_confirmation(
        application_service=runtime.application_service,
        customer_id=context.customer_id,
        purchase_id=purchase_id,
        purchase_type=pending_action["purchase_type"],
        expected_confirmation_command=expected_command,
        action=action,
        current_workflow=workflow,
    )
    if not authorization.authorized:
        state = log_trace_step(
            state,
            message="Blocked refund mutation without persisted confirmation authorization.",
            event_type="workflow.confirmation_authorization_failed",
            data={
                "kind": context.kind.value,
                "action": action,
                "purchase_id": purchase_id,
                "purchase_type": pending_action["purchase_type"],
                "expected_command": expected_command,
                "denial_reason": authorization.denial_reason,
                "confirmation": authorization.confirmation,
            },
            level=logging.WARNING,
        )
        next_state = update_conversation_state_for_page_reference(
            {
                **conversation_state,
                "pending_refund_action": None,
            },
            context.page_reference,
        )
        blocked_response = {
            **state,
            "tool_results": [],
            "assistant_response": (
                "I could not verify your confirmation, so I have not changed the "
                "refund process. Please use the confirmation command again."
            ),
            "conversation_state": next_state,
            "page_reference": context.page_reference,
        }
        return state, {}, "", blocked_response, None, None

    confirmation_for_log = authorization.confirmation
    if _transition_consumes_confirmation(action, pending_action):
        try:
            confirmation_for_log = runtime.application_service.consume_refund_confirmation(
                customer_id=context.customer_id,
                purchase_id=purchase_id,
                purchase_type=pending_action["purchase_type"],
                expected_command=expected_command,
                consumed_at=datetime.now(UTC),
                consumed_by_action=action,
            )
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
                message="Blocked refund mutation because confirmation could not be consumed.",
                event_type="workflow.confirmation_consumption_failed",
                data={
                    "kind": context.kind.value,
                    "action": action,
                    "purchase_id": purchase_id,
                    "purchase_type": pending_action["purchase_type"],
                    "expected_command": expected_command,
                    "reason": str(exc),
                },
                level=logging.WARNING,
            )
            blocked_response = {
                **state,
                "tool_results": [],
                "assistant_response": (
                    "I could not verify your confirmation, so I have not changed the "
                    "refund process. Please use the confirmation command again."
                ),
                "conversation_state": next_state,
                "page_reference": context.page_reference,
            }
            return state, {}, "", blocked_response, None, None

    tool_name = "request_refund" if action == "request_refund" else "issue_refund"
    tool_arguments = {
        "purchase_id": purchase_id,
        "purchase_type": pending_action["purchase_type"],
        "action": action,
    }
    state, tool_call_id = _start_tool_lifecycle(
        state,
        tool_name,
        tool_arguments,
        source="deterministic_confirmed",
    )

    try:
        if action == "request_refund":
            result = runtime.application_service.request_refund(purchase_id)
        else:
            result = runtime.application_service.issue_refund(purchase_id)
    except RefundWorkflowError as exc:
        state, _ = _complete_tool(
            state,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            result={"error": str(exc)},
            message="Confirmed refund workflow mutation failed.",
            status="failed",
        )
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
        blocked_response = {
            **state,
            "tool_results": [],
            "assistant_response": (
                "I could not complete that refund request because the current "
                f"refund status no longer allows it: {exc}"
            ),
            "conversation_state": next_state,
            "page_reference": context.page_reference,
        }
        return state, {}, tool_name, blocked_response, None, tool_call_id

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
        blocked_response = {
            **state,
            "tool_results": [],
            "assistant_response": _build_refund_validation_failed_response(action),
            "conversation_state": next_state,
            "page_reference": context.page_reference,
        }
        state, _ = _complete_tool(
            state,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            result=persisted_result,
            message="Atomic refund mutation transition failed persistence validation.",
            status="failed",
        )
        return state, {}, tool_name, blocked_response, None, tool_call_id

    result = persisted_result
    state, _ = _complete_tool(
        state,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        result=result,
        message="Atomic refund mutation transition completed.",
    )
    transition = _refund_transition_summary(
        action=action,
        pending_action=pending_action,
        workflow_before=workflow,
        persisted_workflow=result,
        tool_name=tool_name,
        expected_stage=expected_stage,
        expected_command=expected_command,
        received_command=state.get("message"),
        confirmation=confirmation_for_log,
        tool_call_id=tool_call_id,
    )
    return state, result, tool_name, None, transition, tool_call_id


def _complete_confirmed_refund_action(
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
    action: str,
    pending_action: dict[str, Any],
    result: dict[str, Any],
    tool_name: str,
    *,
    tool_results: list[dict[str, Any]],
    purchase_id: str,
    transitions: list[dict[str, Any]],
) -> ChatGraphState:
    """Build final response, state, side effects, and completion traces."""
    expected_stage = _expected_refund_stage_for_mutation(action)
    tool_results = [tool_result for tool_result in tool_results if tool_result.get("name")]
    next_state = update_conversation_state_for_page_reference(
        _completed_refund_conversation_state(
            conversation_state,
            state=state,
            context=context,
            action=action,
            pending_action=pending_action,
            result=result,
            tool_name=tool_name,
            purchase_id=purchase_id,
        ),
        context.page_reference,
    )
    response = _build_refund_mutation_success_response(action, pending_action, result)
    state = log_trace_step(
        state,
        message="Refund mutation lifecycle completed after persisted confirmation.",
        event_type="workflow.refund_mutation_lifecycle",
        data=_refund_mutation_lifecycle_payload(
            context,
            pending_action=pending_action,
            result=result,
            transitions=transitions,
        ),
        level=logging.INFO,
    )
    state = log_trace_step(
        state,
        message="Refund workflow context cleared after successful mutation.",
        event_type="workflow.refund_context_cleared",
        data={
            "kind": context.kind.value,
            "cleared_pending_refund_action": True,
            "cleared_confirmation_command": True,
            "cleared_active_purchase": True,
            "cleared_active_refund_context": True,
            "cleared_active_workflow": True,
            "last_completed_refund": _completed_refund_summary(
                action=action,
                pending_action=pending_action,
                result=result,
                purchase_id=purchase_id,
            ),
        },
        level=logging.INFO,
    )
    state = log_trace_step(
        state,
        message="Refund mutation completed after persistence validation.",
        event_type="mutation_completed",
        data={
            "kind": context.kind.value,
            "purchase_id": purchase_id,
            "product_name": pending_action["product_name"],
            "purchase_type": pending_action["purchase_type"],
            "mutation_action": action,
            "expected_status_or_stage": expected_stage,
            "persisted_status_or_stage": result.get("refund_stage"),
            "transition_count": len(transitions),
        },
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


def _completed_refund_conversation_state(
    conversation_state: dict[str, Any],
    *,
    state: ChatGraphState,
    context: WorkflowContext,
    action: str,
    pending_action: dict[str, Any],
    result: dict[str, Any],
    tool_name: str,
    purchase_id: str,
) -> dict[str, Any]:
    """Return a clean post-mutation state so the next turn starts fresh."""
    del state, context, action, pending_action, result, tool_name, purchase_id
    return {
        **EMPTY_CONVERSATION_STATE,
        "current_page": conversation_state.get("current_page"),
    }


def _completed_refund_summary(
    *,
    action: str,
    pending_action: dict[str, Any],
    result: dict[str, Any],
    purchase_id: str,
) -> dict[str, Any]:
    return {
        "purchase_id": purchase_id,
        "product_name": pending_action["product_name"],
        "purchase_type": pending_action["purchase_type"],
        "action": action,
        "final_stage": result.get("refund_stage"),
        "required_action": result.get("required_action"),
    }


def _refund_transition_summary(
    *,
    action: str,
    pending_action: dict[str, Any],
    workflow_before: dict[str, Any],
    persisted_workflow: dict[str, Any],
    tool_name: str,
    expected_stage: str,
    expected_command: str,
    received_command: str | None,
    confirmation: dict[str, Any] | None,
    tool_call_id: str,
) -> dict[str, Any]:
    """Return one compact, audit-friendly atomic mutation transition summary."""
    return {
        "action": action,
        "tool": tool_name,
        "tool_call_id": tool_call_id,
        "from_stage": workflow_before.get("refund_stage"),
        "required_action_before": workflow_before.get("required_action"),
        "permission": {
            "can_prepare_refund": workflow_before.get("can_prepare_refund"),
            "can_issue_funds": workflow_before.get("can_issue_funds"),
            "validated": True,
        },
        "expected_stage": expected_stage,
        "persisted_stage": persisted_workflow.get("refund_stage"),
        "required_action_after": persisted_workflow.get("required_action"),
        "validation": "succeeded",
        "confirmation": _confirmation_lifecycle_summary(
            confirmation,
            expected_command=expected_command,
            received_command=received_command,
        ),
        "result": {
            "refund_stage": persisted_workflow.get("refund_stage"),
            "required_action": persisted_workflow.get("required_action"),
            "refundable_amount_cents": persisted_workflow.get("refundable_amount_cents"),
            "refund_outcome": persisted_workflow.get("refund_outcome"),
        },
        "purchase": {
            "purchase_id": pending_action.get("purchase_id"),
            "product_name": pending_action.get("product_name"),
            "purchase_type": pending_action.get("purchase_type"),
        },
    }


def _refund_mutation_lifecycle_payload(
    context: WorkflowContext,
    *,
    pending_action: dict[str, Any],
    result: dict[str, Any],
    transitions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return the grouped refund mutation lifecycle log payload."""
    confirmation = transitions[-1].get("confirmation") if transitions else {}
    return {
        "kind": context.kind.value,
        "customer_id": context.customer_id,
        "purchase": {
            "purchase_id": pending_action.get("purchase_id"),
            "product_name": pending_action.get("product_name"),
            "purchase_type": pending_action.get("purchase_type"),
        },
        "confirmation": confirmation,
        "transitions": [
            {
                "action": transition.get("action"),
                "from_stage": transition.get("from_stage"),
                "expected_stage": transition.get("expected_stage"),
                "persisted_stage": transition.get("persisted_stage"),
                "validation": transition.get("validation"),
                "required_action_before": transition.get("required_action_before"),
                "required_action_after": transition.get("required_action_after"),
                "permission": transition.get("permission"),
                "result": transition.get("result"),
            }
            for transition in transitions
        ],
        "result": {
            "final_stage": result.get("refund_stage"),
            "required_action": result.get("required_action"),
            "refundable_amount_cents": result.get("refundable_amount_cents"),
            "refund_outcome": result.get("refund_outcome"),
        },
    }


def _confirmation_lifecycle_summary(
    confirmation: dict[str, Any] | None,
    *,
    expected_command: str,
    received_command: str | None,
) -> dict[str, Any]:
    """Return bounded persisted confirmation facts for lifecycle logs."""
    confirmation = confirmation or {}
    return {
        "expected": expected_command,
        "received": received_command,
        "persisted_granted": confirmation.get("refund_confirmation_granted"),
        "matched": confirmation.get("refund_confirmation_matched"),
        "granted_at": confirmation.get("refund_confirmation_granted_at"),
        "source": confirmation.get("refund_confirmation_source"),
        "purchase_id": confirmation.get("refund_confirmation_purchase_id"),
        "customer_id": confirmation.get("refund_confirmation_customer_id"),
        "consumed_at": confirmation.get("refund_confirmation_consumed_at"),
        "consumed_by_action": confirmation.get("refund_confirmation_consumed_by_action"),
    }


def _should_issue_after_preparation(action: str, pending_action: dict[str, Any]) -> bool:
    """Return whether confirmation should complete issue after verified preparation."""
    return (
        action == "request_refund"
        and pending_action.get("purchase_type") in AUTO_ISSUE_AFTER_PREPARATION_PURCHASE_TYPES
    )


def _expected_confirmation_command(pending_action: dict[str, Any]) -> str:
    """Return the expected command carried by pending state or type config."""
    expected_command = pending_action.get("confirmation_expected_command")
    if isinstance(expected_command, str) and expected_command:
        return expected_command
    command_config = refund_confirmation_command_for_purchase_type(
        pending_action.get("purchase_type")
    )
    return command_config["command"] if command_config is not None else ""


def _transition_consumes_confirmation(
    action: str,
    pending_action: dict[str, Any],
) -> bool:
    """Return whether this atomic transition ends the confirmation scope."""
    return action == "issue_refund" or (
        action == "request_refund" and pending_action.get("purchase_type") == "physical"
    )


def _blocked_refund_mutation_response(
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
    *,
    response: str,
    reason: str,
    workflow: dict[str, Any] | None = None,
    customer_explanation_context: dict[str, Any] | None = None,
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
            "customer_explanation_context": customer_explanation_context,
        },
        level=logging.WARNING,
    )
    if customer_explanation_context is not None:
        conversation_state = {
            **conversation_state,
            "customer_explanation_context": customer_explanation_context,
        }
    conversation_state = {
        **conversation_state,
        "entity_extraction_result": (
            context.entity_extraction_result.as_dict()
            if context.entity_extraction_result is not None
            else None
        ),
    }
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
