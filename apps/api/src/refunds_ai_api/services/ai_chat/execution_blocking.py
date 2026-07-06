"""Early blocking behavior for the AI chat tool-execution node."""

from __future__ import annotations

import logging
from typing import Any

from refunds_ai_api.services.ai_chat.logging import (
    build_model_context_summary,
    log_trace_step,
)
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.resolution import (
    build_unresolved_product_response,
    resolve_purchase_fact_context,
    resolve_refund_eligibility_query,
)
from refunds_ai_api.services.ai_chat.scopes import (
    update_conversation_state_for_page_reference,
)
from refunds_ai_api.services.ai_chat.state import normalize_conversation_state
from refunds_ai_api.services.ai_chat.workflow import (
    REFUND_WORKFLOW_CONFIRMATION_REQUIRED_RESPONSE,
    REFUND_WORKFLOW_NOT_READY_RESPONSE,
    build_refund_workflow_action_not_wired_response,
    parse_refund_workflow_mutation_intent,
)


def block_workflow_or_reference_response(
    runtime: Any,
    state: ChatGraphState,
    context: dict[str, Any],
) -> ChatGraphState | None:
    """Return a blocked response before tool execution when policy requires it."""
    customer_id = context["customer_id"]
    page_reference = context["page_reference"]
    unresolved_product_reference = context["unresolved_product_reference"]
    workflow_continuation_intent = context["workflow_continuation_intent"]
    if workflow_continuation_intent is not None:
        normalized_state = normalize_conversation_state(
            state.get("conversation_state")
        )
        active_refund_context = normalized_state.get("active_refund_context")
        if active_refund_context is not None:
            state = log_trace_step(
                state,
                message=(
                    "Resolved refund workflow continuation from active refund "
                    "context."
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
                            "blocked_intent": workflow_continuation_intent,
                        },
                        page_reference=page_reference,
                    ),
                },
                level=logging.WARNING,
            )
            return {
                **state,
                "tool_results": [],
                "assistant_response": build_refund_workflow_action_not_wired_response(
                    active_refund_context
                ),
                "blocked_intent": workflow_continuation_intent,
                "conversation_state": update_conversation_state_for_page_reference(
                    normalized_state,
                    page_reference,
                ),
                "page_reference": page_reference,
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
                        "blocked_intent": workflow_continuation_intent,
                    },
                    page_reference=page_reference,
                ),
            },
            level=logging.WARNING,
        )
        return {
            **state,
            "tool_results": [],
            "assistant_response": REFUND_WORKFLOW_CONFIRMATION_REQUIRED_RESPONSE,
            "blocked_intent": workflow_continuation_intent,
            "conversation_state": update_conversation_state_for_page_reference(
                normalized_state,
                page_reference,
            ),
            "page_reference": page_reference,
        }

    blocked_refund_intent = parse_refund_workflow_mutation_intent(state["message"])
    eligibility_resolution = resolve_refund_eligibility_query(
        state["message"],
        conversation_state=state.get("conversation_state"),
        page_context=state.get("page_context"),
        application_service=runtime.application_service,
        customer_id=customer_id,
    )
    resolved_context_purchase = resolve_purchase_fact_context(
        runtime.application_service,
        customer_id,
        state["message"],
        state.get("conversation_state"),
        state.get("page_context"),
    )
    context.update(
        {
            "blocked_refund_intent": blocked_refund_intent,
            "eligibility_resolution": eligibility_resolution,
            "resolved_context_purchase": resolved_context_purchase,
        }
    )
    if blocked_refund_intent is not None:
        state = log_trace_step(
            state,
            message="Blocked refund request outside the current AI phase.",
            event_type="response.blocked",
            data={
                "reason": f"{blocked_refund_intent}_not_ready",
                "model_context": build_model_context_summary(
                    state,
                    page_reference=page_reference,
                ),
            },
            level=logging.WARNING,
        )
        return {
            **state,
            "tool_results": [],
            "assistant_response": REFUND_WORKFLOW_NOT_READY_RESPONSE,
            "blocked_intent": blocked_refund_intent,
        }

    unresolved_reference = (
        eligibility_resolution.unresolved_product_reference
        if eligibility_resolution is not None
        and eligibility_resolution.unresolved_product_reference is not None
        else unresolved_product_reference
    )
    if unresolved_reference is not None:
        state = log_trace_step(
            state,
            message=(
                "Blocked product-specific refund response because entity "
                "resolution failed."
            ),
            event_type="response.blocked",
            data={
                "reason": "product_reference_unresolved",
                "product_reference": unresolved_reference,
                "model_context": build_model_context_summary(
                    state,
                    page_reference=page_reference,
                ),
            },
            level=logging.WARNING,
        )
        return {
            **state,
            "tool_results": [],
            "assistant_response": build_unresolved_product_response(
                unresolved_reference
            ),
            "blocked_intent": "product_reference_unresolved",
            "conversation_state": update_conversation_state_for_page_reference(
                state.get("conversation_state"),
                page_reference,
            ),
            "page_reference": page_reference,
        }
    return None
