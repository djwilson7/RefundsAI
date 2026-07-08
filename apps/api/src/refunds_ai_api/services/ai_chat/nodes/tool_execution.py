"""Tool-execution graph node for AI chat."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.logging import log_trace_step
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.state import normalize_conversation_state
from refunds_ai_api.services.ai_chat.workflows import (
    block_invalid_workflow_transition,
    classify_workflow,
    execute_workflow,
    finalize_workflow_state,
    resolve_workflow_context,
)


def execute_tools_node(runtime: Any, state: ChatGraphState) -> ChatGraphState:
    """Execute model-requested or deterministic backend tools."""
    normalized_state = normalize_conversation_state(state.get("conversation_state"))
    state = {**state, "conversation_state": normalized_state}

    classification = classify_workflow(
        state["message"],
        conversation_state=normalized_state,
        page_context=state.get("page_context"),
        model_intent={"tool_calls": state.get("tool_calls", [])},
    )
    from refunds_ai_api.services.ai_chat.state import (
        determine_chat_domain,
        generate_conversation_snapshot,
        invalidate_incompatible_state,
    )
    domain = determine_chat_domain(classification.kind.value, state["message"])
    normalized_state = invalidate_incompatible_state(normalized_state, domain)
    state = {**state, "conversation_state": normalized_state}

    state = log_trace_step(
        state,
        message="Classified chat workflow before tool execution.",
        event_type="workflow.classified",
        data={
            "kind": classification.kind.value,
            "confidence": classification.confidence,
            "reason": classification.reason,
            "object": classification.conversation_object.kind.value
            if classification.conversation_object is not None
            else None,
            "object_label": classification.conversation_object.label
            if classification.conversation_object is not None
            else None,
            "operation": classification.operation.operation.value
            if classification.operation is not None
            else None,
            "operation_reason": classification.operation.reason
            if classification.operation is not None
            else None,
        },
    )
    state = {
        **state,
        "workflow_kind": classification.kind.value,
        "workflow_classification_reason": classification.reason,
    }

    context = resolve_workflow_context(runtime, state, classification)
    state = log_trace_step(
        state,
        message="Resolved workflow context before tool execution.",
        event_type="workflow.context_resolved",
        data={
            "kind": context.kind.value,
            "customer_id": context.customer_id,
            "threshold_query": context.threshold_query,
            "date_range_query": context.date_range_query,
            "policy_lookup_query": context.policy_lookup_query,
            "eligibility_resolution": context.eligibility_resolution,
            "resolved_purchase": context.resolved_purchase,
            "resolved_context_purchase": context.resolved_context_purchase,
            "unresolved_product_reference": context.unresolved_product_reference,
            "blocked_refund_intent": context.blocked_refund_intent,
        },
    )

    blocked_state = block_invalid_workflow_transition(runtime, state, context)
    if blocked_state is not None:
        return blocked_state

    state, tool_results = execute_workflow(runtime, state, context)

    finalized_state = finalize_workflow_state(state, context, tool_results)
    conv_state = finalized_state.get("conversation_state") or {}
    conv_state["_snapshot"] = generate_conversation_snapshot(conv_state)
    finalized_state["conversation_state"] = conv_state
    return finalized_state
