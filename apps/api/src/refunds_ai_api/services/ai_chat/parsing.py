"""Low-level parsing helpers for AI chat routing and tool arguments."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from refunds_ai_api.services.money import dollars_to_cents

from .routing import has_account_fact_intent


def has_invalid_pseudo_tool_output(content: str | None) -> bool:
    """Detect malformed textual tool-call attempts returned as model content."""
    if not content:
        return False

    normalized_content = content.casefold()
    return bool(
        re.search(r"\bto\s*=\s*get_[a-z0-9_]+", normalized_content)
        or re.search(r"\bget_[a-z0-9_]+\s*\{", normalized_content)
    )


def parse_amount_threshold_query(message: str) -> dict[str, Any] | None:
    """Parse narrow amount-threshold purchase questions into deterministic tool args."""
    normalized_message = message.casefold()
    if not has_account_fact_intent(normalized_message):
        return None

    amount_match = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", normalized_message)
    if amount_match is None:
        amount_match = re.search(
            r"\b(\d+(?:\.\d{1,2})?)\s*(?:dollar|dollars|usd)\b",
            normalized_message,
        )

    if amount_match is None:
        return None

    comparison = parse_threshold_comparison(normalized_message)
    if comparison is None:
        return None

    amount = Decimal(amount_match.group(1))
    return {
        "threshold_cents": dollars_to_cents(amount),
        "comparison": comparison,
    }


def parse_threshold_comparison(message: str) -> str | None:
    """Return the comparison operator implied by narrow threshold phrasing."""
    comparison_patterns = (
        ("gte", ("at least", "greater than or equal", "more than or equal")),
        ("lte", ("at most", "less than or equal", "under or equal", "up to")),
        ("gt", ("over", "more than", "greater than", "above")),
        ("lt", ("under", "less than", "below")),
    )
    for comparison, patterns in comparison_patterns:
        if any(pattern in message for pattern in patterns):
            return comparison
    return None


def parse_model_threshold_arguments(arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Validate model-provided threshold arguments before tool execution."""
    comparison = arguments.get("comparison")
    threshold_cents = arguments.get("threshold_cents")
    if comparison not in {"gt", "gte", "lt", "lte"}:
        return None
    if not isinstance(threshold_cents, int) or threshold_cents < 0:
        return None
    return {"comparison": comparison, "threshold_cents": threshold_cents}


def parse_model_refund_policy_arguments(arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Validate model-provided refund-policy arguments before tool execution."""
    scope = arguments.get("scope")
    purchase_type = arguments.get("purchase_type")
    if scope not in {"general", "product_type", "funds_release", "administrative_review"}:
        return None
    if purchase_type is not None and purchase_type not in {"digital", "physical", "subscription"}:
        return None
    return {"scope": scope, "purchase_type": purchase_type}


def parse_model_refund_eligibility_arguments(arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Validate model-provided refund-eligibility arguments before tool execution."""
    purchase_ids = arguments.get("purchase_ids")
    context = arguments.get("context", "model_requested")
    if not isinstance(purchase_ids, list) or not purchase_ids:
        return None
    if not all(isinstance(purchase_id, str) for purchase_id in purchase_ids):
        return None
    if not isinstance(context, str) or not context:
        context = "model_requested"
    return {"purchase_ids": purchase_ids, "context": context}


def amount_matches_threshold(amount_cents: int, threshold_cents: int, comparison: str) -> bool:
    """Apply one supported threshold comparison."""
    if comparison == "gt":
        return amount_cents > threshold_cents
    if comparison == "gte":
        return amount_cents >= threshold_cents
    if comparison == "lt":
        return amount_cents < threshold_cents
    if comparison == "lte":
        return amount_cents <= threshold_cents
    raise ValueError(f"Unsupported threshold comparison: {comparison}.")


def parse_tool_arguments(arguments: str | None) -> dict[str, Any]:
    """Parse model tool-call arguments defensively."""
    if not arguments:
        return {}

    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}
