"""Ranking and reference-term helpers for purchase follow-ups."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from refunds_ai_api.services.application import ApplicationService


def has_selected_single_purchase_reference(message: str) -> bool:
    """Return whether text points at the current selected purchase, not a set."""
    normalized_message = message.casefold()
    if has_purchase_ranking_reference(normalized_message):
        return False
    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("those", "them", "these", "those purchases")
    ):
        return False
    return any(
        has_reference_phrase(normalized_message, term)
        for term in (
            "it",
            "its",
            "that",
            "that item",
            "that purchase",
            "that product",
            "this item",
            "this purchase",
            "this product",
        )
    )


def select_ranked_purchase(
    purchases: list[dict[str, Any]],
    ranking_reference: str | None,
) -> dict[str, Any] | None:
    """Select one purchase by a parsed ranking reference."""
    if not purchases or ranking_reference is None:
        return None
    if ranking_reference == "newest":
        return sort_purchases_by_recency(purchases)[0]
    if ranking_reference == "oldest":
        return sort_purchases_by_recency(purchases)[-1]
    if ranking_reference == "cheapest":
        return min(purchases, key=lambda purchase: int(purchase.get("amount_cents") or 0))
    if ranking_reference == "most_expensive":
        return max(purchases, key=lambda purchase: int(purchase.get("amount_cents") or 0))
    return None


def list_purchases_by_ids(
    application_service: ApplicationService | None,
    customer_id: str | None,
    purchase_ids: list[str],
) -> list[dict[str, Any]]:
    """Return active-customer purchase rows matching the provided ids."""
    if application_service is None or customer_id is None:
        return []

    selected_ids = set(purchase_ids)
    return [
        purchase
        for purchase in application_service.list_user_purchases(customer_id)
        if str(purchase.get("id")) in selected_ids
    ]


def sort_purchases_by_recency(purchases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort purchase rows from newest to oldest."""
    return sorted(
        purchases,
        key=lambda purchase: purchase.get("purchased_at") or datetime.min,
        reverse=True,
    )


def has_selected_set_reference(message: str) -> bool:
    """Return whether text refers back to an item in the selected purchase set."""
    normalized_message = message.casefold()
    reference_terms = (
        "one",
        "that one",
        "those",
        "last one",
        "last purchase",
        "first one",
        "first purchase",
        "latest",
        "most recent",
        "newest",
        "oldest",
        "earliest",
        "first",
        "cheapest",
        "least expensive",
        "lowest price",
        "most expensive",
        "highest price",
        "most recent one",
        "latest one",
    )
    return any(has_reference_phrase(normalized_message, term) for term in reference_terms)


def has_recent_purchase_reference(message: str) -> bool:
    """Return whether text asks for the latest purchase in the active scope."""
    return parse_temporal_purchase_reference(message) == "newest"


def has_temporal_purchase_reference(message: str) -> bool:
    """Return whether text asks for a temporal purchase in the active scope."""
    return parse_temporal_purchase_reference(message) is not None


def has_purchase_ranking_reference(message: str) -> bool:
    """Return whether text asks for a ranked purchase in the active scope."""
    return parse_purchase_ranking_reference(message) is not None


def parse_purchase_ranking_reference(message: str) -> str | None:
    """Return a supported purchase ranking reference from user text."""
    normalized_message = message.casefold()
    temporal_reference = parse_temporal_purchase_reference(normalized_message)
    if temporal_reference is not None:
        return temporal_reference
    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("cheapest", "least expensive", "lowest price", "lowest priced")
    ):
        return "cheapest"
    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("most expensive", "highest price", "highest priced")
    ):
        return "most_expensive"
    return None


def parse_temporal_purchase_reference(message: str) -> str | None:
    """Return newest/oldest when text asks for a temporal purchase reference."""
    normalized_message = message.casefold()
    if any(
        has_reference_phrase(normalized_message, term)
        for term in (
            "latest",
            "latest one",
            "most recent",
            "most recent one",
            "newest",
            "newest one",
            "last one",
            "last purchase",
        )
    ):
        return "newest"

    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("oldest", "oldest one", "earliest", "earliest one")
    ):
        return "oldest"
    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("first one", "first purchase")
    ) or (
        has_reference_phrase(normalized_message, "first")
        and not any(
            has_reference_phrase(normalized_message, term)
            for term in ("first week", "first month", "first quarter")
        )
    ):
        return "oldest"

    return None


def has_reference_phrase(message: str, phrase: str) -> bool:
    """Match context-reference phrases without treating product substrings as pronouns."""
    pattern = r"(?<![a-z0-9])" + r"\s+".join(
        re.escape(part) for part in phrase.casefold().split()
    ) + r"(?![a-z0-9])"
    return re.search(pattern, message.casefold()) is not None
