"""Purchase, product, page, and pronoun resolution for AI chat."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from refunds_ai_api.services.application import ApplicationService
from refunds_ai_api.services.money import format_cents

from .dates import parse_date_range_query
from .models import EligibilityResolution
from .ranking import (
    has_purchase_ranking_reference,
    has_reference_phrase,
    has_selected_set_reference,
    has_selected_single_purchase_reference,
    list_purchases_by_ids,
    parse_purchase_ranking_reference,
    select_ranked_purchase,
    sort_purchases_by_recency,
)
from .responses import SUPPORTED_ACCOUNT_TOPICS
from .routing import (
    has_context_reference,
    has_page_context_reference,
    has_policy_follow_up_intent,
    has_refund_eligibility_intent,
    parse_policy_purchase_type,
    parse_purchase_type_filter,
    parse_refund_policy_query,
)
from .scopes import selected_purchase_ids_for_refund_context
from .state import normalize_conversation_state, normalize_page_context
from .tools import get_purchase_history_by_date_range


def resolve_page_reference(
    application_service: ApplicationService | None,
    customer_id: str | None,
    page_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve the current page to a small backend-grounded reference."""
    normalized_context = normalize_page_context(page_context)
    if normalized_context["surface"] != "purchase_detail":
        return {"surface": "purchase_history", "purchase": None}

    purchase = resolve_purchase_by_id(
        application_service,
        customer_id,
        normalized_context["purchase_id"],
    )
    if purchase is None:
        return {"surface": "purchase_detail", "purchase": None}

    return {"surface": "purchase_detail", "purchase": purchase}


def resolve_refund_policy_query(
    message: str,
    *,
    conversation_state: dict[str, Any] | None,
    page_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve a policy lookup from explicit text plus compact conversation state."""
    policy_query, _resolved_purchase, _unresolved_product_reference = (
        resolve_refund_policy_query_with_purchase(
            message,
            conversation_state=conversation_state,
            page_context=page_context,
            application_service=None,
            customer_id=None,
        )
    )
    return policy_query


def resolve_refund_policy_query_with_purchase(
    message: str,
    *,
    conversation_state: dict[str, Any] | None,
    page_context: dict[str, Any] | None,
    application_service: ApplicationService | None,
    customer_id: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    """Resolve policy lookup arguments and an optional product match."""
    normalized_state = normalize_conversation_state(conversation_state)
    product_reference = extract_product_reference(message)
    policy_query = parse_refund_policy_query(
        message,
        conversation_state=normalized_state,
    )
    normalized_message = message.casefold()
    page_purchase = None
    if has_page_context_reference(normalized_message) and product_reference is None:
        page_purchase = resolve_purchase_by_id(
            application_service,
            customer_id,
            normalize_page_context(page_context).get("purchase_id"),
        )
    selected_single_purchase = resolve_selected_single_purchase(
        application_service,
        customer_id,
        message,
        normalized_state,
    )
    selected_set_purchase = resolve_purchase_from_selected_set(
        application_service,
        customer_id,
        message,
        normalized_state,
    )

    if policy_query is not None:
        resolved_purchase = None
        if product_reference is not None:
            resolved_purchase = resolve_purchase_reference(
                application_service,
                customer_id,
                product_reference,
            )
            if resolved_purchase is None:
                return None, None, product_reference
        else:
            resolved_purchase = (
                page_purchase or selected_single_purchase or selected_set_purchase
            )
            if resolved_purchase is None and policy_query.get("purchase_type") is None:
                resolved_purchase = resolve_purchase_mention(
                    application_service,
                    customer_id,
                    message,
                ) or resolve_global_ranked_purchase(
                    application_service,
                    customer_id,
                    message,
                )
        if resolved_purchase is not None:
            policy_query = {
                **policy_query,
                "scope": "product_type",
                "purchase_type": resolved_purchase["purchase_type"],
            }
        return policy_query, resolved_purchase, None

    if not has_policy_follow_up_intent(message, normalized_state):
        return None, None, None

    resolved_purchase = None
    if product_reference is not None:
        resolved_purchase = resolve_purchase_reference(
            application_service,
            customer_id,
            product_reference,
        )
        if resolved_purchase is None:
            return None, None, product_reference
    if resolved_purchase is None:
        resolved_purchase = page_purchase or selected_single_purchase or selected_set_purchase
    if resolved_purchase is None:
        resolved_purchase = resolve_purchase_mention(
            application_service,
            customer_id,
            message,
        ) or resolve_global_ranked_purchase(
            application_service,
            customer_id,
            message,
        )

    if resolved_purchase is not None:
        return (
            {
                "scope": normalized_state.get("selected_policy_scope") or "product_type",
                "purchase_type": resolved_purchase["purchase_type"],
            },
            resolved_purchase,
            None,
        )

    selected_purchase_type = normalized_state.get("selected_purchase_type")
    if selected_purchase_type is None:
        return None, None, None

    return (
        {
            "scope": normalized_state.get("selected_policy_scope") or "product_type",
            "purchase_type": selected_purchase_type,
        },
        None,
        None,
    )


def resolve_refund_eligibility_query(
    message: str,
    *,
    conversation_state: dict[str, Any] | None,
    page_context: dict[str, Any] | None,
    application_service: ApplicationService | None,
    customer_id: str | None,
) -> EligibilityResolution | None:
    """Resolve read-only refund eligibility intent to active-customer purchase ids."""
    normalized_state = normalize_conversation_state(conversation_state)
    if not has_refund_eligibility_intent(
        message,
        conversation_state=normalized_state,
    ):
        return None
    if application_service is None or customer_id is None:
        return EligibilityResolution([], "customer_context_required")

    product_reference = extract_product_reference(message)
    if product_reference is not None:
        resolved_purchase = resolve_purchase_reference(
            application_service,
            customer_id,
            product_reference,
        )
        if resolved_purchase is None:
            return EligibilityResolution(
                [],
                "product",
                unresolved_product_reference=product_reference,
            )
        return EligibilityResolution(
            [resolved_purchase["id"]],
            "product",
            resolved_purchase=resolved_purchase,
        )

    normalized_message = message.casefold()
    if has_context_reference(normalized_message):
        page_purchase = resolve_purchase_by_id(
            application_service,
            customer_id,
            normalize_page_context(page_context).get("purchase_id"),
        )
        if page_purchase is not None and has_page_context_reference(normalized_message):
            return EligibilityResolution(
                [page_purchase["id"]],
                "current_page",
                resolved_purchase=page_purchase,
            )

        selected_purchase = resolve_selected_single_purchase(
            application_service,
            customer_id,
            message,
            normalized_state,
        )
        if selected_purchase is not None:
            return EligibilityResolution(
                [selected_purchase["id"]],
                "selected_purchase",
                resolved_purchase=selected_purchase,
            )

        selected_ids = selected_purchase_ids_for_refund_context(
            application_service,
            customer_id,
            message,
            normalized_state,
        )
        if selected_ids:
            resolved_purchase = (
                resolve_purchase_by_id(application_service, customer_id, selected_ids[0])
                if len(selected_ids) == 1
                else None
            )
            return EligibilityResolution(
                selected_ids,
                "selected_set",
                resolved_purchase=resolved_purchase,
            )

    purchase_type = parse_purchase_type_filter(message)
    if purchase_type is not None:
        purchase_ids = [
            str(purchase["id"])
            for purchase in application_service.list_user_purchases(customer_id)
            if purchase.get("purchase_type") == purchase_type
        ]
        return EligibilityResolution(purchase_ids, purchase_type)

    date_range_query = parse_date_range_query(message)
    if date_range_query is not None:
        date_range_result = get_purchase_history_by_date_range(
            application_service,
            customer_id,
            start_date=date_range_query["start_date"],
            end_date=date_range_query["end_date"],
            timezone_name=date_range_query["timezone"],
            label=date_range_query.get("label"),
        )
        return EligibilityResolution(
            [
                str(purchase["id"])
                for purchase in date_range_result.get("purchases", [])
                if isinstance(purchase.get("id"), str)
            ],
            "date_range",
        )

    purchase_mention = resolve_purchase_mention(application_service, customer_id, message)
    if purchase_mention is not None:
        return EligibilityResolution(
            [purchase_mention["id"]],
            "product",
            resolved_purchase=purchase_mention,
        )

    purchase_ids = [
        str(purchase["id"])
        for purchase in application_service.list_user_purchases(customer_id)
        if isinstance(purchase.get("id"), str)
    ]
    return EligibilityResolution(purchase_ids, "all_purchases")


def extract_product_reference(message: str) -> str | None:
    """Extract a likely named product/SKU/order reference from supported follow-up text."""
    stripped_message = message.strip().strip("?.! ")
    normalized_message = stripped_message.casefold()
    if not stripped_message or has_purchase_ranking_reference(normalized_message):
        return None

    patterns = (
        r"\bcan\s+i\s+refund\s+(?:my\s+|the\s+)?(.+)$",
        r"\bcan\s+i\s+get\s+my\s+money\s+back\s+for\s+(?:my\s+|the\s+)?(.+)$",
        r"\bcan\s+(?:my\s+|the\s+)?(.+?)\s+be\s+refunded\b",
        r"\bwhat\s+about\s+(?:the\s+)?(.+)$",
        r"\brefund\s+policy\s+for\s+(?:the\s+)?(.+)$",
        r"\bpolicy\s+for\s+(?:the\s+)?(.+)$",
        r"\brules?\s+for\s+(?:the\s+)?(.+)$",
        r"\brequirements?\s+for\s+(?:the\s+)?(.+)$",
        r"\bfor\s+(?:the\s+)?(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, stripped_message, flags=re.IGNORECASE)
        if match is None:
            continue

        candidate = clean_product_reference(match.group(1))
        if is_named_product_reference(candidate):
            return candidate

    return None


def clean_product_reference(value: str) -> str:
    """Remove common trailing policy words around an extracted product reference."""
    candidate = value.strip().strip("?.! ")
    candidate = re.sub(
        r"\b(refund|return)\s+(policy|rules?|requirements?|window)\b",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    return " ".join(candidate.split())


def is_named_product_reference(candidate: str) -> bool:
    """Return whether a candidate looks like a concrete product/order reference."""
    if not candidate:
        return False

    normalized_candidate = normalize_match_text(candidate)
    if normalized_candidate in {
        "that",
        "that one",
        "that product",
        "that type of product",
        "those",
        "those products",
        "those purchases",
        "those types of products",
        "them",
        "these",
        "these products",
        "these purchases",
        "these types of products",
        "they",
        "this",
        "this item",
        "this product",
        "this purchase",
        "this order",
        "this type of product",
        "it",
        "its",
        "one",
        "last one",
        "last purchase",
        "first one",
        "first purchase",
        "latest one",
        "most recent one",
        "latest",
        "most recent",
        "newest",
        "newest one",
        "oldest",
        "oldest one",
        "earliest",
        "earliest one",
        "first",
        "cheapest",
        "least expensive",
        "lowest price",
        "lowest priced",
        "most expensive",
        "highest price",
        "highest priced",
    }:
        return False
    if is_demonstrative_product_reference(normalized_candidate):
        return False
    if is_generic_purchase_type_reference(normalized_candidate):
        return False

    return True


def is_demonstrative_product_reference(normalized_candidate: str) -> bool:
    """Return whether text is only a demonstrative product/group reference."""
    return bool(
        re.fullmatch(
            r"(?:this|that|these|those|them|they)(?:\s+types?\s+of)?"
            r"(?:\s+(?:product|products|purchase|purchases))?",
            normalized_candidate,
        )
    )


def is_generic_purchase_type_reference(normalized_candidate: str) -> bool:
    """Return whether text is a product-type phrase rather than a named product."""
    if parse_policy_purchase_type(normalized_candidate) is None:
        return False

    terms = set(normalized_candidate.split())
    generic_terms = {
        "a",
        "an",
        "my",
        "our",
        "the",
        "purchase",
        "purchases",
        "product",
        "products",
        "return",
        "returns",
        "digital",
        "physical",
        "subscription",
        "subscriptions",
    }
    return terms.issubset(generic_terms)


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


def match_purchase_reference(
    product_reference: str,
    purchases: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Match product references by exact, normalized, partial, fuzzy, SKU, or order."""
    reference = product_reference.strip()
    normalized_reference = normalize_match_text(reference)
    if not normalized_reference:
        return None

    for purchase in purchases:
        if str(purchase.get("product_name", "")).casefold() == reference.casefold():
            return build_resolved_purchase(purchase)

    for purchase in purchases:
        searchable_values = purchase_search_values(purchase)
        if normalized_reference in searchable_values:
            return build_resolved_purchase(purchase)

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
        return build_resolved_purchase(partial_matches[0])
    if len(partial_matches) > 1:
        return None

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
    if fuzzy_matches and fuzzy_matches[0][0] >= 0.78:
        if len(fuzzy_matches) > 1 and fuzzy_matches[1][0] >= 0.74:
            return None
        return build_resolved_purchase(fuzzy_matches[0][1])

    return None


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


def build_unresolved_product_response(product_reference: str) -> str:
    """Return a grounded clarification when product entity resolution fails."""
    return (
        f"I couldn't find a purchase matching '{product_reference}' in your account history. "
        "Could you confirm the product name, order number, SKU, or purchase date? "
        f"I can also help with {SUPPORTED_ACCOUNT_TOPICS}."
    )


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


def resolve_ranked_purchase_context(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
    conversation_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve non-policy ranked purchase questions from backend purchase rows."""
    normalized_state = normalize_conversation_state(conversation_state)
    ranking_reference = parse_purchase_ranking_reference(message)
    if ranking_reference is None:
        return None

    selected_purchase_ids = normalized_state.get("selected_purchase_ids")
    purchases = (
        list_purchases_by_ids(application_service, customer_id, selected_purchase_ids)
        if selected_purchase_ids
        else (
            application_service.list_user_purchases(customer_id)
            if application_service is not None and customer_id is not None
            else []
        )
    )
    ranked_purchase = select_ranked_purchase(purchases, ranking_reference)
    return (
        build_resolved_purchase_fact(ranked_purchase)
        if ranked_purchase is not None
        else None
    )


def resolve_purchase_fact_context(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
    conversation_state: dict[str, Any] | None,
    page_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve deterministic purchase facts before honoring model tool choices."""
    normalized_message = message.casefold()
    normalized_state = normalize_conversation_state(conversation_state)

    if has_page_context_reference(normalized_message):
        page_purchase = resolve_purchase_fact_by_id(
            application_service,
            customer_id,
            normalize_page_context(page_context).get("purchase_id"),
        )
        if page_purchase is not None:
            return page_purchase

    product_reference = extract_product_reference(message)
    if product_reference is not None:
        explicit_purchase = resolve_purchase_reference_fact(
            application_service,
            customer_id,
            product_reference,
        )
        if explicit_purchase is not None:
            return explicit_purchase

    if has_selected_single_purchase_reference(message):
        selected_purchase = resolve_purchase_fact_by_id(
            application_service,
            customer_id,
            normalized_state.get("selected_purchase_id"),
        )
        if selected_purchase is not None:
            return selected_purchase

    return resolve_ranked_purchase_context(
        application_service,
        customer_id,
        message,
        normalized_state,
    )


def resolve_purchase_reference_fact(
    application_service: ApplicationService | None,
    customer_id: str | None,
    product_reference: str,
) -> dict[str, Any] | None:
    """Resolve a named purchase reference and return fact fields."""
    resolved_purchase = resolve_purchase_reference(
        application_service,
        customer_id,
        product_reference,
    )
    if resolved_purchase is None:
        return None
    return resolve_purchase_fact_by_id(
        application_service,
        customer_id,
        resolved_purchase["id"],
    )


def resolve_purchase_fact_by_id(
    application_service: ApplicationService | None,
    customer_id: str | None,
    purchase_id: str | None,
) -> dict[str, Any] | None:
    """Resolve one purchase id to model-facing fact fields."""
    if application_service is None or customer_id is None or purchase_id is None:
        return None

    for purchase in application_service.list_user_purchases(customer_id):
        if str(purchase.get("id")) == purchase_id:
            return build_resolved_purchase_fact(purchase)

    return None


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


def build_resolved_purchase_fact(purchase: dict[str, Any]) -> dict[str, Any]:
    """Return a small resolved purchase shape for model-facing account facts."""
    amount_cents = int(purchase.get("amount_cents") or 0)
    return {
        **build_resolved_purchase(purchase),
        "amount_cents": amount_cents,
        "amount_display": format_cents(amount_cents),
        "purchased_at": purchase.get("purchased_at"),
    }


def normalize_match_text(value: str) -> str:
    """Normalize text for lightweight product resolution."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())
