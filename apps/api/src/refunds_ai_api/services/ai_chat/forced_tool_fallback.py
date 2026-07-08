"""Deterministic forced tool fallback for AI chat tool execution."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.logging import log_trace_step
from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.routing import has_account_fact_intent
from refunds_ai_api.services.ai_chat.tools import (
    get_customer_purchase_history,
    get_purchase_count_by_amount_threshold,
    get_purchase_history_by_date_range,
    get_refund_eligibility,
)
from refunds_ai_api.services.refund_policy_catalog import get_refund_policy


def apply_deterministic_forced_tool_fallback(
    runtime: Any,
    state: ChatGraphState,
    context: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> tuple[ChatGraphState, list[dict[str, Any]], bool]:
    """Run the narrowest deterministic fallback when no supported tool ran."""
    customer_id = context["customer_id"]
    threshold_query = context["threshold_query"]
    date_range_query = context["date_range_query"]
    policy_lookup_query = context["policy_lookup_query"]
    eligibility_resolution = context["eligibility_resolution"]
    resolved_context_purchase = context["resolved_context_purchase"]
    account_fact_intent = bool(state.get("account_fact_intent")) or has_account_fact_intent(
        state["message"]
    )
    if resolved_context_purchase is not None:
        account_fact_intent = True

    if not tool_results and eligibility_resolution is not None:
        state = log_trace_step(
            state,
            message=(
                "No supported tool was requested for a refund-eligibility query; "
                "forcing the deterministic refund-eligibility tool."
            ),
            event_type="tool_call.forced",
            data={
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
                "tool_call_id": "forced-get-refund-eligibility",
                "name": "get_refund_eligibility",
                "result": result,
            }
        )
        state = log_trace_step(
            state,
            message="Forced backend refund-eligibility tool completed.",
            event_type="tool_call.completed",
            data={
                "tool_name": "get_refund_eligibility",
                "result": result,
            },
        )
    elif not tool_results and policy_lookup_query is not None:
        state = log_trace_step(
            state,
            message=(
                "No supported tool was requested for a refund-policy query; "
                "forcing the deterministic refund-policy tool."
            ),
            event_type="tool_call.forced",
            data={
                "tool_name": "get_refund_policy",
                "reason": "policy_lookup_intent",
                **policy_lookup_query,
            },
        )
        result = get_refund_policy(**policy_lookup_query)
        tool_results.append(
            {
                "tool_call_id": "forced-get-refund-policy",
                "name": "get_refund_policy",
                "result": result,
            }
        )
        state = log_trace_step(
            state,
            message="Forced backend refund-policy tool completed.",
            event_type="tool_call.completed",
            data={
                "tool_name": "get_refund_policy",
                "result": result,
            },
        )
    elif not tool_results and threshold_query is not None:
        state = log_trace_step(
            state,
            message=(
                "No supported tool was requested for a threshold purchase query; "
                "forcing the deterministic purchase-threshold count tool."
            ),
            event_type="tool_call.forced",
            data={
                "tool_name": "get_purchase_count_by_amount_threshold",
                "reason": "amount_threshold_intent",
                "threshold_cents": threshold_query["threshold_cents"],
                "comparison": threshold_query["comparison"],
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
                "tool_call_id": "forced-get-purchase-count-by-amount-threshold",
                "name": "get_purchase_count_by_amount_threshold",
                "result": result,
            }
        )
        state = log_trace_step(
            state,
            message="Forced backend purchase-threshold count tool completed.",
            event_type="tool_call.completed",
            data={
                "tool_name": "get_purchase_count_by_amount_threshold",
                "customer_id": customer_id,
                "result": result,
            },
        )
    elif not tool_results and date_range_query is not None:
        state = log_trace_step(
            state,
            message=(
                "No supported tool was requested for a date-range purchase query; "
                "forcing the deterministic purchase-date-range tool."
            ),
            event_type="tool_call.forced",
            data={
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
                "tool_call_id": "forced-get-purchase-history-by-date-range",
                "name": "get_purchase_history_by_date_range",
                "result": result,
            }
        )
        state = log_trace_step(
            state,
            message="Forced backend purchase-date-range tool completed.",
            event_type="tool_call.completed",
            data={
                "tool_name": "get_purchase_history_by_date_range",
                "customer_id": customer_id,
                "result": result,
            },
        )
    elif not tool_results and account_fact_intent:
        state = log_trace_step(
            state,
            message=(
                "No supported tool was requested for an account-domain message; "
                "forcing the read-only purchase-history tool."
            ),
            event_type="tool_call.forced",
            data={
                "tool_name": "get_customer_purchase_history",
                "reason": "account_domain_intent",
            },
        )
        result = get_customer_purchase_history(runtime.application_service, customer_id)
        tool_results.append(
            {
                "tool_call_id": "forced-get-customer-purchase-history",
                "name": "get_customer_purchase_history",
                "result": result,
            }
        )
        state = log_trace_step(
            state,
            message="Forced backend purchase-history tool completed.",
            event_type="tool_call.completed",
            data={
                "tool_name": "get_customer_purchase_history",
                "customer_id": customer_id,
                "purchase_count": result["history_summary"]["total_purchase_count"],
                "result": result,
            },
        )
    elif not tool_results:
        state = log_trace_step(
            state,
            message="No supported account tool was requested for an off-domain message.",
            event_type="tool_call.skipped",
            data={"reason": "off_domain_intent"},
        )
    return state, tool_results, account_fact_intent
