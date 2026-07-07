"""Refund-policy lookup resolution."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.routing import (
    has_page_context_reference,
    has_policy_follow_up_intent,
    parse_refund_policy_query,
)
from refunds_ai_api.services.ai_chat.state import (
    normalize_conversation_state,
    normalize_page_context,
)
from refunds_ai_api.services.application import ApplicationService

from .products import extract_product_reference
from .purchases import (
    resolve_global_ranked_purchase,
    resolve_purchase_by_id,
    resolve_purchase_from_selected_set,
    resolve_purchase_mention,
    resolve_purchase_reference_for_state,
    resolve_selected_single_purchase,
)


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
            resolved_purchase, _unresolved_reference = resolve_purchase_reference_for_state(
                application_service,
                customer_id,
                product_reference,
                normalized_state,
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
        resolved_purchase, _unresolved_reference = resolve_purchase_reference_for_state(
            application_service,
            customer_id,
            product_reference,
            normalized_state,
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
