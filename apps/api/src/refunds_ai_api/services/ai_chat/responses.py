"""Customer-facing response guards and deterministic response builders."""

from __future__ import annotations

import re

from .models import ChatGraphState
from .ranking import parse_purchase_ranking_reference
from .state import normalize_conversation_state

CHAT_UNAVAILABLE_RESPONSE = (
    "AI chat is temporarily unavailable. Please try again in a moment."
)
ACCOUNT_DATA_REQUIRED_RESPONSE = (
    "I need account data before I can answer that. Please ask about your purchases, "
    "orders, account activity, or refund flow."
)
CUSTOMER_CONTEXT_REQUIRED_RESPONSE = (
    "I need an active customer session before I can inspect purchase history. "
    "Please load a mock customer, then ask again."
)
FORBIDDEN_CUSTOMER_RESPONSE_TERMS = (
    "workflow",
    "mutation",
    "backend",
    "backend step",
    "persisted state",
    "orchestration",
    "issue_funds",
    "invalidate_code",
    "cancel_subscription",
    "required_action",
    "required action",
    "selected context",
    "selected set",
    "resolver",
    "tool",
    "state",
    "purchase_ids",
    "node",
    "graph",
)
SUPPORTED_ACCOUNT_TOPICS = (
    "account, purchases, orders, refund policies, refund-related questions, "
    "and account activity"
)

def sanitize_customer_response(response: str, state: ChatGraphState) -> str:
    """Replace customer-facing responses that expose backend routing terms."""
    if not contains_forbidden_customer_response_term(response):
        return response

    safe_response = build_customer_safe_resolved_purchase_response(state)
    return safe_response or (
        "I can help with account history, purchases, orders, refund policy, and "
        "refund eligibility."
    )


def contains_forbidden_customer_response_term(response: str) -> bool:
    """Return whether the assistant text exposes backend implementation terms."""
    normalized_response = response.casefold()
    for term in FORBIDDEN_CUSTOMER_RESPONSE_TERMS:
        pattern = r"(?<![a-z0-9_])" + re.escape(term.casefold()) + r"(?![a-z0-9_])"
        if re.search(pattern, normalized_response):
            return True
    return False


def build_customer_safe_resolved_purchase_response(
    state: ChatGraphState,
) -> str | None:
    """Return deterministic prose for resolved purchase facts when sanitizing."""
    resolved_purchase = state.get("resolved_context_purchase")
    if not isinstance(resolved_purchase, dict):
        return None

    product_name = resolved_purchase.get("product_name")
    if not isinstance(product_name, str) or not product_name:
        return None

    ranking_reference = parse_purchase_ranking_reference(state.get("message", ""))
    conversation_state = normalize_conversation_state(state.get("conversation_state"))
    scope_label = conversation_state.get("selected_scope_label") or "your purchases"
    if ranking_reference is not None:
        ranking_label = {
            "newest": "latest",
            "oldest": "oldest",
            "cheapest": "cheapest",
            "most_expensive": "most expensive",
        }[ranking_reference]
        amount_display = resolved_purchase.get("amount_display")
        amount_suffix = (
            f" for {amount_display}" if isinstance(amount_display, str) else ""
        )
        return (
            f"The {ranking_label} purchase from {scope_label} is "
            f"{product_name}{amount_suffix}."
        )

    return f"The purchase I found is {product_name}."
