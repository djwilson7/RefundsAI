"""Read-only deterministic workflow tool executors."""

from __future__ import annotations

import logging
from typing import Any

from refunds_ai_api.services.ai_chat.dates import parse_model_date_range_arguments
from refunds_ai_api.services.ai_chat.logging import log_trace_step
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
from refunds_ai_api.services.ai_chat.resolution import resolve_purchase_by_id
from refunds_ai_api.services.ai_chat.state import normalize_conversation_state
from refunds_ai_api.services.ai_chat.tools import (
    get_customer_purchase_history,
    get_purchase_count_by_amount_threshold,
    get_purchase_history_by_date_range,
    get_refund_eligibility,
)
from refunds_ai_api.services.ai_chat.workflows.context import WorkflowContext
from refunds_ai_api.services.ai_chat.workflows.objects import ConversationObjectKind
from refunds_ai_api.services.refund_policy_catalog import get_refund_policy

from .tool_routing import (
    _complete_tool,
    _first_supported_tool_call,
    _first_tool_call,
    _log_invalid_arguments,
    _log_tool_executing,
    _prepare_deterministic_tool_execution,
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
