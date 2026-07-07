"""Refund-eligibility purchase-scope resolution."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.dates import parse_date_range_query
from refunds_ai_api.services.ai_chat.models import EligibilityResolution
from refunds_ai_api.services.ai_chat.ranking import has_reference_phrase
from refunds_ai_api.services.ai_chat.routing import (
    has_context_reference,
    has_page_context_reference,
    has_refund_eligibility_intent,
    parse_purchase_type_filter,
)
from refunds_ai_api.services.ai_chat.scopes import selected_purchase_ids_for_refund_context
from refunds_ai_api.services.ai_chat.state import (
    normalize_conversation_state,
    normalize_page_context,
)
from refunds_ai_api.services.ai_chat.tools import get_purchase_history_by_date_range
from refunds_ai_api.services.application import ApplicationService

from .products import extract_product_reference
from .purchases import (
    resolve_purchase_by_id,
    resolve_purchase_mention,
    resolve_purchase_reference_for_state,
    resolve_selected_single_purchase,
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
        resolved_purchase, unresolved_reference = resolve_purchase_reference_for_state(
            application_service,
            customer_id,
            product_reference,
            normalized_state,
        )
        if resolved_purchase is None:
            context = (
                "scoped_product_type_mismatch"
                if unresolved_reference is not None
                else "product"
            )
            return EligibilityResolution(
                [],
                context,
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
        if not selected_ids:
            active_result_set = normalized_state.get("active_result_set")
            if isinstance(active_result_set, dict) and any(
                has_reference_phrase(normalized_message, term)
                for term in ("those", "them", "these")
            ):
                selected_ids = [
                    str(purchase_id)
                    for purchase_id in active_result_set.get("purchase_ids", [])
                    if isinstance(purchase_id, str)
                ]
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

    policy_follow_up_resolution = resolve_policy_follow_up_eligibility(
        application_service,
        customer_id,
        normalized_state,
    )
    if policy_follow_up_resolution is not None:
        return policy_follow_up_resolution

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

def resolve_policy_follow_up_eligibility(
    application_service: ApplicationService | None,
    customer_id: str | None,
    conversation_state: dict[str, Any],
) -> EligibilityResolution | None:
    """Resolve policy confirmation follow-ups to the active purchase scope."""
    active_workflow = conversation_state.get("active_workflow")
    if not isinstance(active_workflow, dict) or active_workflow.get("kind") != "refund_policy":
        return None

    active_result_set = conversation_state.get("active_result_set")
    if isinstance(active_result_set, dict):
        purchase_ids = [
            str(purchase_id)
            for purchase_id in active_result_set.get("purchase_ids", [])
            if isinstance(purchase_id, str)
        ]
        if purchase_ids:
            return EligibilityResolution(purchase_ids, "selected_set")

    active_purchase = conversation_state.get("active_purchase")
    if isinstance(active_purchase, dict):
        purchase_id = active_purchase.get("purchase_id")
        if isinstance(purchase_id, str):
            return EligibilityResolution(
                [purchase_id],
                "selected_purchase",
                resolved_purchase=resolve_purchase_by_id(
                    application_service,
                    customer_id,
                    purchase_id,
                ),
            )

    selected_purchase_id = conversation_state.get("selected_purchase_id")
    if isinstance(selected_purchase_id, str):
        return EligibilityResolution(
            [selected_purchase_id],
            "selected_purchase",
            resolved_purchase=resolve_purchase_by_id(
                application_service,
                customer_id,
                selected_purchase_id,
            ),
        )

    return None
