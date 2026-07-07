"""Deterministic workflow execution for AI chat tool orchestration."""

from __future__ import annotations

import logging
from typing import Any

from refunds_ai_api.services.ai_chat.dates import parse_model_date_range_arguments
from refunds_ai_api.services.ai_chat.logging import (
    build_model_context_summary,
    log_trace_step,
)
from refunds_ai_api.services.ai_chat.model_tool_execution import (
    execute_model_requested_tool_calls,
)
from refunds_ai_api.services.ai_chat.models import (
    ChatGraphState,
    EligibilityResolution,
    ModelToolCall,
)
from refunds_ai_api.services.ai_chat.parsing import (
    parse_model_refund_eligibility_arguments,
    parse_model_refund_policy_arguments,
    parse_model_threshold_arguments,
)
from refunds_ai_api.services.ai_chat.resolution import (
    build_unresolved_product_response,
    resolve_purchase_by_id,
)
from refunds_ai_api.services.ai_chat.scopes import (
    update_conversation_state,
    update_conversation_state_for_page_reference,
)
from refunds_ai_api.services.ai_chat.state import normalize_conversation_state
from refunds_ai_api.services.ai_chat.tools import (
    get_customer_purchase_history,
    get_purchase_count_by_amount_threshold,
    get_purchase_history_by_date_range,
    get_refund_eligibility,
)
from refunds_ai_api.services.ai_chat.workflow import (
    REFUND_WORKFLOW_CONFIRMATION_REQUIRED_RESPONSE,
    build_refund_confirmation_command_guidance,
    build_refund_confirmation_command_offer,
    build_refund_workflow_action_not_wired_response,
    is_refund_confirmation_boundary_reply,
    parse_refund_confirmation_command,
    parse_refund_workflow_confirmation_intent,
    parse_refund_workflow_decline_intent,
    parse_refund_workflow_mutation_action,
    refund_confirmation_command_for_purchase_type,
)
from refunds_ai_api.services.ai_chat.workflows.classification import WorkflowKind
from refunds_ai_api.services.ai_chat.workflows.context import WorkflowContext
from refunds_ai_api.services.ai_chat.workflows.objects import ConversationObjectKind
from refunds_ai_api.services.money import format_cents
from refunds_ai_api.services.refund_policy import RefundWorkflowError
from refunds_ai_api.services.refund_policy_catalog import get_refund_policy


def block_invalid_workflow_transition(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> ChatGraphState | None:
    """Return a blocked workflow response before any tool execution."""
    normalized_state = normalize_conversation_state(state.get("conversation_state"))
    if context.kind is WorkflowKind.REFUND_MUTATION:
        return _handle_refund_mutation_workflow(runtime, state, context, normalized_state)

    if context.workflow_continuation_intent is not None:
        active_refund_context = normalized_state.get("active_refund_context")
        if active_refund_context is not None:
            state = log_trace_step(
                state,
                message=(
                    "Resolved refund workflow continuation from active refund context."
                ),
                event_type="response.blocked",
                data={
                    "reason": "refund_workflow_action_not_wired",
                    "purchase_id": active_refund_context["purchase_id"],
                    "next_action": active_refund_context.get("next_action"),
                    "model_context": build_model_context_summary(
                        {
                            **state,
                            "conversation_state": normalized_state,
                            "blocked_intent": context.workflow_continuation_intent,
                        },
                        page_reference=context.page_reference,
                    ),
                },
                level=logging.WARNING,
            )
            state = log_trace_step(
                state,
                message="Workflow transition blocked before tool execution.",
                event_type="workflow.blocked",
                data={
                    "kind": context.kind.value,
                    "reason": "refund_workflow_action_not_wired",
                },
                level=logging.WARNING,
            )
            return {
                **state,
                "tool_results": [],
                "assistant_response": build_refund_workflow_action_not_wired_response(
                    active_refund_context
                ),
                "blocked_intent": context.workflow_continuation_intent,
                "conversation_state": update_conversation_state_for_page_reference(
                    normalized_state,
                    context.page_reference,
                ),
                "page_reference": context.page_reference,
            }

        state = log_trace_step(
            state,
            message=(
                "Blocked refund workflow continuation because no active refund "
                "context was available."
            ),
            event_type="response.blocked",
            data={
                "reason": "active_refund_context_required",
                "model_context": build_model_context_summary(
                    {
                        **state,
                        "conversation_state": normalized_state,
                        "blocked_intent": context.workflow_continuation_intent,
                    },
                    page_reference=context.page_reference,
                ),
            },
            level=logging.WARNING,
        )
        state = log_trace_step(
            state,
            message="Workflow transition blocked before tool execution.",
            event_type="workflow.blocked",
            data={
                "kind": context.kind.value,
                "reason": "active_refund_context_required",
            },
            level=logging.WARNING,
        )
        return {
            **state,
            "tool_results": [],
            "assistant_response": REFUND_WORKFLOW_CONFIRMATION_REQUIRED_RESPONSE,
            "blocked_intent": context.workflow_continuation_intent,
            "conversation_state": update_conversation_state_for_page_reference(
                normalized_state,
                context.page_reference,
            ),
            "page_reference": context.page_reference,
        }

    if context.unresolved_product_reference is not None:
        unresolved_reason = "product_reference_unresolved"
        if (
            context.eligibility_resolution is not None
            and context.eligibility_resolution.context == "scoped_product_type_mismatch"
        ):
            unresolved_reason = "scoped_product_resolution_type_mismatch"
        state = log_trace_step(
            state,
            message=(
                "Blocked product-specific refund response because entity resolution failed."
            ),
            event_type="response.blocked",
            data={
                "reason": unresolved_reason,
                "product_reference": context.unresolved_product_reference,
                "model_context": build_model_context_summary(
                    state,
                    page_reference=context.page_reference,
                ),
            },
            level=logging.WARNING,
        )
        state = log_trace_step(
            state,
            message="Workflow transition blocked before tool execution.",
            event_type="workflow.blocked",
            data={
                "kind": context.kind.value,
                "reason": unresolved_reason,
                "product_reference": context.unresolved_product_reference,
            },
            level=logging.WARNING,
        )
        return {
            **state,
            "tool_results": [],
            "assistant_response": build_unresolved_product_response(
                context.unresolved_product_reference
            ),
            "blocked_intent": "product_reference_unresolved",
            "conversation_state": update_conversation_state_for_page_reference(
                state.get("conversation_state"),
                context.page_reference,
            ),
            "page_reference": context.page_reference,
        }

    return None


def _handle_refund_mutation_workflow(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
) -> ChatGraphState:
    """Gate and execute refund mutations behind explicit confirmation."""
    pending_action = conversation_state.get("pending_refund_action")
    active_refund_context = conversation_state.get("active_refund_context")
    if isinstance(pending_action, dict) and parse_refund_workflow_decline_intent(
        state["message"]
    ):
        next_state = {
            **conversation_state,
            "pending_refund_action": None,
        }
        response = "No problem. I have not changed the refund process."
        state = _log_confirmation_event(
            state,
            context,
            reason="refund_mutation_declined",
            pending_action=pending_action,
            level=logging.INFO,
        )
        return {
            **state,
            "tool_results": [],
            "assistant_response": response,
            "blocked_intent": context.blocked_refund_intent,
            "conversation_state": update_conversation_state_for_page_reference(
                next_state,
                context.page_reference,
            ),
            "page_reference": context.page_reference,
        }

    if isinstance(pending_action, dict) and parse_refund_confirmation_command(
        state["message"]
    ) == pending_action.get("purchase_type"):
        return _execute_confirmed_refund_action(
            runtime,
            state,
            context,
            conversation_state,
            pending_action,
        )

    if isinstance(pending_action, dict) and parse_refund_workflow_confirmation_intent(
        state["message"]
    ):
        return _invalid_refund_confirmation_command_response(
            state,
            context,
            conversation_state,
            active_refund_context
            if isinstance(active_refund_context, dict)
            else {
                "purchase_id": pending_action["purchase_id"],
                "product_name": pending_action["product_name"],
                "purchase_type": pending_action["purchase_type"],
                "eligible": True,
                "stage": "awaiting_customer_confirmation",
                "next_action": pending_action.get("required_action"),
            },
            received_command=state["message"],
            matched_command=parse_refund_confirmation_command(state["message"]),
        )

    if (
        isinstance(active_refund_context, dict)
        and active_refund_context.get("confirmation_command")
        and is_refund_confirmation_boundary_reply(state["message"])
    ):
        return _handle_refund_confirmation_command_boundary(
            runtime,
            state,
            context,
            conversation_state,
            active_refund_context,
        )

    mutation_target = _resolve_refund_mutation_target(runtime, state, context)
    if mutation_target is None:
        response = (
            "Please choose one purchase by product name or order number before I "
            "start or issue a refund."
        )
        return _blocked_refund_mutation_response(
            state,
            context,
            conversation_state,
            response=response,
            reason="refund_mutation_target_required",
        )

    action = _resolve_refund_mutation_action(state["message"], mutation_target)
    workflow = runtime.application_service.get_refund_workflow(
        mutation_target["purchase_id"]
    )
    allowed, denial_response = _validate_refund_mutation_allowed(
        action,
        mutation_target,
        workflow,
    )
    if not allowed:
        return _blocked_refund_mutation_response(
            state,
            context,
            conversation_state,
            response=denial_response,
            reason=f"{action}_not_allowed",
            workflow=workflow,
        )

    active_refund_context = _active_refund_context_from_pending_action(
        {
            "action": action,
            "purchase_id": mutation_target["purchase_id"],
            "product_name": mutation_target["product_name"],
            "purchase_type": mutation_target["purchase_type"],
            "required_action": workflow.get("required_action"),
            "refundable_amount_cents": workflow.get("refundable_amount_cents"),
            "refund_outcome": workflow.get("refund_outcome"),
        },
        workflow,
    )
    next_state = update_conversation_state_for_page_reference(
        {
            **conversation_state,
            "pending_refund_action": None,
            "active_refund_context": active_refund_context,
            "active_purchase": {
                "purchase_id": mutation_target["purchase_id"],
                "product_name": mutation_target["product_name"],
                "purchase_type": mutation_target["purchase_type"],
            },
            "active_workflow": _active_mutation_workflow_state(
                state,
                context,
                action,
                {
                    "action": action,
                    "purchase_id": mutation_target["purchase_id"],
                    "product_name": mutation_target["product_name"],
                    "purchase_type": mutation_target["purchase_type"],
                    "required_action": workflow.get("required_action"),
                },
                workflow,
            ),
        },
        context.page_reference,
    )
    response = build_refund_confirmation_command_offer(active_refund_context)
    state = _log_confirmation_command_event(
        state,
        context,
        event_type="workflow.confirmation_command_generated",
        message="Generated canonical refund confirmation command.",
        active_refund_context=active_refund_context,
        workflow=workflow,
        expected_command=active_refund_context.get("confirmation_command"),
        level=logging.INFO,
    )
    return {
        **state,
        "tool_results": [],
        "assistant_response": response,
        "blocked_intent": context.blocked_refund_intent,
        "conversation_state": next_state,
        "page_reference": context.page_reference,
    }


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


def _resolve_refund_mutation_target(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> dict[str, Any] | None:
    """Return exactly one backend-owned purchase for a refund mutation."""
    customer_id = context.customer_id
    if runtime.application_service is None or customer_id is None:
        return None

    normalized_state = normalize_conversation_state(state.get("conversation_state"))
    active_refund_context = normalized_state.get("active_refund_context")
    if isinstance(active_refund_context, dict):
        return {
            "purchase_id": active_refund_context["purchase_id"],
            "product_name": active_refund_context["product_name"],
            "purchase_type": active_refund_context["purchase_type"],
        }

    conversation_object = (
        context.classification.conversation_object
        if context.classification is not None
        else None
    )
    if conversation_object is None:
        return None

    if conversation_object.kind is ConversationObjectKind.ACTIVE_RESULT_SET:
        if len(conversation_object.purchase_ids) != 1:
            return None
        purchase_id = conversation_object.purchase_ids[0]
    elif conversation_object.kind in {
        ConversationObjectKind.ACTIVE_PURCHASE,
        ConversationObjectKind.PAGE_PURCHASE,
    }:
        if not conversation_object.purchase_ids:
            return None
        purchase_id = conversation_object.purchase_ids[0]
    elif conversation_object.kind is ConversationObjectKind.PRODUCT_REFERENCE:
        resolved_purchase = context.resolved_purchase or context.resolved_context_purchase
        if resolved_purchase is None:
            return None
        return {
            "purchase_id": resolved_purchase["id"],
            "product_name": resolved_purchase["product_name"],
            "purchase_type": resolved_purchase["purchase_type"],
        }
    else:
        return None

    resolved_purchase = resolve_purchase_by_id(
        runtime.application_service,
        customer_id,
        purchase_id,
    )
    if resolved_purchase is None:
        return None
    return {
        "purchase_id": resolved_purchase["id"],
        "product_name": resolved_purchase["product_name"],
        "purchase_type": resolved_purchase["purchase_type"],
    }


def _handle_refund_confirmation_command_boundary(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
    active_refund_context: dict[str, Any],
) -> ChatGraphState:
    """Validate a canonical command before entering the mutation workflow."""
    expected_purchase_type = active_refund_context["purchase_type"]
    matched_purchase_type = parse_refund_confirmation_command(state["message"])
    expected_command = active_refund_context.get("confirmation_command")
    state = _log_confirmation_command_event(
        state,
        context,
        event_type="workflow.confirmation_command_received",
        message="Received refund confirmation command boundary input.",
        active_refund_context=active_refund_context,
        expected_command=expected_command,
        received_command=state["message"],
        matched_command=matched_purchase_type,
        level=logging.INFO,
    )
    if matched_purchase_type != expected_purchase_type:
        return _invalid_refund_confirmation_command_response(
            state,
            context,
            conversation_state,
            active_refund_context,
            received_command=state["message"],
            matched_command=matched_purchase_type,
        )

    pending_action = _pending_action_from_active_refund_context(active_refund_context)
    if pending_action is None:
        return _invalid_refund_confirmation_command_response(
            state,
            context,
            conversation_state,
            active_refund_context,
            received_command=state["message"],
            matched_command=matched_purchase_type,
        )

    verified_state = {
        **conversation_state,
        "pending_refund_action": pending_action,
    }
    state = _log_confirmation_command_event(
        state,
        context,
        event_type="workflow.confirmation_command_verified",
        message="Verified canonical refund confirmation command.",
        active_refund_context=active_refund_context,
        expected_command=expected_command,
        received_command=state["message"],
        matched_command=matched_purchase_type,
        pending_action=pending_action,
        level=logging.INFO,
    )
    state = _log_confirmation_command_event(
        state,
        context,
        event_type="workflow.refund_mutation_started",
        message="Starting refund mutation after canonical command verification.",
        active_refund_context=active_refund_context,
        expected_command=expected_command,
        received_command=state["message"],
        matched_command=matched_purchase_type,
        pending_action=pending_action,
        level=logging.INFO,
    )
    return _execute_confirmed_refund_action(
        runtime,
        state,
        context,
        verified_state,
        pending_action,
    )


def _invalid_refund_confirmation_command_response(
    state: ChatGraphState,
    context: WorkflowContext,
    conversation_state: dict[str, Any],
    active_refund_context: dict[str, Any],
    *,
    received_command: str,
    matched_command: str | None,
) -> ChatGraphState:
    """Reject generic or wrong confirmation text without mutating state."""
    expected_command = active_refund_context.get("confirmation_command")
    if not isinstance(expected_command, str) or not expected_command:
        command_config = refund_confirmation_command_for_purchase_type(
            active_refund_context.get("purchase_type")
        )
        expected_command = command_config["command"] if command_config else None
    state = _log_confirmation_command_event(
        state,
        context,
        event_type="workflow.confirmation_command_invalid",
        message="Rejected refund confirmation command boundary input.",
        active_refund_context=active_refund_context,
        expected_command=expected_command,
        received_command=received_command,
        matched_command=matched_command,
        level=logging.WARNING,
    )
    response = build_refund_confirmation_command_guidance(active_refund_context)
    next_state = update_conversation_state_for_page_reference(
        {
            **conversation_state,
            "pending_refund_action": None,
            "active_refund_context": active_refund_context,
        },
        context.page_reference,
    )
    return {
        **state,
        "tool_results": [],
        "assistant_response": response,
        "blocked_intent": context.blocked_refund_intent,
        "conversation_state": next_state,
        "page_reference": context.page_reference,
    }


def _pending_action_from_active_refund_context(
    active_refund_context: dict[str, Any],
) -> dict[str, Any] | None:
    """Build the internal pending action after command verification."""
    command_config = refund_confirmation_command_for_purchase_type(
        active_refund_context.get("purchase_type")
    )
    action = active_refund_context.get("confirmation_mutation_action")
    if action not in {"request_refund", "issue_refund"} and command_config is not None:
        action = command_config["mutation_action"]
    if action not in {"request_refund", "issue_refund"}:
        return None
    return {
        "action": action,
        "purchase_id": active_refund_context["purchase_id"],
        "product_name": active_refund_context["product_name"],
        "purchase_type": active_refund_context["purchase_type"],
        "required_action": active_refund_context.get("next_action"),
        "refundable_amount_cents": None,
        "refund_outcome": None,
    }


def _resolve_refund_mutation_action(
    message: str,
    mutation_target: dict[str, Any],
) -> str:
    """Return the mutation command requested for the resolved purchase."""
    action = parse_refund_workflow_mutation_action(message)
    if action is not None:
        return action
    del mutation_target
    return "request_refund"


def _validate_refund_mutation_allowed(
    action: str,
    mutation_target: dict[str, Any],
    workflow: dict[str, Any],
) -> tuple[bool, str]:
    """Return whether the current backend workflow allows the requested command."""
    product_name = mutation_target["product_name"]
    if action == "request_refund":
        if workflow.get("can_prepare_refund") is True:
            return True, ""
        return (
            False,
            (
                f"I cannot start a refund for {product_name} because the current "
                "refund status does not allow it."
            ),
        )

    if workflow.get("can_issue_funds") is True:
        return True, ""
    return (
        False,
        (
            f"I cannot issue the refund for {product_name} because the current "
            "refund status is not ready to release funds."
        ),
    )


def _expected_refund_stage_for_mutation(action: str) -> str:
    if action == "issue_refund":
        return "issued"
    return "prepared"


def _mutation_persistence_matches(action: str, workflow: dict[str, Any]) -> bool:
    return workflow.get("refund_stage") == _expected_refund_stage_for_mutation(action)


def _build_refund_validation_failed_response(action: str) -> str:
    if action == "issue_refund":
        return (
            "The refund was submitted, but I could not verify that the final "
            "refund status was saved. Please check the purchase status."
        )
    return (
        "I started the refund process, but I could not verify that the "
        "preparation step was saved. I did not issue funds."
    )


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


def _build_refund_mutation_success_response(
    action: str,
    pending_action: dict[str, Any],
    result: dict[str, Any],
) -> str:
    """Return a concise deterministic response after a confirmed mutation."""
    product_name = pending_action["product_name"]
    if action == "issue_refund":
        amount_cents = result.get("refundable_amount_cents")
        amount = format_cents(amount_cents) if isinstance(amount_cents, int) else None
        amount_text = f"{amount} " if amount is not None else "the refunded amount "
        if pending_action.get("purchase_type") == "subscription":
            return (
                "The subscription has been canceled and the refund process has "
                f"completed. You should see {amount_text}reflected to your "
                "original payment method within 3-10 business days. Do you have "
                "any other questions, or would you like further assistance?"
            )
        return (
            "The refund process has completed. You should see "
            f"{amount_text}reflected to your original payment method within "
            "3-10 business days. Do you have any other questions, or would you "
            "like further assistance?"
        )

    required_action = result.get("required_action")
    if required_action == "await_carrier_acceptance":
        return (
            "The return process has started, and your return label is ready. "
            "Please send the item back using the provided label. Once the "
            "carrier accepts or scans the package, the refund can be released."
        )
    if result.get("can_issue_funds") is True:
        return (
            f"The refund process has started for {product_name}. The refund has "
            "not been released yet."
        )
    return f"The refund process has started for {product_name}."


def _active_refund_context_from_workflow(
    pending_action: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Build active refund context after a mutation updates backend state."""
    stage = workflow.get("refund_stage")
    required_action = workflow.get("required_action")
    if stage == "issued":
        next_action = None
        active_stage = "issued"
    elif stage == "prepared":
        next_action = required_action if isinstance(required_action, str) else None
        if next_action == "none":
            next_action = None
        active_stage = "prepared"
    else:
        next_action = required_action if isinstance(required_action, str) else None
        active_stage = "eligibility_confirmed"
    reasons = workflow.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    active_refund_context: dict[str, Any] = {
        "purchase_id": pending_action["purchase_id"],
        "product_name": pending_action["product_name"],
        "purchase_type": pending_action["purchase_type"],
        "eligible": workflow.get("refund_stage") != "blocked",
        "stage": active_stage,
        "next_action": next_action,
        "reason_codes": [reason for reason in reasons if isinstance(reason, str)],
    }
    command_config = refund_confirmation_command_for_purchase_type(
        pending_action.get("purchase_type")
    )
    if (
        active_refund_context["eligible"] is True
        and active_stage in {"eligibility_confirmed", "awaiting_return_label", "prepared"}
        and command_config is not None
    ):
        backend_action = command_config["backend_action"]
        mutation_action = command_config["mutation_action"]
        confirmation_steps = list(command_config["steps"])
        if active_stage == "prepared" and next_action == "issue_funds":
            backend_action = "issue_funds"
            mutation_action = "issue_refund"
            confirmation_steps = ["issue the refund"]
        active_refund_context.update(
            {
                "confirmation_command": command_config["command"],
                "confirmation_backend_action": backend_action,
                "confirmation_mutation_action": mutation_action,
                "confirmation_steps": confirmation_steps,
            }
        )
    return active_refund_context


def _active_refund_context_from_pending_action(
    pending_action: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Build command-ready active refund context before any mutation is executed."""
    return _active_refund_context_from_workflow(pending_action, workflow)


def _active_mutation_workflow_state(
    state: ChatGraphState,
    context: WorkflowContext,
    action: str,
    pending_action: dict[str, Any],
    workflow: dict[str, Any],
    *,
    last_tool_name: str | None = None,
) -> dict[str, Any]:
    """Return compact active workflow metadata for refund mutation turns."""
    conversation_object = (
        context.classification.conversation_object
        if context.classification is not None
        else None
    )
    return {
        "kind": "refund_mutation",
        "object_kind": conversation_object.kind.value
        if conversation_object is not None
        else None,
        "object_label": pending_action.get("product_name"),
        "operation": action,
        "last_user_message": state["message"],
        "last_tool_name": last_tool_name,
        "last_tool_result_summary": {
            "purchase_id": pending_action.get("purchase_id"),
            "refund_stage": workflow.get("refund_stage"),
            "required_action": workflow.get("required_action"),
        },
    }


def execute_workflow(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    """Execute the deterministic backend tool for the resolved workflow."""
    state = log_trace_step(
        state,
        message="Executing deterministic workflow route.",
        event_type="workflow.executing",
        data={
            "kind": context.kind.value,
            "reason": context.classification.reason
            if context.classification is not None
            else None,
        },
    )

    if context.kind is WorkflowKind.ACCOUNT_FACT:
        return _execute_account_fact_workflow(runtime, state, context)
    if context.kind is WorkflowKind.REFUND_POLICY:
        return _execute_refund_policy_workflow(runtime, state, context)
    if context.kind is WorkflowKind.REFUND_ELIGIBILITY:
        return _execute_refund_eligibility_workflow(runtime, state, context)
    if context.kind is WorkflowKind.OFF_DOMAIN:
        state, tool_results = execute_model_requested_tool_calls(
            runtime,
            state,
            context.as_legacy_context(),
        )
        if not tool_results:
            state = log_trace_step(
                state,
                message="No supported account tool was requested for an off-domain message.",
                event_type="tool_call.skipped",
                data={"reason": "off_domain_intent"},
            )
        return state, tool_results

    return state, []


def finalize_workflow_state(
    state: ChatGraphState,
    context: WorkflowContext,
    tool_results: list[dict[str, Any]],
) -> ChatGraphState:
    """Update legacy and explicit workflow conversation state after execution."""
    conversation_state = update_conversation_state(
        state["message"],
        current_state=state.get("conversation_state"),
        tool_results=tool_results,
        policy_lookup_query=context.policy_lookup_query,
        eligibility_resolution=state.get("effective_eligibility_resolution")
        or context.eligibility_resolution,
        resolved_purchase=context.resolved_purchase
        or context.resolved_context_purchase,
        page_reference=context.page_reference,
    )
    conversation_state = _update_explicit_workflow_state(
        conversation_state,
        message=state["message"],
        context=context,
        tool_results=tool_results,
    )

    state = {
        **state,
        "tool_results": tool_results,
        "account_fact_intent": context.account_fact_intent,
        "policy_lookup_intent": context.policy_lookup_query is not None,
        "eligibility_lookup_intent": context.eligibility_resolution is not None,
        "resolved_context_purchase": context.resolved_context_purchase,
        "conversation_state": conversation_state,
        "page_reference": context.page_reference,
    }
    return log_trace_step(
        state,
        message="Workflow state updated.",
        event_type="workflow.state_updated",
        data={
            "kind": context.kind.value,
            "active_workflow": conversation_state.get("active_workflow"),
            "active_result_set": conversation_state.get("active_result_set"),
            "active_purchase": conversation_state.get("active_purchase"),
        },
    )


def _execute_account_fact_workflow(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    if context.threshold_query is not None:
        return _execute_threshold_tool(runtime, state, context)
    if context.date_range_query is not None:
        return _execute_date_range_tool(runtime, state, context)
    model_call = _first_supported_tool_call(state)
    if model_call is not None:
        if model_call.name == "get_purchase_count_by_amount_threshold":
            model_args = parse_model_threshold_arguments(model_call.arguments)
            if model_args is not None:
                return _execute_model_threshold_tool(
                    runtime,
                    state,
                    context,
                    model_call,
                    model_args,
                )
        if model_call.name == "get_purchase_history_by_date_range":
            model_args = parse_model_date_range_arguments(model_call.arguments)
            if model_args is not None:
                return _execute_model_date_range_tool(
                    runtime,
                    state,
                    context,
                    model_call,
                    model_args,
                )
    return _execute_purchase_history_tool(runtime, state, context)


def _execute_refund_policy_workflow(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    policy_query = context.policy_lookup_query
    if policy_query is None:
        model_call = _first_tool_call(state, "get_refund_policy")
        model_args = (
            parse_model_refund_policy_arguments(model_call.arguments)
            if model_call is not None
            else None
        )
        if model_call is not None and model_args is None:
            state = _log_invalid_arguments(state, model_call)
            return state, []
        if model_args is None:
            return state, []
        policy_query = model_args

    model_call = _first_supported_tool_call(state)
    state, tool_call_id = _prepare_deterministic_tool_execution(
        state,
        requested_call=model_call,
        target_tool_name="get_refund_policy",
        target_arguments=policy_query,
        override_reason="policy_lookup_intent",
        same_tool_override_reason="resolved_policy_context",
    )
    result = get_refund_policy(**policy_query)
    return _complete_tool(
        state,
        tool_call_id=tool_call_id,
        tool_name="get_refund_policy",
        result=result,
        message="Backend refund-policy tool completed.",
    )


def _execute_refund_eligibility_workflow(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    eligibility_resolution = context.eligibility_resolution
    resolved_purchase = context.resolved_purchase or context.resolved_context_purchase
    conversation_object = (
        context.classification.conversation_object
        if context.classification is not None
        else None
    )
    if (
        resolved_purchase is not None
        and conversation_object is not None
        and conversation_object.kind is ConversationObjectKind.PRODUCT_REFERENCE
    ):
        eligibility_resolution = EligibilityResolution(
            [resolved_purchase["id"]],
            "selected_purchase",
            resolved_purchase=resolved_purchase,
        )
    purchase_ids: list[str] | None = (
        eligibility_resolution.purchase_ids
        if eligibility_resolution is not None
        else None
    )
    eligibility_context: str | None = (
        eligibility_resolution.context
        if eligibility_resolution is not None
        else None
    )

    model_call = _first_tool_call(state, "get_refund_eligibility")
    if purchase_ids is None or eligibility_context is None:
        model_args = (
            parse_model_refund_eligibility_arguments(model_call.arguments)
            if model_call is not None
            else None
        )
        if model_call is not None and model_args is None:
            state = _log_invalid_arguments(state, model_call)
            return state, []
        if model_args is None:
            return state, []
        purchase_ids = model_args["purchase_ids"]
        eligibility_context = model_args["context"]

    model_call = _first_supported_tool_call(state)
    state, tool_call_id = _prepare_deterministic_tool_execution(
        state,
        requested_call=model_call,
        target_tool_name="get_refund_eligibility",
        target_arguments={
            "purchase_ids": purchase_ids,
            "context": eligibility_context,
        },
        override_reason="eligibility_lookup_intent",
        same_tool_override_reason="resolved_eligibility_context",
    )
    result = get_refund_eligibility(
        runtime.application_service,
        context.customer_id,
        purchase_ids=purchase_ids,
        context=eligibility_context,
    )
    if result.get("purchase_count") == 0:
        recovered_purchase = _recover_empty_eligibility_purchase(
            runtime,
            state,
            context,
        )
        if recovered_purchase is not None:
            retry_arguments = {
                "purchase_ids": [recovered_purchase["id"]],
                "context": "selected_purchase",
            }
            state = log_trace_step(
                state,
                message=(
                    "Retrying refund eligibility after zero purchases were evaluated."
                ),
                event_type="workflow.eligibility_reconciled",
                data={
                    "reason": "empty_eligibility_result",
                    "original_purchase_ids": purchase_ids,
                    "retry_purchase_ids": retry_arguments["purchase_ids"],
                    "product_name": recovered_purchase.get("product_name"),
                    "purchase_type": recovered_purchase.get("purchase_type"),
                },
                level=logging.INFO,
            )
            result = get_refund_eligibility(
                runtime.application_service,
                context.customer_id,
                purchase_ids=retry_arguments["purchase_ids"],
                context=retry_arguments["context"],
            )
            eligibility_resolution = EligibilityResolution(
                retry_arguments["purchase_ids"],
                retry_arguments["context"],
                resolved_purchase=recovered_purchase,
            )
        if result.get("purchase_count") == 0:
            state = log_trace_step(
                state,
                message=(
                    "Blocked final refund eligibility response because no purchase "
                    "was evaluated."
                ),
                event_type="response.blocked",
                data={
                    "reason": "empty_refund_eligibility_result",
                    "requested_purchase_ids": purchase_ids,
                    "resolved_purchase": recovered_purchase,
                },
                level=logging.WARNING,
            )
            state, tool_results = _complete_tool(
                state,
                tool_call_id=tool_call_id,
                tool_name="get_refund_eligibility",
                result=result,
                message="Backend refund-eligibility tool completed with no evaluated purchases.",
            )
            return {
                **state,
                "assistant_response": (
                    "I could not determine which purchase to check. Please choose "
                    "one purchase by product name or order number."
                ),
            }, tool_results
    return _complete_tool(
        {**state, "effective_eligibility_resolution": eligibility_resolution},
        tool_call_id=tool_call_id,
        tool_name="get_refund_eligibility",
        result=result,
        message="Backend refund-eligibility tool completed.",
    )


def _recover_empty_eligibility_purchase(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> dict[str, Any] | None:
    """Recover a concrete purchase when eligibility evaluated no rows."""
    if runtime.application_service is None or context.customer_id is None:
        return None

    for purchase in (context.resolved_purchase, context.resolved_context_purchase):
        if isinstance(purchase, dict) and isinstance(purchase.get("id"), str):
            return purchase

    conversation_state = normalize_conversation_state(state.get("conversation_state"))
    active_purchase = conversation_state.get("active_purchase")
    if isinstance(active_purchase, dict):
        purchase = resolve_purchase_by_id(
            runtime.application_service,
            context.customer_id,
            active_purchase.get("purchase_id"),
        )
        if purchase is not None:
            return purchase

    selected_purchase_id = conversation_state.get("selected_purchase_id")
    if isinstance(selected_purchase_id, str):
        purchase = resolve_purchase_by_id(
            runtime.application_service,
            context.customer_id,
            selected_purchase_id,
        )
        if purchase is not None:
            return purchase

    active_result_set = conversation_state.get("active_result_set")
    if isinstance(active_result_set, dict):
        purchase_ids = [
            purchase_id
            for purchase_id in active_result_set.get("purchase_ids", [])
            if isinstance(purchase_id, str)
        ]
        if len(purchase_ids) == 1:
            return resolve_purchase_by_id(
                runtime.application_service,
                context.customer_id,
                purchase_ids[0],
            )

    return None


def _execute_threshold_tool(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    threshold_query = context.threshold_query
    model_call = _first_supported_tool_call(state)
    state, tool_call_id = _prepare_deterministic_tool_execution(
        state,
        requested_call=model_call,
        target_tool_name="get_purchase_count_by_amount_threshold",
        target_arguments=threshold_query,
        override_reason="amount_threshold_intent",
        same_tool_override_reason="resolved_threshold_context",
    )
    result = get_purchase_count_by_amount_threshold(
        runtime.application_service,
        context.customer_id,
        threshold_cents=threshold_query["threshold_cents"],
        comparison=threshold_query["comparison"],
    )
    return _complete_tool(
        state,
        tool_call_id=tool_call_id,
        tool_name="get_purchase_count_by_amount_threshold",
        result=result,
        message="Backend purchase-threshold count tool completed.",
    )


def _execute_model_threshold_tool(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
    model_call: ModelToolCall,
    threshold_query: dict[str, Any],
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    state = _log_tool_executing(
        state,
        model_call,
        "get_purchase_count_by_amount_threshold",
        threshold_query,
    )
    result = get_purchase_count_by_amount_threshold(
        runtime.application_service,
        context.customer_id,
        threshold_cents=threshold_query["threshold_cents"],
        comparison=threshold_query["comparison"],
    )
    return _complete_tool(
        state,
        tool_call_id=model_call.id,
        tool_name="get_purchase_count_by_amount_threshold",
        result=result,
        message="Backend purchase-threshold count tool completed.",
    )


def _execute_date_range_tool(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    date_range_query = context.date_range_query
    model_call = _first_supported_tool_call(state)
    state, tool_call_id = _prepare_deterministic_tool_execution(
        state,
        requested_call=model_call,
        target_tool_name="get_purchase_history_by_date_range",
        target_arguments=date_range_query,
        override_reason="date_range_intent",
        same_tool_override_reason="resolved_date_range_context",
    )
    result = get_purchase_history_by_date_range(
        runtime.application_service,
        context.customer_id,
        start_date=date_range_query["start_date"],
        end_date=date_range_query["end_date"],
        timezone_name=date_range_query["timezone"],
        label=date_range_query.get("label"),
    )
    return _complete_tool(
        state,
        tool_call_id=tool_call_id,
        tool_name="get_purchase_history_by_date_range",
        result=result,
        message="Backend purchase-date-range tool completed.",
    )


def _execute_model_date_range_tool(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
    model_call: ModelToolCall,
    date_range_query: dict[str, Any],
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    state = _log_tool_executing(
        state,
        model_call,
        "get_purchase_history_by_date_range",
        date_range_query,
    )
    result = get_purchase_history_by_date_range(
        runtime.application_service,
        context.customer_id,
        start_date=date_range_query["start_date"],
        end_date=date_range_query["end_date"],
        timezone_name=date_range_query["timezone"],
        label=date_range_query.get("label"),
    )
    return _complete_tool(
        state,
        tool_call_id=model_call.id,
        tool_name="get_purchase_history_by_date_range",
        result=result,
        message="Backend purchase-date-range tool completed.",
    )


def _execute_purchase_history_tool(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    model_call = _first_supported_tool_call(state)
    state, tool_call_id = _prepare_deterministic_tool_execution(
        state,
        requested_call=model_call,
        target_tool_name="get_customer_purchase_history",
        target_arguments={},
        override_reason="account_domain_intent",
        same_tool_override_reason="resolved_account_fact_context",
    )
    result = get_customer_purchase_history(runtime.application_service, context.customer_id)
    state, tool_results = _complete_tool(
        state,
        tool_call_id=tool_call_id,
        tool_name="get_customer_purchase_history",
        result=result,
        message="Backend purchase-history tool completed.",
    )
    return state, tool_results


def _prepare_deterministic_tool_execution(
    state: ChatGraphState,
    *,
    requested_call: ModelToolCall | None,
    target_tool_name: str,
    target_arguments: dict[str, Any],
    override_reason: str,
    same_tool_override_reason: str,
) -> tuple[ChatGraphState, str]:
    """Log deterministic tool routing and return the effective tool call id."""
    if requested_call is None:
        state = _log_forced_tool(
            state,
            target_tool_name,
            override_reason,
            target_arguments,
        )
        return state, _forced_tool_call_id(target_tool_name)

    model_arguments = _parse_model_arguments_for_tool(requested_call)
    if model_arguments is None:
        state = _log_invalid_arguments(state, requested_call)
        state = _log_forced_tool(
            state,
            target_tool_name,
            override_reason,
            target_arguments,
        )
        return state, _forced_tool_call_id(target_tool_name)

    if requested_call.name != target_tool_name:
        state = _log_workflow_override(
            state,
            requested_tool_name=requested_call.name,
            target_tool_name=target_tool_name,
            reason=override_reason,
            target_arguments=target_arguments,
        )
        state = _log_tool_override(
            state,
            requested_tool_name=requested_call.name,
            target_tool_name=target_tool_name,
            reason=override_reason,
            target_arguments=target_arguments,
        )
        return state, requested_call.id

    if model_arguments != target_arguments:
        state = _log_workflow_override(
            state,
            requested_tool_name=requested_call.name,
            target_tool_name=target_tool_name,
            reason=same_tool_override_reason,
            target_arguments=target_arguments,
            model_arguments=model_arguments,
        )
        state = _log_tool_override(
            state,
            requested_tool_name=requested_call.name,
            target_tool_name=target_tool_name,
            reason=same_tool_override_reason,
            target_arguments=target_arguments,
            model_arguments=model_arguments,
        )

    return _log_tool_executing(
        state,
        requested_call,
        target_tool_name,
        target_arguments,
    ), requested_call.id


def _complete_tool(
    state: ChatGraphState,
    *,
    tool_call_id: str,
    tool_name: str,
    result: dict[str, Any],
    message: str,
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    tool_results = [
        {
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "result": result,
        }
    ]
    state = log_trace_step(
        state,
        message=message,
        event_type="tool_call.completed",
        data={
            "tool_name": tool_name,
            "result": result,
        },
    )
    state = log_trace_step(
        state,
        message="Deterministic workflow completed.",
        event_type="workflow.completed",
        data={
            "tool_name": tool_name,
            "result": result,
        },
    )
    return state, tool_results


def _log_forced_tool(
    state: ChatGraphState,
    tool_name: str,
    reason: str,
    target_arguments: dict[str, Any],
) -> ChatGraphState:
    labels = {
        "get_customer_purchase_history": (
            "No supported tool was requested for an account-domain message; "
            "forcing the read-only purchase-history tool."
        ),
        "get_purchase_count_by_amount_threshold": (
            "No supported tool was requested for a threshold purchase query; "
            "forcing the deterministic purchase-threshold count tool."
        ),
        "get_purchase_history_by_date_range": (
            "No supported tool was requested for a date-range purchase query; "
            "forcing the deterministic purchase-date-range tool."
        ),
        "get_refund_policy": (
            "No supported tool was requested for a refund-policy query; "
            "forcing the deterministic refund-policy tool."
        ),
        "get_refund_eligibility": (
            "No supported tool was requested for a refund-eligibility query; "
            "forcing the deterministic refund-eligibility tool."
        ),
    }
    return log_trace_step(
        state,
        message=labels[tool_name],
        event_type="tool_call.forced",
        data={
            "tool_name": tool_name,
            "reason": reason,
            **_trace_arguments(target_arguments),
        },
    )


def _log_workflow_override(
    state: ChatGraphState,
    *,
    requested_tool_name: str,
    target_tool_name: str,
    reason: str,
    target_arguments: dict[str, Any],
    model_arguments: dict[str, Any] | None = None,
) -> ChatGraphState:
    data = {
        "requested_tool_name": requested_tool_name,
        "tool_name": target_tool_name,
        "reason": reason,
        **_trace_arguments(target_arguments),
    }
    if model_arguments is not None:
        data["model_arguments"] = model_arguments
    return log_trace_step(
        state,
        message="Deterministic workflow overrode a conflicting model tool call.",
        event_type="workflow.tool_overridden",
        data=data,
    )


def _log_tool_override(
    state: ChatGraphState,
    *,
    requested_tool_name: str,
    target_tool_name: str,
    reason: str,
    target_arguments: dict[str, Any],
    model_arguments: dict[str, Any] | None = None,
) -> ChatGraphState:
    data = {
        "requested_tool_name": requested_tool_name,
        "tool_name": target_tool_name,
        "reason": reason,
        **_trace_arguments(target_arguments),
    }
    if model_arguments is not None:
        data["model_arguments"] = model_arguments
    return log_trace_step(
        state,
        message="Overriding model tool selection with deterministic workflow routing.",
        event_type="tool_call.overridden",
        data=data,
    )


def _log_tool_executing(
    state: ChatGraphState,
    requested_call: ModelToolCall,
    target_tool_name: str,
    target_arguments: dict[str, Any],
) -> ChatGraphState:
    return log_trace_step(
        state,
        message=f"Executing backend {target_tool_name} tool.",
        event_type="tool_call.executing",
        data={
            "tool_call_id": requested_call.id,
            "tool_name": target_tool_name,
            "model_arguments": requested_call.arguments,
            **_trace_arguments(target_arguments),
        },
    )


def _log_invalid_arguments(
    state: ChatGraphState,
    tool_call: ModelToolCall,
) -> ChatGraphState:
    return log_trace_step(
        state,
        message=f"Ignoring invalid {tool_call.name} tool arguments.",
        event_type="tool_call.ignored",
        data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
    )


def _parse_model_arguments_for_tool(
    tool_call: ModelToolCall,
) -> dict[str, Any] | None:
    if tool_call.name == "get_purchase_count_by_amount_threshold":
        return parse_model_threshold_arguments(tool_call.arguments)
    if tool_call.name == "get_purchase_history_by_date_range":
        return parse_model_date_range_arguments(tool_call.arguments)
    if tool_call.name == "get_refund_policy":
        return parse_model_refund_policy_arguments(tool_call.arguments)
    if tool_call.name == "get_refund_eligibility":
        return parse_model_refund_eligibility_arguments(tool_call.arguments)
    if tool_call.name == "get_customer_purchase_history":
        return {} if not tool_call.arguments else tool_call.arguments
    return None


def _first_supported_tool_call(state: ChatGraphState) -> ModelToolCall | None:
    for tool_call in state.get("tool_calls", []):
        if tool_call.name in {
            "get_customer_purchase_history",
            "get_purchase_count_by_amount_threshold",
            "get_purchase_history_by_date_range",
            "get_refund_policy",
            "get_refund_eligibility",
        }:
            return tool_call
    return None


def _first_tool_call(
    state: ChatGraphState,
    tool_name: str,
) -> ModelToolCall | None:
    for tool_call in state.get("tool_calls", []):
        if tool_call.name == tool_name:
            return tool_call
    return None


def _forced_tool_call_id(tool_name: str) -> str:
    return f"forced-{tool_name.replace('_', '-')}"


def _trace_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return legacy-compatible tool trace arguments."""
    return {key: value for key, value in arguments.items() if key != "label"}


def _update_explicit_workflow_state(
    conversation_state: dict[str, Any],
    *,
    message: str,
    context: WorkflowContext,
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    next_state = normalize_conversation_state(conversation_state)
    if (
        context.kind is WorkflowKind.REFUND_ELIGIBILITY
        and context.eligibility_resolution is not None
        and context.eligibility_resolution.context in {
            "product",
            "current_page",
            "selected_purchase",
        }
    ):
        next_state["selected_scope_label"] = None
    last_tool = tool_results[-1] if tool_results else None
    last_tool_name = last_tool.get("name") if isinstance(last_tool, dict) else None
    active_workflow = None
    if context.kind in {
        WorkflowKind.ACCOUNT_FACT,
        WorkflowKind.REFUND_POLICY,
        WorkflowKind.REFUND_ELIGIBILITY,
    }:
        conversation_object = (
            context.classification.conversation_object
            if context.classification is not None
            else None
        )
        operation = (
            context.classification.operation if context.classification is not None else None
        )
        active_workflow = {
            "kind": context.kind.value,
            "object_kind": conversation_object.kind.value
            if conversation_object is not None
            else None,
            "object_label": conversation_object.label
            if conversation_object is not None
            else None,
            "operation": operation.operation.value if operation is not None else None,
            "last_user_message": message,
            "last_tool_name": last_tool_name,
            "last_tool_result_summary": _summarize_workflow_tool_result(last_tool),
        }

    active_result_set = _build_active_result_set(next_state, context)
    active_purchase = _build_active_purchase(next_state)
    return {
        **next_state,
        "active_workflow": active_workflow,
        "active_result_set": active_result_set,
        "active_purchase": active_purchase,
    }


def _build_active_result_set(
    conversation_state: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, Any] | None:
    selected_ids = conversation_state.get("selected_purchase_ids")
    if not selected_ids:
        return None
    if (
        context.kind is WorkflowKind.REFUND_ELIGIBILITY
        and context.eligibility_resolution is not None
        and context.eligibility_resolution.context in {
            "product",
            "current_page",
            "selected_purchase",
        }
    ):
        return None

    previous_result_set = conversation_state.get("active_result_set")
    if (
        context.classification is not None
        and context.classification.reason == "active_result_set_follow_up"
        and isinstance(previous_result_set, dict)
        and previous_result_set.get("purchase_ids") == selected_ids
    ):
        return {
            **previous_result_set,
            "purchase_ids": selected_ids,
            "label": conversation_state.get("selected_scope_label")
            or previous_result_set.get("label"),
        }

    result_type = "purchase_history"
    if context.threshold_query is not None:
        result_type = "threshold"
    elif context.date_range_query is not None:
        result_type = "date_range"
    elif conversation_state.get("selected_purchase_type") == "subscription":
        result_type = "subscriptions"

    return {
        "type": result_type,
        "purchase_ids": selected_ids,
        "sort": "purchase_date_desc",
        "label": conversation_state.get("selected_scope_label"),
    }


def _build_active_purchase(
    conversation_state: dict[str, Any],
) -> dict[str, Any] | None:
    purchase_id = conversation_state.get("selected_purchase_id")
    product_name = conversation_state.get("selected_product")
    purchase_type = conversation_state.get("selected_purchase_type")
    if not all(isinstance(value, str) and value for value in (purchase_id, product_name)):
        return None
    if purchase_type not in {"digital", "physical", "subscription"}:
        return None
    return {
        "purchase_id": purchase_id,
        "product_name": product_name,
        "purchase_type": purchase_type,
    }


def _summarize_workflow_tool_result(
    tool_result: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(tool_result, dict):
        return {}
    result = tool_result.get("result")
    if not isinstance(result, dict):
        return {}
    if "aggregates" in result and isinstance(result["aggregates"], dict):
        return {
            "purchase_count": result["aggregates"].get("total_purchase_count"),
            "total_amount_dollars": result["aggregates"].get("total_amount_dollars"),
        }
    if "count" in result:
        return {
            "count": result.get("count"),
            "matching_purchase_count": len(result.get("matching_purchase_ids", [])),
        }
    if "purchase_count" in result:
        return {
            "purchase_count": result.get("purchase_count"),
            "eligible_count": result.get("eligible_count"),
            "blocked_count": result.get("blocked_count"),
        }
    if "sections" in result:
        sections = result.get("sections")
        return {
            "scope": result.get("scope"),
            "purchase_type": result.get("purchase_type"),
            "section_count": len(sections) if isinstance(sections, list) else 0,
        }
    return {}
