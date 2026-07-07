"""Public workflow execution router for AI chat orchestration."""

from __future__ import annotations

import logging
from typing import Any

from refunds_ai_api.services.ai_chat.logging import (
    build_model_context_summary,
    log_trace_step,
)
from refunds_ai_api.services.ai_chat.model_tool_execution import (
    execute_model_requested_tool_calls,
)
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.resolution import build_unresolved_product_response
from refunds_ai_api.services.ai_chat.scopes import (
    update_conversation_state,
    update_conversation_state_for_page_reference,
)
from refunds_ai_api.services.ai_chat.state import normalize_conversation_state
from refunds_ai_api.services.ai_chat.workflow import (
    REFUND_WORKFLOW_CONFIRMATION_REQUIRED_RESPONSE,
    build_refund_workflow_action_not_wired_response,
)
from refunds_ai_api.services.ai_chat.workflows.classification import WorkflowKind
from refunds_ai_api.services.ai_chat.workflows.context import WorkflowContext
from refunds_ai_api.services.ai_chat.workflows.refund_mutation.confirmation import (
    handle_refund_mutation_workflow,
)
from refunds_ai_api.services.ai_chat.workflows.state_updates import (
    _update_explicit_workflow_state,
)
from refunds_ai_api.services.ai_chat.workflows.tool_execution import (
    _execute_account_fact_workflow,
    _execute_refund_eligibility_workflow,
    _execute_refund_policy_workflow,
)


def block_invalid_workflow_transition(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> ChatGraphState | None:
    """Return a blocked workflow response before any tool execution."""
    normalized_state = normalize_conversation_state(state.get("conversation_state"))
    if context.kind is WorkflowKind.REFUND_MUTATION:
        return handle_refund_mutation_workflow(runtime, state, context, normalized_state)

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
