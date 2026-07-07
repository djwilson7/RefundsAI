"""Selected purchase scope and compact conversation-state update helpers."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.application import ApplicationService

from .models import EligibilityResolution
from .ranking import (
    has_reference_phrase,
    has_temporal_purchase_reference,
)
from .routing import (
    parse_policy_purchase_type,
    parse_purchase_type_filter,
)
from .state import normalize_conversation_state
from .workflow import refund_confirmation_command_for_purchase_type


def selected_purchase_ids_for_refund_context(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
    conversation_state: dict[str, Any],
) -> list[str]:
    """Resolve selected purchase ids for eligibility pronoun follow-ups."""
    normalized_message = message.casefold()
    selected_ids = conversation_state.get("selected_refund_purchase_ids") or conversation_state.get(
        "selected_purchase_ids"
    )
    if not selected_ids:
        return []

    if has_temporal_purchase_reference(normalized_message) or has_reference_phrase(
        normalized_message,
        "that one",
    ):
        from .resolution import resolve_purchase_from_selected_set

        selected_purchase = resolve_purchase_from_selected_set(
            application_service,
            customer_id,
            message,
            {**conversation_state, "selected_purchase_ids": selected_ids},
        )
        return [selected_purchase["id"]] if selected_purchase is not None else []

    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("those", "them", "these")
    ):
        return [str(purchase_id) for purchase_id in selected_ids if isinstance(purchase_id, str)]

    if has_reference_phrase(normalized_message, "one"):
        from .resolution import resolve_purchase_from_selected_set

        selected_purchase = resolve_purchase_from_selected_set(
            application_service,
            customer_id,
            message,
            {**conversation_state, "selected_purchase_ids": selected_ids},
        )
        return [selected_purchase["id"]] if selected_purchase is not None else []

    return []


def update_conversation_state(
    message: str,
    *,
    current_state: dict[str, Any] | None,
    tool_results: list[dict[str, Any]],
    policy_lookup_query: dict[str, Any] | None,
    eligibility_resolution: EligibilityResolution | None,
    resolved_purchase: dict[str, Any] | None,
    page_reference: dict[str, Any] | None,
) -> dict[str, Any]:
    """Update the compact state from deterministic tool outputs and routing."""
    next_state = normalize_conversation_state(current_state)

    explicit_type = parse_policy_purchase_type(message.casefold()) or parse_purchase_type_filter(
        message
    )
    if explicit_type is not None:
        next_state["selected_purchase_type"] = explicit_type

    if resolved_purchase is not None:
        active_refund_context = next_state.get("active_refund_context")
        selected_purchase_ids = next_state.get("selected_purchase_ids") or []
        next_state["pending_refund_product_reference"] = None
        next_state["selected_purchase_id"] = resolved_purchase["id"]
        next_state["selected_product"] = resolved_purchase["product_name"]
        next_state["selected_purchase_type"] = resolved_purchase["purchase_type"]
        if (
            selected_purchase_ids
            and resolved_purchase["id"] not in selected_purchase_ids
            and has_explicit_resolved_purchase_reference(message, resolved_purchase)
        ):
            next_state["selected_purchase_ids"] = []
            next_state["selected_scope_label"] = None
        if (
            isinstance(active_refund_context, dict)
            and active_refund_context.get("purchase_id") != resolved_purchase["id"]
        ):
            next_state["active_refund_context"] = None

    if page_reference is not None:
        next_state["current_page"] = page_reference

    if policy_lookup_query is not None:
        next_state["selected_policy_scope"] = policy_lookup_query["scope"]
        if policy_lookup_query.get("purchase_type") is not None:
            next_state["selected_purchase_type"] = policy_lookup_query["purchase_type"]

    if eligibility_resolution is not None and eligibility_resolution.purchase_ids:
        next_state["pending_refund_product_reference"] = None
        next_state["selected_refund_purchase_ids"] = eligibility_resolution.purchase_ids
        next_state["selected_refund_context"] = eligibility_resolution.context
        next_state["selected_purchase_ids"] = eligibility_resolution.purchase_ids
        if eligibility_resolution.resolved_purchase is not None:
            next_state["selected_purchase_id"] = eligibility_resolution.resolved_purchase["id"]
            next_state["selected_product"] = eligibility_resolution.resolved_purchase[
                "product_name"
            ]
            next_state["selected_purchase_type"] = eligibility_resolution.resolved_purchase[
                "purchase_type"
            ]

    for tool_result in tool_results:
        result = tool_result.get("result", {})
        if tool_result.get("name") == "get_purchase_count_by_amount_threshold":
            matching_purchase_ids = result.get("matching_purchase_ids")
            if isinstance(matching_purchase_ids, list):
                next_state["selected_purchase_ids"] = [
                    str(purchase_id)
                    for purchase_id in matching_purchase_ids
                    if isinstance(purchase_id, str)
                ]
                next_state["selected_scope_label"] = build_threshold_scope_label(result)
                next_state["selected_policy_scope"] = None
        if tool_result.get("name") == "get_purchase_history_by_date_range":
            date_range = result.get("date_range")
            next_state["selected_date_range"] = date_range
            next_state["selected_purchase_ids"] = [
                str(purchase["id"])
                for purchase in result.get("purchases", [])
                if isinstance(purchase.get("id"), str)
            ]
            next_state["selected_scope_label"] = build_date_range_scope_label(date_range)
            next_state["selected_policy_scope"] = None
        if tool_result.get("name") in {
            "get_customer_purchase_history",
            "get_purchase_history_by_date_range",
        }:
            selected_type = parse_purchase_type_filter(message)
            if selected_type is not None:
                matching_purchases = [
                    purchase
                    for purchase in result.get("purchases", [])
                    if purchase.get("purchase_type") == selected_type
                ]
                next_state["selected_purchase_ids"] = [
                    str(purchase["id"])
                    for purchase in matching_purchases
                    if isinstance(purchase.get("id"), str)
                ]
                next_state["selected_scope_label"] = build_purchase_type_scope_label(
                    selected_type
                )
                next_state["selected_policy_scope"] = None
                if len(matching_purchases) == 1:
                    next_state["selected_purchase_id"] = matching_purchases[0]["id"]
                    next_state["selected_product"] = matching_purchases[0]["product_name"]
        if tool_result.get("name") == "get_refund_eligibility":
            active_refund_context = build_active_refund_context_from_eligibility_result(
                result
            )
            next_state["active_refund_context"] = active_refund_context
            next_state["pending_refund_action"] = (
                build_pending_refund_action_from_eligibility_result(result)
            )
            if active_refund_context is not None:
                next_state["pending_refund_product_reference"] = None

    return next_state


def build_purchase_type_scope_label(purchase_type: str) -> str:
    """Return customer-facing scope labels for purchase-type aggregates."""
    labels = {
        "digital": "your digital purchases",
        "physical": "your physical purchases",
        "subscription": "your subscriptions",
    }
    return labels.get(purchase_type, "your purchases")


def build_date_range_scope_label(date_range: Any) -> str | None:
    """Return customer-facing scope labels for date-range aggregates."""
    if not isinstance(date_range, dict):
        return None
    label = date_range.get("label")
    if not isinstance(label, str) or not label.strip():
        return None
    normalized_label = label.casefold()
    if normalized_label in {"last week", "this week"}:
        return f"{normalized_label}'s purchases"
    return f"purchases from {label}"


def build_threshold_scope_label(result: dict[str, Any]) -> str | None:
    """Return customer-facing scope labels for amount-threshold aggregates."""
    comparison = result.get("comparison")
    threshold_dollars = result.get("threshold_dollars")
    if comparison not in {"gt", "gte", "lt", "lte"} or not isinstance(
        threshold_dollars,
        str,
    ):
        return None
    comparison_labels = {
        "gt": "over",
        "gte": "at least",
        "lt": "under",
        "lte": "at most",
    }
    return f"purchases {comparison_labels[comparison]} ${threshold_dollars}"


def has_explicit_resolved_purchase_reference(
    message: str,
    resolved_purchase: dict[str, Any],
) -> bool:
    """Return whether text explicitly names the resolved purchase or identifiers."""
    from .resolution import extract_product_reference, normalize_match_text

    normalized_message = normalize_match_text(message)
    for key in ("id", "product_name", "sku", "order_number"):
        value = resolved_purchase.get(key)
        if not isinstance(value, str):
            continue
        normalized_value = normalize_match_text(value)
        if normalized_value and normalized_value in normalized_message:
            return True
    return extract_product_reference(message) is not None


def build_active_refund_context_from_eligibility_result(
    result: dict[str, Any],
) -> dict[str, Any] | None:
    """Build active refund context from a single resolved eligibility result."""
    purchases = result.get("purchases")
    if not isinstance(purchases, list) or len(purchases) != 1:
        return None

    purchase = purchases[0]
    if not isinstance(purchase, dict):
        return None

    purchase_id = purchase.get("id")
    product_name = purchase.get("product_name")
    purchase_type = purchase.get("purchase_type")
    required_action = purchase.get("required_action")
    eligible = purchase.get("can_enter_refund_workflow") is True
    if (
        not isinstance(purchase_id, str)
        or not isinstance(product_name, str)
        or purchase_type not in {"physical", "digital", "subscription"}
    ):
        return None

    next_action = required_action if isinstance(required_action, str) else None
    if next_action == "none":
        next_action = None

    if not eligible:
        stage = "ineligible"
        next_action = None
    elif next_action == "generate_return_label":
        stage = "awaiting_return_label"
    else:
        stage = "eligibility_confirmed"

    reasons = purchase.get("reasons")
    if not isinstance(reasons, list):
        reasons = []

    active_refund_context: dict[str, Any] = {
        "purchase_id": purchase_id,
        "product_name": product_name,
        "purchase_type": purchase_type,
        "eligible": eligible,
        "stage": stage,
        "next_action": next_action,
        "reason_codes": [reason for reason in reasons if isinstance(reason, str)],
    }
    command_config = refund_confirmation_command_for_purchase_type(purchase_type)
    if eligible and command_config is not None:
        active_refund_context.update(
            {
                "confirmation_command": command_config["command"],
                "confirmation_backend_action": command_config["backend_action"],
                "confirmation_mutation_action": command_config["mutation_action"],
                "confirmation_steps": list(command_config["steps"]),
            }
        )
    return active_refund_context


def build_pending_refund_action_from_eligibility_result(
    result: dict[str, Any],
) -> dict[str, Any] | None:
    """Build an awaiting-confirmation refund action from one eligible physical result."""
    purchases = result.get("purchases")
    if not isinstance(purchases, list) or len(purchases) != 1:
        return None

    purchase = purchases[0]
    if not isinstance(purchase, dict):
        return None

    purchase_id = purchase.get("id")
    product_name = purchase.get("product_name")
    purchase_type = purchase.get("purchase_type")
    required_action = purchase.get("required_action")
    if (
        not isinstance(purchase_id, str)
        or not isinstance(product_name, str)
        or purchase_type != "physical"
        or required_action != "generate_return_label"
        or purchase.get("can_prepare_refund") is not True
    ):
        return None

    command_config = refund_confirmation_command_for_purchase_type(purchase_type)
    if command_config is None:
        return None

    return {
        "purchase_id": purchase_id,
        "product_name": product_name,
        "purchase_type": purchase_type,
        "action": command_config["mutation_action"],
        "required_action": required_action,
        "confirmation_expected_command": command_config["command"],
    }


def update_conversation_state_for_page_reference(
    current_state: dict[str, Any] | None,
    page_reference: dict[str, Any] | None,
) -> dict[str, Any]:
    """Update only current-page state when a request is blocked before tool execution."""
    next_state = normalize_conversation_state(current_state)
    if page_reference is not None:
        next_state["current_page"] = page_reference
    return next_state
