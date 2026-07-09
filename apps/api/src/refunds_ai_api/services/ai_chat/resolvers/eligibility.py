"""Refund-eligibility purchase-scope resolution."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.dates import parse_date_range_query
from refunds_ai_api.services.ai_chat.entity_extraction import (
    CurrentMessageEntity,
    extract_entity,
)
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

from .products import explicit_purchase_type_word
from .purchases import (
    resolve_purchase_by_id,
    resolve_purchase_from_selected_set,
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
    current_message_entity: CurrentMessageEntity | None = None,
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

    entity_result = extract_entity(message)
    if (
        current_message_entity is not None
        and current_message_entity.entity_kind
        in {"named_product", "purchase_id", "sku"}
    ):
        if current_message_entity.matched_purchase_id is None:
            return EligibilityResolution(
                [],
                "product",
                unresolved_product_reference=current_message_entity.raw_text,
            )
        resolved_purchase = resolve_purchase_by_id(
            application_service,
            customer_id,
            current_message_entity.matched_purchase_id,
        )
        if resolved_purchase is not None:
            requested_type = explicit_purchase_type_word(current_message_entity.raw_text)
            if (
                requested_type is not None
                and resolved_purchase.get("purchase_type") != requested_type
            ):
                return EligibilityResolution(
                    [],
                    "scoped_product_type_mismatch",
                    unresolved_product_reference=current_message_entity.raw_text,
                )
            return EligibilityResolution(
                [resolved_purchase["id"]],
                "product",
                resolved_purchase=resolved_purchase,
            )

    product_reference = (
        entity_result.entity_value
        if entity_result.entity_kind in {"named_product", "purchase_id", "sku"}
        else None
    )
    if product_reference is None:
        product_reference = _pending_product_reference_follow_up(
            message,
            normalized_state,
        )
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

        active_purchase = normalized_state.get("active_purchase")
        if isinstance(active_purchase, dict):
            resolved_active_purchase = resolve_purchase_by_id(
                application_service,
                customer_id,
                active_purchase.get("purchase_id"),
            )
            if resolved_active_purchase is not None:
                return EligibilityResolution(
                    [resolved_active_purchase["id"]],
                    "selected_purchase",
                    resolved_purchase=resolved_active_purchase,
                )

        active_result_set = normalized_state.get("active_result_set")
        if (
            entity_result.entity_kind == "contextual_reference"
            and isinstance(active_result_set, dict)
            and active_result_set.get("purchase_ids")
        ):
            selected_from_result_set = resolve_purchase_from_selected_set(
                application_service,
                customer_id,
                message,
                {
                    **normalized_state,
                    "selected_purchase_ids": active_result_set["purchase_ids"],
                },
            )
            if selected_from_result_set is not None:
                return EligibilityResolution(
                    [selected_from_result_set["id"]],
                    "selected_purchase",
                    resolved_purchase=selected_from_result_set,
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
        if entity_result.entity_kind == "contextual_reference":
            return EligibilityResolution([], "entity_required")

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
    if entity_result.entity_kind == "named_product" and purchase_mention is not None:
        return EligibilityResolution(
            [purchase_mention["id"]],
            "product",
            resolved_purchase=purchase_mention,
        )

    if entity_result.rejected_entity_candidates or entity_result.entity_kind == "none":
        if _has_refund_action_without_entity(message):
            return EligibilityResolution([], "entity_required")

    purchase_ids = [
        str(purchase["id"])
        for purchase in application_service.list_user_purchases(customer_id)
        if isinstance(purchase.get("id"), str)
    ]
    return EligibilityResolution(purchase_ids, "all_purchases")


def _has_refund_action_without_entity(message: str) -> bool:
    """Return whether a refund request lacks a searchable or contextual entity."""
    normalized = message.casefold()
    return any(term in normalized for term in ("refund", "return", "cancel"))

def _pending_product_reference_follow_up(
    message: str,
    conversation_state: dict[str, Any],
) -> str | None:
    pending_reference = conversation_state.get("pending_refund_product_reference")
    if not isinstance(pending_reference, dict):
        return None
    product_reference = pending_reference.get("product_reference")
    if not isinstance(product_reference, str) or not product_reference:
        return None
    candidate = message.strip().strip("?.! ")
    if not candidate or len(candidate.split()) > 5:
        return None
    return candidate

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
