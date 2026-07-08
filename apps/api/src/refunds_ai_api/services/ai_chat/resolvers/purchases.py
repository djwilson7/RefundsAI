"""Purchase-row lookup and scoped purchase reference resolution."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from refunds_ai_api.services.ai_chat.ranking import (
    has_reference_phrase,
    has_selected_set_reference,
    has_selected_single_purchase_reference,
    list_purchases_by_ids,
    parse_purchase_ranking_reference,
    select_ranked_purchase,
    sort_purchases_by_recency,
)
from refunds_ai_api.services.application import ApplicationService

from .products import explicit_purchase_type_word, normalize_match_text


@dataclass(frozen=True)
class PurchaseMatchResult:
    """A purchase match plus audit-safe candidate diagnostics."""

    purchase: dict[str, Any] | None
    confidence: float | None
    candidates: list[dict[str, Any]]
    reason: str


def resolve_purchase_reference(
    application_service: ApplicationService | None,
    customer_id: str | None,
    product_reference: str,
) -> dict[str, Any] | None:
    """Resolve a named product, SKU, or order number against purchase history."""
    if application_service is None or customer_id is None:
        return None

    purchases = application_service.list_user_purchases(customer_id)
    return match_purchase_reference(product_reference, purchases)

def resolve_purchase_reference_for_state(
    application_service: ApplicationService | None,
    customer_id: str | None,
    product_reference: str,
    conversation_state: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve a product reference while respecting explicit type words in scope."""
    if application_service is None or customer_id is None:
        return None, None

    requested_type = explicit_purchase_type_word(product_reference)
    if requested_type is None:
        return (
            resolve_purchase_reference(
                application_service,
                customer_id,
                product_reference,
            ),
            None,
        )

    active_result_set = conversation_state.get("active_result_set")
    active_purchase_ids = (
        active_result_set.get("purchase_ids")
        if isinstance(active_result_set, dict)
        else None
    )
    if active_purchase_ids:
        scoped_purchases = [
            purchase
            for purchase in list_purchases_by_ids(
                application_service,
                customer_id,
                active_purchase_ids,
            )
            if purchase.get("purchase_type") == requested_type
        ]
        scoped_match = match_purchase_reference(product_reference, scoped_purchases)
        if scoped_match is not None:
            return scoped_match, None

    type_matches = [
        purchase
        for purchase in application_service.list_user_purchases(customer_id)
        if purchase.get("purchase_type") == requested_type
    ]
    type_match = match_purchase_reference(product_reference, type_matches)
    if type_match is not None:
        return type_match, None

    return None, product_reference

def match_purchase_reference(
    product_reference: str,
    purchases: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Match product references by exact, normalized, partial, fuzzy, SKU, or order."""
    return match_purchase_reference_with_metadata(product_reference, purchases).purchase


def match_purchase_reference_with_metadata(
    product_reference: str,
    purchases: list[dict[str, Any]],
) -> PurchaseMatchResult:
    """Match a reference and retain confidence/candidate data for audit traces."""
    reference = product_reference.strip()
    normalized_reference = normalize_match_text(reference)
    if not normalized_reference:
        return PurchaseMatchResult(None, None, [], "empty_reference")

    for purchase in purchases:
        if str(purchase.get("product_name", "")).casefold() == reference.casefold():
            resolved = build_resolved_purchase(purchase)
            return PurchaseMatchResult(
                resolved,
                1.0,
                [_match_candidate(resolved, 1.0)],
                "exact_product_name",
            )

    for purchase in purchases:
        searchable_values = purchase_search_values(purchase)
        if normalized_reference in searchable_values:
            resolved = build_resolved_purchase(purchase)
            return PurchaseMatchResult(
                resolved,
                1.0,
                [_match_candidate(resolved, 1.0)],
                "normalized_identifier",
            )

    partial_matches = [
        purchase
        for purchase in purchases
        if any(
            normalized_reference in value or value in normalized_reference
            for value in purchase_search_values(purchase)
            if value
        )
    ]
    if len(partial_matches) == 1:
        resolved = build_resolved_purchase(partial_matches[0])
        return PurchaseMatchResult(
            resolved,
            0.95,
            [_match_candidate(resolved, 0.95)],
            "unique_partial_match",
        )
    if len(partial_matches) > 1:
        return PurchaseMatchResult(
            None,
            None,
            [
                _match_candidate(build_resolved_purchase(purchase), 0.95)
                for purchase in partial_matches
            ],
            "ambiguous_partial_match",
        )

    fuzzy_matches = sorted(
        (
            (
                max(
                    SequenceMatcher(None, normalized_reference, value).ratio()
                    for value in purchase_search_values(purchase)
                    if value
                ),
                purchase,
            )
            for purchase in purchases
            if purchase_search_values(purchase)
        ),
        reverse=True,
        key=lambda match: match[0],
    )
    candidates = [
        _match_candidate(build_resolved_purchase(purchase), round(score, 4))
        for score, purchase in fuzzy_matches[:5]
    ]
    if fuzzy_matches and fuzzy_matches[0][0] >= 0.78:
        if len(fuzzy_matches) > 1 and fuzzy_matches[1][0] >= 0.74:
            return PurchaseMatchResult(None, None, candidates, "ambiguous_fuzzy_match")
        return PurchaseMatchResult(
            build_resolved_purchase(fuzzy_matches[0][1]),
            round(fuzzy_matches[0][0], 4),
            candidates,
            "unique_high_confidence_fuzzy_match",
        )

    return PurchaseMatchResult(None, None, candidates, "no_strong_match")


def _match_candidate(
    purchase: dict[str, Any],
    confidence: float,
) -> dict[str, Any]:
    return {
        "purchase_id": purchase["id"],
        "product_name": purchase["product_name"],
        "confidence": confidence,
    }

def purchase_search_values(purchase: dict[str, Any]) -> list[str]:
    """Return normalized purchase identifiers for entity resolution."""
    return [
        normalize_match_text(str(value))
        for value in (
            purchase.get("id"),
            purchase.get("product_name"),
            purchase.get("sku"),
            purchase.get("order_number"),
        )
        if value
    ]

def resolve_purchase_mention(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
) -> dict[str, Any] | None:
    """Resolve exact, partial, or fuzzy product mentions to a purchase row."""
    if application_service is None or customer_id is None:
        return None

    normalized_message = normalize_match_text(message)
    if not normalized_message:
        return None

    return match_purchase_reference(
        normalized_message,
        application_service.list_user_purchases(customer_id),
    )

def resolve_selected_single_purchase(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
    conversation_state: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve vague singular follow-ups to the selected purchase before set scope."""
    if not has_selected_single_purchase_reference(message):
        return None

    selected_purchase_id = conversation_state.get("selected_purchase_id")
    if not isinstance(selected_purchase_id, str):
        return None

    return resolve_purchase_by_id(application_service, customer_id, selected_purchase_id)

def resolve_purchase_from_selected_set(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
    conversation_state: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve pronoun and ranking follow-ups inside the selected purchase set."""
    if not has_selected_set_reference(message):
        return None

    selected_purchase_ids = conversation_state.get("selected_purchase_ids")
    if not selected_purchase_ids:
        return None

    purchases = list_purchases_by_ids(application_service, customer_id, selected_purchase_ids)
    if not purchases:
        return None

    if len(purchases) == 1:
        return build_resolved_purchase(purchases[0])

    normalized_message = message.casefold()
    ranking_reference = parse_purchase_ranking_reference(normalized_message)
    ranked_purchase = select_ranked_purchase(purchases, ranking_reference)
    if ranked_purchase is not None:
        return build_resolved_purchase(ranked_purchase)
    if has_reference_phrase(normalized_message, "one"):
        return build_resolved_purchase(sort_purchases_by_recency(purchases)[0])

    selected_purchase_type = conversation_state.get("selected_purchase_type")
    if selected_purchase_type in {"digital", "physical", "subscription"}:
        matching_type_purchases = [
            purchase
            for purchase in purchases
            if purchase.get("purchase_type") == selected_purchase_type
        ]
        if matching_type_purchases:
            return build_resolved_purchase(sort_purchases_by_recency(matching_type_purchases)[0])

    return None

def resolve_global_ranked_purchase(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
) -> dict[str, Any] | None:
    """Resolve global ranked references only when no selected set exists."""
    ranking_reference = parse_purchase_ranking_reference(message.casefold())
    if ranking_reference is None:
        return None
    if application_service is None or customer_id is None:
        return None

    purchases = application_service.list_user_purchases(customer_id)
    if not purchases:
        return None

    ranked_purchase = select_ranked_purchase(purchases, ranking_reference)
    return build_resolved_purchase(ranked_purchase) if ranked_purchase is not None else None

def resolve_purchase_by_id(
    application_service: ApplicationService | None,
    customer_id: str | None,
    purchase_id: str | None,
) -> dict[str, Any] | None:
    """Resolve one current-page purchase id against the active customer's rows."""
    if application_service is None or customer_id is None or purchase_id is None:
        return None

    for purchase in application_service.list_user_purchases(customer_id):
        if str(purchase.get("id")) == purchase_id:
            return build_resolved_purchase(purchase)

    return None

def build_resolved_purchase(purchase: dict[str, Any]) -> dict[str, Any]:
    """Return the small resolved purchase shape stored in conversation state."""
    return {
        "id": str(purchase["id"]),
        "product_name": str(purchase["product_name"]),
        "sku": str(purchase.get("sku", "")),
        "order_number": str(purchase.get("order_number", "")),
        "purchase_type": purchase["purchase_type"],
    }
