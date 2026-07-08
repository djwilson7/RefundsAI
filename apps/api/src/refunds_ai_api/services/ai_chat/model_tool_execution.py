"""Model-requested tool execution for the AI chat tool-execution node."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.dates import parse_model_date_range_arguments
from refunds_ai_api.services.ai_chat.logging import log_trace_step
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.parsing import (
    parse_model_refund_eligibility_arguments,
    parse_model_refund_policy_arguments,
    parse_model_threshold_arguments,
)
from refunds_ai_api.services.ai_chat.tools import (
    get_customer_purchase_history,
    get_purchase_count_by_amount_threshold,
    get_purchase_history_by_date_range,
    get_refund_eligibility,
    validate_customer_account,
)
from refunds_ai_api.services.refund_policy_catalog import get_refund_policy


def execute_model_requested_tool_calls(
    runtime: Any,
    state: ChatGraphState,
    context: dict[str, Any],
) -> tuple[ChatGraphState, list[dict[str, Any]]]:
    """Execute supported model-requested tools after deterministic resolution."""
    tool_results: list[dict[str, Any]] = []
    customer_id = context["customer_id"]
    date_range_query = context["date_range_query"]
    policy_lookup_query = context["policy_lookup_query"]
    eligibility_resolution = context["eligibility_resolution"]
    resolved_context_purchase = context["resolved_context_purchase"]
    for tool_call in state.get("tool_calls", []):
        if tool_call.name == "validate_customer_account":
            if tool_call.arguments:
                state = log_trace_step(
                    state,
                    message="Ignoring invalid customer-validation tool arguments.",
                    event_type="tool_call.ignored",
                    data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                )
                continue

            state = log_trace_step(
                state,
                message="Executing backend active-customer validation tool.",
                event_type="tool_call.executing",
                data={
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.name,
                    "model_arguments": tool_call.arguments,
                    "effective_customer_id": customer_id,
                },
            )
            result = validate_customer_account(
                runtime.application_service,
                customer_id,
            )
            tool_results.append(
                {
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "result": result,
                }
            )
            state = log_trace_step(
                state,
                message="Backend active-customer validation tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": tool_call.name,
                    "customer_id": customer_id,
                    "result": result,
                },
            )
            continue

        if tool_call.name == "get_customer_purchase_history":
            if eligibility_resolution is not None:
                state = log_trace_step(
                    state,
                    message=(
                        "Overriding broad purchase-history tool selection with "
                        "the deterministic refund-eligibility tool."
                    ),
                    event_type="tool_call.overridden",
                    data={
                        "requested_tool_name": tool_call.name,
                        "tool_name": "get_refund_eligibility",
                        "reason": "eligibility_lookup_intent",
                        "purchase_ids": eligibility_resolution.purchase_ids,
                        "context": eligibility_resolution.context,
                    },
                )
                result = get_refund_eligibility(
                    runtime.application_service,
                    customer_id,
                    purchase_ids=eligibility_resolution.purchase_ids,
                    context=eligibility_resolution.context,
                )
                tool_results.append(
                    {
                        "tool_call_id": tool_call.id,
                        "name": "get_refund_eligibility",
                        "result": result,
                    }
                )
                state = log_trace_step(
                    state,
                    message="Backend refund-eligibility tool completed.",
                    event_type="tool_call.completed",
                    data={
                        "tool_name": "get_refund_eligibility",
                        "result": result,
                    },
                )
                continue

            if policy_lookup_query is not None:
                state = log_trace_step(
                    state,
                    message=(
                        "Overriding broad purchase-history tool selection with "
                        "the deterministic refund-policy tool."
                    ),
                    event_type="tool_call.overridden",
                    data={
                        "requested_tool_name": tool_call.name,
                        "tool_name": "get_refund_policy",
                        "reason": "policy_lookup_intent",
                        **policy_lookup_query,
                    },
                )
                result = get_refund_policy(**policy_lookup_query)
                tool_results.append(
                    {
                        "tool_call_id": tool_call.id,
                        "name": "get_refund_policy",
                        "result": result,
                    }
                )
                state = log_trace_step(
                    state,
                    message="Backend refund-policy tool completed.",
                    event_type="tool_call.completed",
                    data={
                        "tool_name": "get_refund_policy",
                        "result": result,
                    },
                )
                continue

            if date_range_query is not None:
                state = log_trace_step(
                    state,
                    message=(
                        "Overriding broad purchase-history tool selection with "
                        "the narrower deterministic purchase-date-range tool."
                    ),
                    event_type="tool_call.overridden",
                    data={
                        "requested_tool_name": tool_call.name,
                        "tool_name": "get_purchase_history_by_date_range",
                        "reason": "date_range_intent",
                        "start_date": date_range_query["start_date"],
                        "end_date": date_range_query["end_date"],
                        "timezone": date_range_query["timezone"],
                    },
                )
                result = get_purchase_history_by_date_range(
                    runtime.application_service,
                    customer_id,
                    start_date=date_range_query["start_date"],
                    end_date=date_range_query["end_date"],
                    timezone_name=date_range_query["timezone"],
                    label=date_range_query.get("label"),
                )
                tool_results.append(
                    {
                        "tool_call_id": tool_call.id,
                        "name": "get_purchase_history_by_date_range",
                        "result": result,
                    }
                )
                state = log_trace_step(
                    state,
                    message="Backend purchase-date-range tool completed.",
                    event_type="tool_call.completed",
                    data={
                        "tool_name": "get_purchase_history_by_date_range",
                        "customer_id": customer_id,
                        "result": result,
                    },
                )
                continue

            state = log_trace_step(
                state,
                message="Executing backend purchase-history tool.",
                event_type="tool_call.executing",
                data={
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.name,
                    "model_arguments": tool_call.arguments,
                    "effective_customer_id": customer_id,
                },
            )
            result = get_customer_purchase_history(runtime.application_service, customer_id)
            tool_results.append(
                {
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "result": result,
                }
            )

            state = log_trace_step(
                state,
                message="Backend purchase-history tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": tool_call.name,
                    "customer_id": customer_id,
                    "purchase_count": result["history_summary"]["total_purchase_count"],
                    "result": result,
                },
            )
            continue

        if tool_call.name == "get_purchase_count_by_amount_threshold":
            threshold_query = parse_model_threshold_arguments(tool_call.arguments)
            if threshold_query is None:
                state = log_trace_step(
                    state,
                    message="Ignoring invalid purchase-threshold tool arguments.",
                    event_type="tool_call.ignored",
                    data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                )
                continue

            state = log_trace_step(
                state,
                message="Executing backend purchase-threshold count tool.",
                event_type="tool_call.executing",
                data={
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.name,
                    "model_arguments": tool_call.arguments,
                    "effective_customer_id": customer_id,
                },
            )
            result = get_purchase_count_by_amount_threshold(
                runtime.application_service,
                customer_id,
                threshold_cents=threshold_query["threshold_cents"],
                comparison=threshold_query["comparison"],
            )
            tool_results.append(
                {
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "result": result,
                }
            )
            state = log_trace_step(
                state,
                message="Backend purchase-threshold count tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": tool_call.name,
                    "customer_id": customer_id,
                    "result": result,
                },
            )
            continue

        if tool_call.name == "get_refund_policy":
            policy_arguments = parse_model_refund_policy_arguments(tool_call.arguments)
            if policy_arguments is None:
                state = log_trace_step(
                    state,
                    message="Ignoring invalid refund-policy tool arguments.",
                    event_type="tool_call.ignored",
                    data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                )
                continue
            if policy_lookup_query is None:
                state = log_trace_step(
                    state,
                    message=(
                        "Ignoring refund-policy tool request because the "
                        "message was resolved as an account fact."
                    ),
                    event_type="tool_call.ignored",
                    data={
                        "tool_name": tool_call.name,
                        "arguments": tool_call.arguments,
                        "reason": "policy_intent_not_detected",
                    },
                )
                continue
            if policy_lookup_query is not None and policy_arguments != policy_lookup_query:
                state = log_trace_step(
                    state,
                    message=(
                        "Overriding refund-policy tool arguments with resolved "
                        "conversation context."
                    ),
                    event_type="tool_call.overridden",
                    data={
                        "requested_tool_name": tool_call.name,
                        "tool_name": "get_refund_policy",
                        "reason": "resolved_policy_context",
                        "model_arguments": policy_arguments,
                        **policy_lookup_query,
                    },
                )
                policy_arguments = policy_lookup_query

            state = log_trace_step(
                state,
                message="Executing backend refund-policy tool.",
                event_type="tool_call.executing",
                data={
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.name,
                    "model_arguments": tool_call.arguments,
                },
            )
            result = get_refund_policy(**policy_arguments)
            tool_results.append(
                {
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "result": result,
                }
            )
            state = log_trace_step(
                state,
                message="Backend refund-policy tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": tool_call.name,
                    "result": result,
                },
            )
            continue

        if tool_call.name == "get_refund_eligibility":
            eligibility_arguments = parse_model_refund_eligibility_arguments(
                tool_call.arguments
            )
            if eligibility_arguments is None:
                state = log_trace_step(
                    state,
                    message="Ignoring invalid refund-eligibility tool arguments.",
                    event_type="tool_call.ignored",
                    data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                )
                continue
            if eligibility_resolution is None and resolved_context_purchase is not None:
                state = log_trace_step(
                    state,
                    message=(
                        "Ignoring refund-eligibility tool request because the "
                        "message was resolved as an account fact."
                    ),
                    event_type="tool_call.ignored",
                    data={
                        "tool_name": tool_call.name,
                        "arguments": tool_call.arguments,
                        "reason": "eligibility_intent_not_detected",
                    },
                )
                continue
            if eligibility_resolution is not None:
                effective_purchase_ids = eligibility_resolution.purchase_ids
                effective_context = eligibility_resolution.context
                if (
                    eligibility_arguments["purchase_ids"] != effective_purchase_ids
                    or eligibility_arguments["context"] != effective_context
                ):
                    state = log_trace_step(
                        state,
                        message=(
                            "Overriding refund-eligibility tool arguments with "
                            "resolved conversation context."
                        ),
                        event_type="tool_call.overridden",
                        data={
                            "requested_tool_name": tool_call.name,
                            "tool_name": "get_refund_eligibility",
                            "reason": "resolved_eligibility_context",
                            "model_arguments": eligibility_arguments,
                            "purchase_ids": effective_purchase_ids,
                            "context": effective_context,
                        },
                    )
            else:
                effective_purchase_ids = eligibility_arguments["purchase_ids"]
                effective_context = eligibility_arguments["context"]

            state = log_trace_step(
                state,
                message="Executing backend refund-eligibility tool.",
                event_type="tool_call.executing",
                data={
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.name,
                    "model_arguments": tool_call.arguments,
                    "effective_purchase_ids": effective_purchase_ids,
                    "context": effective_context,
                },
            )
            result = get_refund_eligibility(
                runtime.application_service,
                customer_id,
                purchase_ids=effective_purchase_ids,
                context=effective_context,
            )
            tool_results.append(
                {
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "result": result,
                }
            )
            state = log_trace_step(
                state,
                message="Backend refund-eligibility tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": tool_call.name,
                    "result": result,
                },
            )
            continue

        if tool_call.name == "get_purchase_history_by_date_range":
            date_range_query = parse_model_date_range_arguments(tool_call.arguments)
            if date_range_query is None:
                state = log_trace_step(
                    state,
                    message="Ignoring invalid purchase-date-range tool arguments.",
                    event_type="tool_call.ignored",
                    data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                )
                continue

            state = log_trace_step(
                state,
                message="Executing backend purchase-date-range tool.",
                event_type="tool_call.executing",
                data={
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.name,
                    "model_arguments": tool_call.arguments,
                    "effective_customer_id": customer_id,
                },
            )
            result = get_purchase_history_by_date_range(
                runtime.application_service,
                customer_id,
                start_date=date_range_query["start_date"],
                end_date=date_range_query["end_date"],
                timezone_name=date_range_query["timezone"],
                label=date_range_query.get("label"),
            )
            tool_results.append(
                {
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "result": result,
                }
            )
            state = log_trace_step(
                state,
                message="Backend purchase-date-range tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": tool_call.name,
                    "customer_id": customer_id,
                    "result": result,
                },
            )
            continue

        state = log_trace_step(
            state,
            message="Ignoring unsupported model-requested tool.",
            event_type="tool_call.ignored",
            data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
        )
    return state, tool_results
