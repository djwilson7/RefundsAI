"""Deterministic model-facing context projection for final responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from refunds_ai_api.services.ai_chat.token_budget import (
    TextTokenCounter,
    count_serialized,
)

RequestCategory = Literal[
    "account_validation",
    "purchase_count",
    "purchase_count_by_group",
    "purchase_list",
    "purchase_filter",
    "purchase_detail",
    "selection",
    "refund_eligibility",
    "refund_confirmation",
    "refund_execution",
    "policy_lookup",
    "off_domain",
    "fallback",
]


@dataclass(frozen=True)
class ModelContextProjection:
    """Projected context intended for model handoff, not backend authority."""

    request_category: RequestCategory
    projection_reason: str
    projected_tool_results: list[dict[str, Any]] = field(default_factory=list)
    backend_state_refs: dict[str, Any] = field(default_factory=dict)
    raw_context_tokens: int = 0
    projected_context_tokens: int = 0
    token_savings_estimated: int = 0


def build_model_context_projection(
    *,
    state: dict[str, Any],
    tool_results: list[dict[str, Any]],
    counter: TextTokenCounter,
) -> ModelContextProjection:
    """Return compact model-facing tool context for the current request."""
    request_category = classify_request_category(state, tool_results)
    projected_tool_results = [
        project_tool_result(
            tool_result,
            request_category=request_category,
            state=state,
        )
        for tool_result in tool_results
        if isinstance(tool_result, dict)
    ]
    backend_state_refs = build_backend_state_refs(state)
    raw_context_tokens = count_serialized(tool_results, counter) if tool_results else 0
    projected_context_tokens = (
        count_serialized(projected_tool_results, counter) if projected_tool_results else 0
    )
    return ModelContextProjection(
        request_category=request_category,
        projection_reason=projection_reason(request_category),
        projected_tool_results=projected_tool_results,
        backend_state_refs=backend_state_refs,
        raw_context_tokens=raw_context_tokens,
        projected_context_tokens=projected_context_tokens,
        token_savings_estimated=max(0, raw_context_tokens - projected_context_tokens),
    )


def classify_request_category(
    state: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> RequestCategory:
    """Map existing deterministic workflow state to a model context category."""
    workflow_kind = state.get("workflow_kind")
    conversation_state = state.get("conversation_state")
    if not isinstance(conversation_state, dict):
        conversation_state = {}
    active_workflow = conversation_state.get("active_workflow")
    if workflow_kind is None and isinstance(active_workflow, dict):
        workflow_kind = active_workflow.get("kind")
    if workflow_kind == "refund_policy":
        return "policy_lookup"
    if workflow_kind == "refund_eligibility":
        return "refund_eligibility"
    if workflow_kind == "refund_mutation":
        if state.get("side_effects"):
            return "refund_execution"
        return "refund_confirmation"
    if workflow_kind == "off_domain":
        return "off_domain"

    operation = (
        active_workflow.get("operation")
        if isinstance(active_workflow, dict)
        else None
    )
    message = str(state.get("message") or "").casefold()
    tool_names = {str(result.get("name")) for result in tool_results}

    if tool_names == {"validate_customer_account"}:
        return "account_validation"
    if operation in {"select_first", "select_last", "select_latest", "select_previous"}:
        return "selection"
    if any(term in message for term in ("list", "show", "which", "what are")):
        return "purchase_list"
    if "get_purchase_count_by_amount_threshold" in tool_names:
        return "purchase_filter"
    if "get_purchase_history_by_date_range" in tool_names:
        return "purchase_filter"
    if conversation_state.get("selected_purchase_type"):
        return "purchase_count_by_group"
    if any(term in message for term in ("how many", "count", "number of")):
        return "purchase_count"
    if conversation_state.get("active_purchase"):
        return "purchase_detail"
    if workflow_kind == "account_fact":
        return "purchase_list"
    return "fallback"


def project_tool_result(
    tool_result: dict[str, Any],
    *,
    request_category: RequestCategory,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Project one raw tool result into the minimum model-facing shape."""
    name = tool_result.get("name")
    result = tool_result.get("result")
    if not isinstance(name, str) or not isinstance(result, dict):
        return {"name": name, "result": result}
    if name in {"get_customer_purchase_history", "get_purchase_history_by_date_range"}:
        return {
            "name": name,
            "result": project_purchase_history_result(
                result,
                request_category=request_category,
                state=state,
            ),
        }
    if name == "get_purchase_count_by_amount_threshold":
        return {
            "name": name,
            "result": {
                "count": result.get("count"),
                "total_amount_dollars": result.get("total_amount_dollars"),
                "threshold_dollars": result.get("threshold_dollars"),
                "comparison": result.get("comparison"),
                "matching_purchase_count": len(result.get("matching_purchase_ids", []))
                if isinstance(result.get("matching_purchase_ids"), list)
                else result.get("count"),
            },
        }
    if name == "get_refund_eligibility":
        return {
            "name": name,
            "result": project_refund_eligibility_result(result),
        }
    if name == "get_refund_policy":
        return {
            "name": name,
            "result": {
                "scope": result.get("scope"),
                "purchase_type": result.get("purchase_type"),
                "sections": result.get("sections", []),
                "source": result.get("source"),
            },
        }
    if name == "validate_customer_account":
        return {
            "name": name,
            "result": {
                "valid": result.get("valid"),
                "display_name": result.get("display_name"),
            },
        }
    return {"name": name, "result": result}


def project_purchase_history_result(
    result: dict[str, Any],
    *,
    request_category: RequestCategory,
    state: dict[str, Any],
) -> dict[str, Any]:
    conversation_state = state.get("conversation_state")
    if not isinstance(conversation_state, dict):
        conversation_state = {}
    selected_type = conversation_state.get("selected_purchase_type")
    purchases = result.get("purchases") if isinstance(result.get("purchases"), list) else []
    selected_ids = {
        str(purchase_id)
        for purchase_id in conversation_state.get("selected_purchase_ids", [])
        if isinstance(purchase_id, str)
    }
    if selected_ids:
        scoped_purchases = [
            purchase
            for purchase in purchases
            if isinstance(purchase, dict) and str(purchase.get("id")) in selected_ids
        ]
    elif isinstance(selected_type, str):
        scoped_purchases = [
            purchase
            for purchase in purchases
            if isinstance(purchase, dict)
            and purchase.get("purchase_type") == selected_type
        ]
    else:
        scoped_purchases = [purchase for purchase in purchases if isinstance(purchase, dict)]

    projected: dict[str, Any] = {
        "history_summary": result.get("history_summary"),
        "aggregates": project_aggregates(result.get("aggregates")),
    }
    date_range = result.get("date_range")
    if isinstance(date_range, dict):
        projected["date_range"] = date_range
    if isinstance(selected_type, str):
        projected["scope"] = selected_type
        projected["scope_summary"] = scoped_history_summary(
            result.get("history_summary"),
            selected_type,
        )
    if request_category in {
        "purchase_count_by_group",
        "purchase_list",
        "purchase_filter",
        "selection",
        "purchase_detail",
    }:
        projected["purchases"] = [compact_purchase_row(purchase) for purchase in scoped_purchases]
    elif request_category == "purchase_count" and len(scoped_purchases) <= 5:
        projected["purchases"] = [compact_purchase_row(purchase) for purchase in scoped_purchases]
    else:
        projected["purchase_count"] = len(scoped_purchases)
    return projected


def project_aggregates(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "total_purchase_count": value.get("total_purchase_count"),
        "total_amount_dollars": value.get("total_amount_dollars"),
        "by_purchase_type": value.get("by_purchase_type"),
    }


def scoped_history_summary(value: Any, purchase_type: str) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    by_type = value.get("by_purchase_type")
    if not isinstance(by_type, dict):
        return None
    scoped = by_type.get(purchase_type)
    return scoped if isinstance(scoped, dict) else None


def compact_purchase_row(purchase: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "product_name": purchase.get("product_name"),
        "purchase_type": purchase.get("purchase_type"),
        "amount_display": purchase.get("amount_display"),
        "purchased_date_display": purchase.get("purchased_date_display"),
        "status": purchase.get("status"),
    }
    return {key: value for key, value in fields.items() if value is not None}


def project_refund_eligibility_result(result: dict[str, Any]) -> dict[str, Any]:
    purchases = result.get("purchases") if isinstance(result.get("purchases"), list) else []
    return {
        "context": result.get("context"),
        "purchase_count": result.get("purchase_count"),
        "eligible_count": result.get("eligible_count"),
        "blocked_count": result.get("blocked_count"),
        "prepared_count": result.get("prepared_count"),
        "issued_count": result.get("issued_count"),
        "purchases": [
            compact_refund_eligibility_row(purchase)
            for purchase in purchases
            if isinstance(purchase, dict)
        ],
    }


def compact_refund_eligibility_row(purchase: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "product_name": purchase.get("product_name"),
        "purchase_type": purchase.get("purchase_type"),
        "amount_display": purchase.get("amount_display"),
        "refund_stage": purchase.get("refund_stage"),
        "can_enter_refund_workflow": purchase.get("can_enter_refund_workflow"),
        "required_action": purchase.get("required_action"),
        "refund_outcome": purchase.get("refund_outcome"),
        "refundable_amount_display": purchase.get("refundable_amount_display"),
        "reasons": purchase.get("reasons"),
    }
    return {
        key: value
        for key, value in fields.items()
        if value is not None and value != []
    }


def build_backend_state_refs(state: dict[str, Any]) -> dict[str, Any]:
    conversation_state = state.get("conversation_state")
    if not isinstance(conversation_state, dict):
        return {}
    active_result_set = conversation_state.get("active_result_set")
    active_purchase = conversation_state.get("active_purchase")
    refs: dict[str, Any] = {}
    if isinstance(active_result_set, dict):
        purchase_ids = active_result_set.get("purchase_ids")
        refs["active_result_set"] = {
            "type": active_result_set.get("type"),
            "label": active_result_set.get("label"),
            "count": len(purchase_ids) if isinstance(purchase_ids, list) else 0,
        }
    if isinstance(active_purchase, dict):
        refs["active_purchase"] = {
            "purchase_id": active_purchase.get("purchase_id"),
            "product_name": active_purchase.get("product_name"),
        }
    return refs


def projection_reason(request_category: RequestCategory) -> str:
    return {
        "purchase_count": "aggregate_only_for_count",
        "purchase_count_by_group": "scoped_group_summary_and_names",
        "purchase_list": "compact_purchase_rows",
        "purchase_filter": "filtered_summary_with_compact_rows",
        "refund_eligibility": "eligibility_fields_only",
        "policy_lookup": "policy_slice_only",
        "selection": "selected_scope_context",
        "off_domain": "no_account_context_required",
    }.get(request_category, "request_specific_projection")
