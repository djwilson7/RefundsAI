"""Compact conversation-state trace summaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .helpers import _count, _id_items_preview, _mapping_or_none


def summarize_conversation_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return compact conversation state for structured logs."""
    if not isinstance(state, Mapping):
        return {}
    active_result_set = _mapping_or_none(state.get("active_result_set"))
    active_purchase = _mapping_or_none(state.get("active_purchase"))
    active_workflow = _mapping_or_none(state.get("active_workflow"))
    return {
        "selected_type": state.get("selected_purchase_type"),
        "selected_count": _count(state.get("selected_purchase_ids")),
        "scope": state.get("selected_scope_label"),
        "active_workflow": active_workflow.get("kind") if active_workflow else None,
        "active_result_set": summarize_active_result_set(active_result_set),
        "active_purchase": summarize_active_purchase(active_purchase),
        "pending_refund_action": summarize_pending_refund_action(
            state.get("pending_refund_action")
        ),
    }

def summarize_active_workflow(value: Any) -> dict[str, Any] | None:
    """Return active workflow summary."""
    active_workflow = _mapping_or_none(value)
    if active_workflow is None:
        return None
    return {
        "kind": active_workflow.get("kind"),
        "tool": active_workflow.get("last_tool_name"),
        "operation": active_workflow.get("operation"),
    }

def summarize_active_result_set(value: Any) -> dict[str, Any] | None:
    """Return active result-set summary."""
    active_result_set = _mapping_or_none(value)
    if active_result_set is None:
        return None
    purchase_ids = active_result_set.get("purchase_ids")
    return {
        "type": active_result_set.get("type"),
        "label": active_result_set.get("label"),
        "count": _count(purchase_ids),
        "items": _id_items_preview(purchase_ids),
    }

def summarize_active_purchase(value: Any) -> dict[str, Any] | None:
    """Return active purchase summary."""
    active_purchase = _mapping_or_none(value)
    if active_purchase is None:
        return None
    return {
        "purchase_id": active_purchase.get("purchase_id"),
        "product_name": active_purchase.get("product_name"),
        "purchase_type": active_purchase.get("purchase_type"),
    }

def summarize_pending_refund_action(value: Any) -> dict[str, Any] | None:
    """Return pending refund confirmation summary."""
    pending_action = _mapping_or_none(value)
    if pending_action is None:
        return None
    return {
        "action": pending_action.get("action"),
        "product_name": pending_action.get("product_name"),
        "purchase_type": pending_action.get("purchase_type"),
    }
