"""Compact conversation and page context normalization for AI chat."""

from __future__ import annotations

from typing import Any

from .workflow import REFUND_CONTEXT_STAGES

EMPTY_CONVERSATION_STATE = {
    "selected_purchase_type": None,
    "selected_product": None,
    "selected_purchase_id": None,
    "selected_purchase_ids": [],
    "selected_scope_label": None,
    "selected_policy_scope": None,
    "selected_date_range": None,
    "selected_refund_purchase_ids": [],
    "selected_refund_context": None,
    "active_refund_context": None,
    "current_page": None,
    "active_workflow": None,
    "active_result_set": None,
    "active_purchase": None,
}

def normalize_conversation_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Return the compact, model-facing conversation state shape."""
    state = state or {}
    selected_purchase_type = state.get("selected_purchase_type")
    if selected_purchase_type not in {"digital", "physical", "subscription"}:
        selected_purchase_type = None

    selected_policy_scope = state.get("selected_policy_scope")
    if selected_policy_scope not in {
        "general",
        "product_type",
        "funds_release",
        "administrative_review",
    }:
        selected_policy_scope = None

    selected_date_range = state.get("selected_date_range")
    if not isinstance(selected_date_range, dict):
        selected_date_range = None

    selected_purchase_ids = state.get("selected_purchase_ids")
    if not isinstance(selected_purchase_ids, list):
        selected_purchase_ids = []

    selected_scope_label = state.get("selected_scope_label")
    if not isinstance(selected_scope_label, str) or not selected_scope_label.strip():
        selected_scope_label = None
    if (
        selected_scope_label is None
        and selected_purchase_ids
        and selected_purchase_type in {"digital", "physical", "subscription"}
    ):
        from .scopes import build_purchase_type_scope_label

        selected_scope_label = build_purchase_type_scope_label(selected_purchase_type)

    selected_refund_purchase_ids = state.get("selected_refund_purchase_ids")
    if not isinstance(selected_refund_purchase_ids, list):
        selected_refund_purchase_ids = []

    selected_refund_context = state.get("selected_refund_context")
    if not isinstance(selected_refund_context, str):
        selected_refund_context = None

    active_refund_context = normalize_active_refund_context(
        state.get("active_refund_context")
    )
    active_workflow = normalize_active_workflow(state.get("active_workflow"))
    active_result_set = normalize_active_result_set(state.get("active_result_set"))
    active_purchase = normalize_active_purchase(state.get("active_purchase"))

    return {
        **EMPTY_CONVERSATION_STATE,
        "selected_purchase_type": selected_purchase_type,
        "selected_product": state.get("selected_product")
        if isinstance(state.get("selected_product"), str)
        else None,
        "selected_purchase_id": state.get("selected_purchase_id")
        if isinstance(state.get("selected_purchase_id"), str)
        else None,
        "selected_purchase_ids": [
            str(purchase_id)
            for purchase_id in selected_purchase_ids
            if isinstance(purchase_id, str)
        ],
        "selected_scope_label": selected_scope_label,
        "selected_policy_scope": selected_policy_scope,
        "selected_date_range": selected_date_range,
        "selected_refund_purchase_ids": [
            str(purchase_id)
            for purchase_id in selected_refund_purchase_ids
            if isinstance(purchase_id, str)
        ],
        "selected_refund_context": selected_refund_context,
        "active_refund_context": active_refund_context,
        "current_page": state.get("current_page")
        if isinstance(state.get("current_page"), dict)
        else None,
        "active_workflow": active_workflow,
        "active_result_set": active_result_set,
        "active_purchase": active_purchase,
    }


def normalize_active_refund_context(value: Any) -> dict[str, Any] | None:
    """Return a validated active refund workflow context."""
    if not isinstance(value, dict):
        return None

    purchase_id = value.get("purchase_id")
    product_name = value.get("product_name")
    purchase_type = value.get("purchase_type")
    eligible = value.get("eligible")
    stage = value.get("stage")
    next_action = value.get("next_action")
    reason_codes = value.get("reason_codes")

    if not isinstance(purchase_id, str) or not purchase_id:
        return None
    if not isinstance(product_name, str) or not product_name:
        return None
    if purchase_type not in {"physical", "digital", "subscription"}:
        return None
    if not isinstance(eligible, bool):
        return None
    if stage not in REFUND_CONTEXT_STAGES:
        return None
    if next_action is not None and not isinstance(next_action, str):
        return None
    if not isinstance(reason_codes, list):
        reason_codes = []

    return {
        "purchase_id": purchase_id,
        "product_name": product_name,
        "purchase_type": purchase_type,
        "eligible": eligible,
        "stage": stage,
        "next_action": next_action,
        "reason_codes": [
            reason_code for reason_code in reason_codes if isinstance(reason_code, str)
        ],
    }


def normalize_active_workflow(value: Any) -> dict[str, Any] | None:
    """Return a validated active deterministic workflow context."""
    if not isinstance(value, dict):
        return None
    kind = value.get("kind")
    if kind not in {"account_fact", "refund_policy", "refund_eligibility"}:
        return None
    object_kind = value.get("object_kind")
    object_label = value.get("object_label")
    operation = value.get("operation")
    last_user_message = value.get("last_user_message")
    last_tool_name = value.get("last_tool_name")
    last_tool_result_summary = value.get("last_tool_result_summary")
    return {
        "kind": kind,
        "object_kind": object_kind if isinstance(object_kind, str) else None,
        "object_label": object_label if isinstance(object_label, str) else None,
        "operation": operation if isinstance(operation, str) else None,
        "last_user_message": last_user_message
        if isinstance(last_user_message, str)
        else None,
        "last_tool_name": last_tool_name if isinstance(last_tool_name, str) else None,
        "last_tool_result_summary": last_tool_result_summary
        if isinstance(last_tool_result_summary, dict)
        else {},
    }


def normalize_active_result_set(value: Any) -> dict[str, Any] | None:
    """Return a validated active result-set context for follow-up routing."""
    if not isinstance(value, dict):
        return None
    result_type = value.get("type")
    if result_type not in {
        "purchase_history",
        "date_range",
        "threshold",
        "subscriptions",
    }:
        return None
    purchase_ids = value.get("purchase_ids")
    if not isinstance(purchase_ids, list):
        purchase_ids = []
    sort = value.get("sort")
    label = value.get("label")
    return {
        "type": result_type,
        "purchase_ids": [
            str(purchase_id)
            for purchase_id in purchase_ids
            if isinstance(purchase_id, str)
        ],
        "sort": sort
        if sort in {"purchase_date_desc", "purchase_date_asc"}
        else None,
        "label": label if isinstance(label, str) and label.strip() else None,
    }


def normalize_active_purchase(value: Any) -> dict[str, Any] | None:
    """Return a validated active single-purchase context."""
    if not isinstance(value, dict):
        return None
    purchase_id = value.get("purchase_id")
    product_name = value.get("product_name")
    purchase_type = value.get("purchase_type")
    if not isinstance(purchase_id, str) or not purchase_id:
        return None
    if not isinstance(product_name, str) or not product_name:
        return None
    if purchase_type not in {"physical", "digital", "subscription"}:
        return None
    return {
        "purchase_id": purchase_id,
        "product_name": product_name,
        "purchase_type": purchase_type,
    }


def normalize_page_context(
    page_context: dict[str, Any] | None,
    *,
    fallback_purchase_id: str | None = None,
) -> dict[str, Any]:
    """Return the compact current-page context accepted from the frontend."""
    page_context = page_context or {}
    surface = page_context.get("surface")
    if surface not in {"purchase_history", "purchase_detail"}:
        surface = "purchase_detail" if fallback_purchase_id else "purchase_history"

    purchase_id = page_context.get("purchase_id") or fallback_purchase_id
    if not isinstance(purchase_id, str):
        purchase_id = None

    return {
        "surface": surface,
        "purchase_id": purchase_id if surface == "purchase_detail" else None,
    }
