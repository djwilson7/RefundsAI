"""Refund confirmation-command boundary handling."""

from __future__ import annotations

import logging
from typing import Any

from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.resolution import resolve_purchase_by_id
from refunds_ai_api.services.ai_chat.scopes import update_conversation_state_for_page_reference
from refunds_ai_api.services.ai_chat.state import normalize_conversation_state
from refunds_ai_api.services.ai_chat.workflow import (
    build_refund_confirmation_command_guidance,
    build_refund_confirmation_command_offer,
    is_refund_confirmation_boundary_reply,
    parse_refund_confirmation_command,
    parse_refund_workflow_confirmation_intent,
    parse_refund_workflow_decline_intent,
    refund_confirmation_command_for_purchase_type,
)
from refunds_ai_api.services.ai_chat.workflows.context import WorkflowContext
from refunds_ai_api.services.ai_chat.workflows.objects import ConversationObjectKind

from .logging import (
    _log_confirmation_command_event,
    _log_confirmation_event,
)
from .orchestration import (
    _blocked_refund_mutation_response,
    _execute_confirmed_refund_action,
)
from .state import (
    _active_mutation_workflow_state,
    _active_refund_context_from_pending_action,
    _pending_action_from_active_refund_context,
    _resolve_refund_mutation_action,
    _validate_refund_mutation_allowed,
)


def handle_refund_mutation_workflow(
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
