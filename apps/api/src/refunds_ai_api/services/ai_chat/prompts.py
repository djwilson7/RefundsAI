"""System prompt and compact model-context prompt construction."""

from __future__ import annotations

import json
from typing import Any

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
    "Do not initiate refund workflow actions. Keep the conversation grounded in the "
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
) -> dict[str, str] | None:
    """Return a small model-visible context message for follow-up grounding."""
    payload = compact_model_context_payload(
        state,
        tool_results=tool_results,
        page_reference=page_reference,
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
            )
            if key in active_refund_context
        }

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
