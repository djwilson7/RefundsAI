"""Model-facing purchase fact resolution."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.ranking import (
    has_selected_single_purchase_reference,
    list_purchases_by_ids,
    parse_purchase_ranking_reference,
    select_ranked_purchase,
)
from refunds_ai_api.services.ai_chat.routing import has_page_context_reference
from refunds_ai_api.services.ai_chat.state import (
    normalize_conversation_state,
    normalize_page_context,
)
from refunds_ai_api.services.application import ApplicationService
from refunds_ai_api.services.money import format_cents

from .products import extract_product_reference
from .purchases import (
    build_resolved_purchase,
    resolve_purchase_reference,
)


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

def build_resolved_purchase_fact(purchase: dict[str, Any]) -> dict[str, Any]:
    """Return a small resolved purchase shape for model-facing account facts."""
    amount_cents = int(purchase.get("amount_cents") or 0)
    return {
        **build_resolved_purchase(purchase),
        "amount_cents": amount_cents,
        "amount_display": format_cents(amount_cents),
        "purchased_at": purchase.get("purchased_at"),
    }
