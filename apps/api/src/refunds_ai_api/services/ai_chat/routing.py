"""Deterministic intent detection and route-selection helpers for AI chat."""

from __future__ import annotations

import re
from typing import Any

from refunds_ai_api.services.refund_policy_catalog import PolicyPurchaseType

from .ranking import has_reference_phrase
from .state import normalize_conversation_state
from .workflow import parse_refund_workflow_mutation_intent

ROUTING_PRECEDENCE = (
    "page_purchase_reference",
    "active_refund_workflow_context",
    "explicit_purchase_reference",
    "selected_single_purchase",
    "scoped_selected_purchase_set",
    "aggregate_list_scope_capture",
    "explicit_policy_intent",
    "explicit_eligibility_intent",
    "supported_mutation_intent",
    "clarification",
)

def should_continue(state: dict[str, Any]) -> str:
    """Stop graph execution when a previous node already produced an answer."""
    return "stop" if state.get("assistant_response") else "continue"


def should_force_purchase_history_tool(message: str) -> bool:
    """Return whether account-domain text should receive purchase-history context."""
    return has_account_fact_intent(message)


def has_account_fact_intent(message: str) -> bool:
    """Return whether text asks for account-backed purchase/order facts."""
    normalized_message = message.casefold()
    account_domain_terms = (
        "account",
        "activity",
        "billing",
        "customer",
        "delivery",
        "digital",
        "history",
        "license",
        "order",
        "orders",
        "purchase",
        "purchases",
        "puchase",
        "puchases",
        "refund",
        "return",
        "shipment",
        "shipping",
        "subscription",
        "tracking",
    )
    fact_terms = (
        "amount",
        "count",
        "date",
        "dates",
        "between",
        "first",
        "how many",
        "last",
        "list",
        "made",
        "month",
        "months",
        "on",
        "over",
        "show",
        "status",
        "statuses",
        "summarize",
        "summary",
        "this",
        "total",
        "type",
        "under",
        "week",
        "weeks",
    )
    return any(term in normalized_message for term in account_domain_terms) and (
        any(term in normalized_message for term in fact_terms)
        or "?" in normalized_message
    )


def has_refund_eligibility_intent(
    message: str,
    *,
    conversation_state: dict[str, Any] | None = None,
) -> bool:
    """Return whether text asks for backend-evaluated refund eligibility."""
    normalized_message = message.casefold()
    normalized_state = normalize_conversation_state(conversation_state)
    if parse_refund_workflow_mutation_intent(message) is not None:
        return False

    eligibility_patterns = (
        r"\bwhich\b.+\b(?:can|could)\s+be\s+refund(?:ed|able)\b",
        r"\bwhich\b.+\b(?:eligible|eligibility)\b",
        r"\bcan\s+i\s+refund\b",
        r"\bcan\s+i\s+get\s+a\s+refund\s+for\b",
        r"\bcould\s+i\s+refund\b",
        r"\bam\s+i\s+able\s+to\s+refund\b",
        r"\bam\s+i\s+able\s+to\s+get\s+a\s+refund\s+for\b",
        r"\bcan\s+i\s+get\s+my\s+money\s+back\b",
        r"\bam\s+i\s+eligible\b",
        r"\bis\s+(?:it|this|that|this\s+item|that\s+item)\s+eligible\b",
        r"\bis\s+(?:it|this|that|this\s+item|that\s+item)\s+refund(?:ed|able)\b",
        r"\bis\b.+\beligible\s+for\s+(?:a\s+)?refund\b",
        r"\bis\b.+\brefund(?:ed|able)\b",
        r"\bare\s+(?:they|these|those|them)\s+refund(?:ed|able)\b",
        r"\bcan\s+(?:they|these|those|them)\s+be\s+refund(?:ed|able)\b",
        r"\bcan\b.+\bbe\s+refund(?:ed|able)\b",
        r"\bcheck\s+if\b.+\brefund(?:ed|able)\b",
        r"\brefund\s+eligibility\b",
    )
    if any(re.search(pattern, normalized_message) for pattern in eligibility_patterns):
        return True

    if _has_policy_to_eligibility_follow_up(normalized_message, normalized_state):
        return True

    has_prior_refund_context = bool(
        normalized_state.get("selected_refund_purchase_ids")
        or normalized_state.get("selected_refund_context")
    )
    return has_prior_refund_context and has_context_reference(normalized_message)


def _has_policy_to_eligibility_follow_up(
    message: str,
    conversation_state: dict[str, Any],
) -> bool:
    active_workflow = conversation_state.get("active_workflow")
    if not isinstance(active_workflow, dict):
        return False
    if active_workflow.get("kind") != "refund_policy":
        return False

    active_result_set = conversation_state.get("active_result_set")
    active_purchase = conversation_state.get("active_purchase")
    has_active_object = (
        isinstance(active_result_set, dict)
        and bool(active_result_set.get("purchase_ids"))
    ) or (
        isinstance(active_purchase, dict)
        and bool(active_purchase.get("purchase_id"))
    ) or bool(conversation_state.get("selected_purchase_id"))
    if not has_active_object:
        return False

    follow_up_patterns = (
        r"^yes[.!]?$",
        r"^yes,?\s+please[.!]?$",
        r"^yes,?\s+(?:please,?\s+)?(?:let'?s|lets)\s+check[.!]?$",
        r"^(?:let'?s|lets)\s+check[.!]?$",
        r"^check\s+(?:it|that|them|those|these)[.!]?$",
    )
    return any(re.search(pattern, message) for pattern in follow_up_patterns)


def has_policy_follow_up_intent(message: str, conversation_state: dict[str, Any]) -> bool:
    """Return whether a short follow-up can reuse prior policy context."""
    if conversation_state.get("selected_policy_scope") is None:
        return False

    normalized_message = message.casefold()
    follow_up_terms = (
        "one",
        "that",
        "that one",
        "those",
        "those purchases",
        "them",
        "it",
        "its",
        "this",
        "this item",
        "this purchase",
        "most recent one",
        "latest one",
        "newest",
        "oldest",
        "earliest",
        "first",
        "what about",
    )
    return any(has_reference_phrase(normalized_message, term) for term in follow_up_terms)


def parse_purchase_type_filter(message: str) -> PolicyPurchaseType | None:
    """Return a purchase type named in account-history text."""
    return parse_policy_purchase_type(message.casefold())


def parse_refund_policy_query(
    message: str,
    *,
    conversation_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Parse refund policy lookup intent into deterministic tool arguments."""
    normalized_message = message.casefold()
    normalized_state = normalize_conversation_state(conversation_state)
    has_refund_domain = "refund" in normalized_message or "return" in normalized_message
    has_release_intent = has_funds_release_intent(normalized_message)
    if not has_refund_domain and not has_release_intent:
        return None
    if has_refund_eligibility_intent(message):
        return None
    if parse_refund_workflow_mutation_intent(message) is not None:
        return None

    purchase_type = parse_policy_purchase_type(normalized_message)
    if purchase_type is None and has_context_reference(normalized_message):
        purchase_type = normalized_state.get("selected_purchase_type")
    if has_administrative_review_intent(normalized_message):
        return {"scope": "administrative_review", "purchase_type": purchase_type}
    if has_release_intent:
        return {"scope": "funds_release", "purchase_type": purchase_type}
    if has_policy_lookup_intent(normalized_message):
        return {
            "scope": "product_type" if purchase_type is not None else "general",
            "purchase_type": purchase_type,
        }
    return None


def has_context_reference(message: str) -> bool:
    """Return whether text points at a prior selected entity or group."""
    reference_terms = (
        "one",
        "that",
        "that one",
        "those",
        "them",
        "it",
        "its",
        "this",
        "this item",
        "this purchase",
        "these",
        "latest",
        "most recent",
        "newest",
        "oldest",
        "earliest",
        "first",
        "most recent one",
        "latest one",
    )
    return any(has_reference_phrase(message, term) for term in reference_terms)


def has_page_context_reference(message: str) -> bool:
    """Return whether text explicitly points at the current page purchase."""
    reference_terms = (
        "this",
        "this item",
        "this product",
        "this purchase",
        "this order",
    )
    return any(has_reference_phrase(message, term) for term in reference_terms)


def parse_blocked_refund_intent(message: str) -> str | None:
    """Return blocked refund mutation intent for backward-compatible callers."""
    return parse_refund_workflow_mutation_intent(message)


def has_policy_lookup_intent(message: str) -> bool:
    """Return whether text asks for refund policy information."""
    policy_terms = (
        "guideline",
        "guidelines",
        "policy",
        "policies",
        "requirement",
        "requirements",
        "rule",
        "rules",
        "window",
    )
    return any(term in message for term in policy_terms)


def has_funds_release_intent(message: str) -> bool:
    """Return whether text asks about refund processing or fund release timing."""
    release_terms = (
        "3-10",
        "business day",
        "business days",
        "complete",
        "completed",
        "funds",
        "how long",
        "money back",
        "payment method",
        "processed",
        "processing",
        "released",
        "takes",
        "timeline",
    )
    return any(term in message for term in release_terms)


def has_administrative_review_intent(message: str) -> bool:
    """Return whether text asks about administrative review policy."""
    review_terms = (
        "admin review",
        "administrative review",
        "additional review",
        "fraud",
        "investigation",
        "manual review",
        "review",
        "suspected abuse",
    )
    return any(term in message for term in review_terms)


def parse_policy_purchase_type(message: str) -> PolicyPurchaseType | None:
    """Return a product type mentioned in policy lookup text."""
    if "digital" in message or "license" in message or "code" in message:
        return "digital"
    if "physical" in message or "shipment" in message or "shipping" in message:
        return "physical"
    if "subscription" in message or "billing period" in message or "auto-renew" in message:
        return "subscription"
    return None
