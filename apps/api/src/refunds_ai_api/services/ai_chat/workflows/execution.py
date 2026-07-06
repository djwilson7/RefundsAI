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
from refunds_ai_api.services.ai_chat.models import ChatGraphState, ModelToolCall
from refunds_ai_api.services.ai_chat.parsing import (
    parse_model_refund_eligibility_arguments,
    parse_model_refund_policy_arguments,
    parse_model_threshold_arguments,
)
from refunds_ai_api.services.ai_chat.resolution import build_unresolved_product_response
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
    REFUND_WORKFLOW_NOT_READY_RESPONSE,
    build_refund_workflow_action_not_wired_response,
)
from refunds_ai_api.services.ai_chat.workflows.classification import WorkflowKind
from refunds_ai_api.services.ai_chat.workflows.context import WorkflowContext
from refunds_ai_api.services.refund_policy_catalog import get_refund_policy


def block_invalid_workflow_transition(
    runtime: Any,
    state: ChatGraphState,
    context: WorkflowContext,
) -> ChatGraphState | None:
    """Return a blocked workflow response before any tool execution."""
    if context.workflow_continuation_intent is not None:
        normalized_state = normalize_conversation_state(state.get("conversation_state"))
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

    if context.kind is WorkflowKind.REFUND_MUTATION:
        blocked_reason = context.blocked_refund_intent or "refund_mutation"
        state = log_trace_step(
            state,
            message="Blocked refund request outside the current AI phase.",
            event_type="response.blocked",
            data={
                "reason": f"{blocked_reason}_not_ready",
                "model_context": build_model_context_summary(
                    state,
                    page_reference=context.page_reference,
                ),
                "object": context.classification.conversation_object.kind.value
                if context.classification is not None
                and context.classification.conversation_object is not None
                else None,
                "object_label": context.classification.conversation_object.label
                if context.classification is not None
                and context.classification.conversation_object is not None
                else None,
                "operation": context.classification.operation.operation.value
                if context.classification is not None
                and context.classification.operation is not None
                else None,
            },
            level=logging.WARNING,
        )
        state = log_trace_step(
            state,
            message="Workflow transition blocked before tool execution.",
            event_type="workflow.blocked",
            data={
                "kind": context.kind.value,
                "reason": f"{blocked_reason}_not_ready",
                "object": context.classification.conversation_object.kind.value
                if context.classification is not None
                and context.classification.conversation_object is not None
                else None,
                "object_label": context.classification.conversation_object.label
                if context.classification is not None
                and context.classification.conversation_object is not None
                else None,
                "operation": context.classification.operation.operation.value
                if context.classification is not None
                and context.classification.operation is not None
                else None,
            },
            level=logging.WARNING,
        )
        return {
            **state,
            "tool_results": [],
            "assistant_response": REFUND_WORKFLOW_NOT_READY_RESPONSE,
            "blocked_intent": context.blocked_refund_intent,
        }

    if context.unresolved_product_reference is not None:
        state = log_trace_step(
            state,
            message=(
                "Blocked product-specific refund response because entity resolution failed."
            ),
            event_type="response.blocked",
            data={
                "reason": "product_reference_unresolved",
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
                "reason": "product_reference_unresolved",
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
        eligibility_resolution=context.eligibility_resolution,
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
    return _complete_tool(
        state,
        tool_call_id=tool_call_id,
        tool_name="get_refund_eligibility",
        result=result,
        message="Backend refund-eligibility tool completed.",
    )


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
