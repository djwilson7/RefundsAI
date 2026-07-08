"""System prompt and compact model-context prompt construction."""

from __future__ import annotations

import json
from typing import Any

from refunds_ai_api.services.money import format_cents

from .logging import short_id, summarize_tool_results_for_context
from .state import normalize_conversation_state

SYSTEM_PROMPT = (
    "You are RefundsAI's customer support assistant. For purchase-history "
    "questions, call the relevant read-only purchase tool before answering. For "
    "refund policy questions, call get_refund_policy before answering. For refund "
    "eligibility questions, call get_refund_eligibility before answering. Use only "
    "tool-provided purchase data for counts, totals, purchase types, statuses, "
    "and dates. Use only tool-provided refund policy data for policy explanations. "
    "Use only tool-provided refund eligibility data for eligibility explanations. "
    "Refund process changes are allowed only through explicit confirmation-gated "
    "context. Do not claim a refund was started, prepared, or issued unless "
    "available context says that action completed. Keep the conversation grounded in the "
    "customer's account, account history, purchases, orders, account activity, "
    "and refund flows. If the customer asks about unrelated topics, briefly and "
    "gracefully redirect them to account, purchase, order, activity, or refund "
    "topics you can help with. Return plain standard text only. Do not use "
    "Markdown, bullets, numbered lists, headings, tables, code blocks, links, or "
    "other markup."
)

def build_compact_model_context_message(
    state: dict[str, Any],
    *,
    tool_results: list[dict[str, Any]] | None = None,
    page_reference: dict[str, Any] | None = None,
    application_service: Any | None = None,
) -> dict[str, str] | None:
    """Return a small model-visible context message for follow-up grounding."""
    payload = compact_model_context_payload(
        state,
        tool_results=tool_results,
        page_reference=page_reference,
        application_service=application_service,
    )
    if not payload:
        return None

    return {
        "role": "user",
        "content": (
            "Compact conversation context for resolving follow-up references: "
            f"{json.dumps(payload, default=str, sort_keys=True)}"
        ),
    }


def compact_model_context_payload(
    state: dict[str, Any],
    *,
    tool_results: list[dict[str, Any]] | None = None,
    page_reference: dict[str, Any] | None = None,
    application_service: Any | None = None,
) -> dict[str, Any]:
    """Return only model-relevant state, without transcript or page payloads."""
    conversation_state = normalize_conversation_state(state.get("conversation_state"))
    payload: dict[str, Any] = {}

    compact_state: dict[str, Any] = {}
    for key in (
        "selected_purchase_type",
        "selected_product",
        "selected_purchase_id",
        "selected_scope_label",
        "selected_policy_scope",
        "selected_refund_context",
    ):
        value = conversation_state.get(key)
        if value:
            compact_state[key] = value

    selected_purchase_ids = [
        str(purchase_id)
        for purchase_id in conversation_state.get("selected_purchase_ids", [])
        if isinstance(purchase_id, str)
    ]
    if selected_purchase_ids:
        compact_state["selected_purchase_ids"] = {
            "count": len(selected_purchase_ids),
            "ids": [short_id(purchase_id) for purchase_id in selected_purchase_ids[:5]],
        }

    selected_refund_purchase_ids = [
        str(purchase_id)
        for purchase_id in conversation_state.get("selected_refund_purchase_ids", [])
        if isinstance(purchase_id, str)
    ]
    if selected_refund_purchase_ids:
        compact_state["selected_refund_purchase_ids"] = {
            "count": len(selected_refund_purchase_ids),
            "ids": [
                short_id(purchase_id) for purchase_id in selected_refund_purchase_ids[:5]
            ],
        }

    active_refund_context = conversation_state.get("active_refund_context")
    if isinstance(active_refund_context, dict):
        compact_state["active_refund_context"] = {
            key: active_refund_context[key]
            for key in (
                "purchase_id",
                "product_name",
                "purchase_type",
                "eligible",
                "stage",
                "next_action",
                "confirmation_command",
                "confirmation_backend_action",
                "confirmation_steps",
            )
            if key in active_refund_context
        }

    pending_refund_action = conversation_state.get("pending_refund_action")
    if isinstance(pending_refund_action, dict):
        compact_state["pending_refund_action"] = {
            key: pending_refund_action[key]
            for key in (
                "action",
                "purchase_id",
                "product_name",
                "purchase_type",
                "required_action",
            )
            if key in pending_refund_action
        }

    customer_explanation_context = conversation_state.get("customer_explanation_context")
    if isinstance(customer_explanation_context, dict):
        compact_state["customer_explanation_context"] = customer_explanation_context

    current_page = page_reference or conversation_state.get("current_page")
    if isinstance(current_page, dict) and current_page.get("surface") == "purchase_detail":
        current_page_purchase = current_page.get("purchase")
        if not isinstance(current_page_purchase, dict):
            current_page_purchase = current_page
        compact_page_purchase: dict[str, Any] = {}
        purchase_id = current_page.get("purchase_id") or current_page_purchase.get("id")
        if purchase_id:
            compact_page_purchase["purchase_id"] = purchase_id
        for key in ("product_name", "purchase_type"):
            if current_page_purchase.get(key):
                compact_page_purchase[key] = current_page_purchase[key]
        if compact_page_purchase:
            compact_state["current_page_purchase"] = compact_page_purchase

    if compact_state:
        payload["conversation_state"] = compact_state

    response_context = build_deterministic_response_context(
        state,
        conversation_state=conversation_state,
        tool_results=tool_results,
        application_service=application_service,
    )
    if response_context is not None:
        payload["response_context"] = response_context

    resolved_purchase = state.get("resolved_context_purchase")
    if isinstance(resolved_purchase, dict):
        payload["resolved_purchase"] = {
            key: resolved_purchase[key]
            for key in ("id", "product_name", "purchase_type", "amount_display", "purchased_at")
            if resolved_purchase.get(key)
        }

    effective_tool_results = tool_results
    if effective_tool_results is None:
        maybe_tool_results = state.get("tool_results")
        effective_tool_results = maybe_tool_results if isinstance(maybe_tool_results, list) else []
    if effective_tool_results:
        payload["available_tool_results"] = summarize_tool_results_for_context(
            effective_tool_results
        )

    blocked_intent = state.get("blocked_intent")
    if blocked_intent:
        payload["blocked_intent"] = blocked_intent

    return payload


def build_deterministic_response_context(
    state: dict[str, Any],
    *,
    conversation_state: dict[str, Any],
    tool_results: list[dict[str, Any]] | None,
    application_service: Any | None,
) -> dict[str, Any] | None:
    """Return deterministic answer context that should outrank raw tool results."""
    active_result_set = conversation_state.get("active_result_set")
    if not isinstance(active_result_set, dict):
        return None

    purchase_ids = [
        purchase_id
        for purchase_id in active_result_set.get("purchase_ids", [])
        if isinstance(purchase_id, str)
    ]
    if not purchase_ids:
        return None

    primary_tool_result = primary_refund_tool_result(tool_results)
    items = hydrate_active_result_set_items(
        purchase_ids,
        tool_results=tool_results,
        application_service=(
            application_service
            if state.get("workflow_classification_reason") == "active_result_set_follow_up"
            else None
        ),
        customer_id=state.get("customer_id"),
    )
    label = active_result_set.get("label")
    response_context = {
        "primary_answer_source": "active_result_set",
        "answer_scope": label,
        "active_result_set": {
            "type": active_result_set.get("type"),
            "label": label,
            "count": len(purchase_ids),
            "items": items,
            "filters": active_result_set.get("filters"),
            "selector": active_result_set.get("selector"),
        },
        "raw_tool_results": summarize_tool_results_for_context(
            tool_results if isinstance(tool_results, list) else []
        ),
    }
    if primary_tool_result is not None:
        response_context["primary_answer_source"] = primary_tool_result["source"]
        response_context[primary_tool_result["source"]] = primary_tool_result["result"]
    return response_context


def primary_refund_tool_result(
    tool_results: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Return refund tool output that should outrank active result-set context."""
    for tool_result in reversed(tool_results or []):
        if not isinstance(tool_result, dict):
            continue
        name = tool_result.get("name")
        if name == "get_refund_eligibility":
            return {
                "source": "refund_eligibility_result",
                "result": tool_result.get("result"),
            }
        if name == "get_refund_policy":
            return {
                "source": "refund_policy_result",
                "result": tool_result.get("result"),
            }
    return None


def hydrate_active_result_set_items(
    purchase_ids: list[str],
    *,
    tool_results: list[dict[str, Any]] | None,
    application_service: Any | None,
    customer_id: str | None,
) -> list[dict[str, Any]]:
    """Hydrate active result-set ids from latest tool rows, falling back to service data."""
    purchases_by_id: dict[str, dict[str, Any]] = {}
    for tool_result in reversed(tool_results or []):
        result = tool_result.get("result") if isinstance(tool_result, dict) else None
        if not isinstance(result, dict):
            continue
        purchases = result.get("purchases")
        if not isinstance(purchases, list):
            continue
        for purchase in purchases:
            if not isinstance(purchase, dict):
                continue
            purchase_id = purchase.get("id")
            if isinstance(purchase_id, str) and purchase_id not in purchases_by_id:
                purchases_by_id[purchase_id] = purchase

    missing_ids = [
        purchase_id for purchase_id in purchase_ids if purchase_id not in purchases_by_id
    ]
    if missing_ids and application_service is not None and isinstance(customer_id, str):
        for purchase in application_service.list_user_purchases(customer_id):
            purchase_id = purchase.get("id")
            if isinstance(purchase_id, str) and purchase_id in missing_ids:
                purchases_by_id[purchase_id] = purchase

    return [
        compact_purchase_for_response_context(purchases_by_id[purchase_id])
        for purchase_id in purchase_ids
        if purchase_id in purchases_by_id
    ]


def compact_purchase_for_response_context(purchase: dict[str, Any]) -> dict[str, Any]:
    """Return customer-safe purchase fields for active result-set answers."""
    amount_cents = purchase.get("amount_cents")
    item = {
        "id": purchase.get("id"),
        "order_number": purchase.get("order_number"),
        "product_name": purchase.get("product_name"),
        "purchase_type": purchase.get("purchase_type"),
        "status": purchase.get("status"),
        "purchased_at": purchase.get("purchased_at"),
    }
    if purchase.get("amount_display"):
        item["amount_display"] = purchase.get("amount_display")
    elif isinstance(amount_cents, int):
        item["amount_display"] = format_cents(amount_cents)
    return {key: value for key, value in item.items() if value is not None}
