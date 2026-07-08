"""Conversation-state updates after deterministic workflow execution."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.state import normalize_conversation_state
from refunds_ai_api.services.ai_chat.workflows.classification import WorkflowKind
from refunds_ai_api.services.ai_chat.workflows.context import WorkflowContext


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
        history_summary = (
            result.get("history_summary")
            if isinstance(result.get("history_summary"), dict)
            else {}
        )
        return {
            "purchase_count": history_summary.get(
                "total_purchase_count",
                result["aggregates"].get("total_purchase_count"),
            ),
            "non_refunded_purchase_count": history_summary.get(
                "non_refunded_purchase_count"
            ),
            "refunded_purchase_count": history_summary.get("refunded_purchase_count"),
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
