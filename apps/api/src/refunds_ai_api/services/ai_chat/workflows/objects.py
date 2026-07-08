"""Conversation object resolution for deterministic chat workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from refunds_ai_api.services.ai_chat.dates import parse_date_range_query
from refunds_ai_api.services.ai_chat.parsing import parse_amount_threshold_query
from refunds_ai_api.services.ai_chat.ranking import has_reference_phrase
from refunds_ai_api.services.ai_chat.resolution import extract_product_reference
from refunds_ai_api.services.ai_chat.routing import (
    has_account_fact_intent,
    parse_purchase_type_filter,
)
from refunds_ai_api.services.ai_chat.state import (
    normalize_conversation_state,
    normalize_page_context,
)
from refunds_ai_api.services.ai_chat.workflow import parse_refund_confirmation_command


class ConversationObjectKind(StrEnum):
    """Grounded object a user turn is asking about."""

    FULL_PURCHASE_HISTORY = "full_purchase_history"
    ACTIVE_RESULT_SET = "active_result_set"
    ACTIVE_PURCHASE = "active_purchase"
    PAGE_PURCHASE = "page_purchase"
    PRODUCT_REFERENCE = "product_reference"
    PURCHASE_TYPE = "purchase_type"
    DATE_RANGE = "date_range"
    AMOUNT_THRESHOLD = "amount_threshold"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConversationObject:
    """Resolved object for workflow lookup."""

    kind: ConversationObjectKind
    label: str | None = None
    purchase_ids: tuple[str, ...] = ()
    purchase_type: str | None = None
    product_reference: str | None = None
    date_range: dict[str, Any] | None = None
    amount_threshold: dict[str, Any] | None = None
    source: Literal[
        "message",
        "active_result_set",
        "active_purchase",
        "page_context",
        "conversation_state",
        "fallback",
    ] = "fallback"


def resolve_conversation_object(
    message: str,
    *,
    conversation_state: Mapping[str, Any] | None,
    page_context: Mapping[str, Any] | None,
    runtime: Any | None = None,
    customer_id: str | None = None,
) -> ConversationObject:
    """Resolve the conversation object that should ground workflow routing."""
    del runtime, customer_id

    normalized_state = normalize_conversation_state(
        dict(conversation_state) if conversation_state is not None else None
    )
    normalized_message = message.casefold()

    if parse_refund_confirmation_command(message) is not None:
        active_refund_object = _active_refund_context_object(normalized_state)
        if active_refund_object is not None:
            return active_refund_object
        active_purchase_object = _active_purchase_object(normalized_state)
        if active_purchase_object is not None:
            return active_purchase_object

    if _has_policy_to_eligibility_follow_up(normalized_message, normalized_state):
        referenced_object = _referenced_conversation_object(
            normalized_state,
            page_context,
        )
        if referenced_object is not None:
            return referenced_object

    if has_reference_phrase(normalized_message, "that one"):
        singular_result = _singular_active_result_set_object(normalized_state)
        if singular_result is not None:
            return singular_result
        active_purchase_object = _active_purchase_object(normalized_state)
        if active_purchase_object is not None:
            return active_purchase_object
        page_object = _page_purchase_object(page_context)
        if page_object is not None:
            return page_object

    if has_reference_phrase(normalized_message, "it"):
        active_purchase_object = _active_purchase_object(normalized_state)
        if active_purchase_object is not None:
            return active_purchase_object
        page_object = _page_purchase_object(page_context)
        if page_object is not None:
            return page_object
        singular_result = _singular_active_result_set_object(normalized_state)
        if singular_result is not None:
            return singular_result

    if _has_demonstrative_product_reference(normalized_message):
        referenced_object = _referenced_conversation_object(
            normalized_state,
            page_context,
        )
        if referenced_object is not None:
            return referenced_object

    product_reference = extract_product_reference(message)
    if product_reference is not None:
        return ConversationObject(
            ConversationObjectKind.PRODUCT_REFERENCE,
            label=product_reference,
            product_reference=product_reference,
            source="message",
        )

    pending_product_reference = _pending_refund_product_reference_object(
        message,
        normalized_state,
    )
    if pending_product_reference is not None:
        return pending_product_reference

    purchase_type = parse_purchase_type_filter(message)
    if purchase_type is not None:
        return ConversationObject(
            ConversationObjectKind.PURCHASE_TYPE,
            label=_purchase_type_label(purchase_type),
            purchase_type=purchase_type,
            source="message",
        )

    date_range = parse_date_range_query(message)
    if date_range is not None:
        return ConversationObject(
            ConversationObjectKind.DATE_RANGE,
            label=date_range.get("label"),
            date_range=date_range,
            source="message",
        )

    amount_threshold = parse_amount_threshold_query(message)
    if amount_threshold is not None:
        return ConversationObject(
            ConversationObjectKind.AMOUNT_THRESHOLD,
            amount_threshold=amount_threshold,
            source="message",
        )

    if _has_plural_follow_up_reference(normalized_message):
        active_result_set_object = _active_result_set_object(normalized_state)
        if active_result_set_object is not None:
            return active_result_set_object

    if _has_context_reference(normalized_message):
        page_object = _page_purchase_object(page_context)
        if page_object is not None:
            return page_object
        active_purchase_object = _active_purchase_object(normalized_state)
        if active_purchase_object is not None:
            return active_purchase_object
        active_result_set_object = _active_result_set_object(normalized_state)
        if active_result_set_object is not None:
            return active_result_set_object

    page_object = _page_purchase_object(page_context)
    if page_object is not None:
        return page_object

    active_purchase_object = _active_purchase_object(normalized_state)
    if active_purchase_object is not None and _has_context_reference(normalized_message):
        return active_purchase_object

    active_result_set_object = _active_result_set_object(normalized_state)
    if active_result_set_object is not None and _has_context_reference(normalized_message):
        return active_result_set_object

    if has_account_fact_intent(message):
        return ConversationObject(
            ConversationObjectKind.FULL_PURCHASE_HISTORY,
            label="your purchase history",
            source="fallback",
        )

    return ConversationObject(ConversationObjectKind.UNKNOWN)


def _referenced_conversation_object(
    conversation_state: Mapping[str, Any],
    page_context: Mapping[str, Any] | None,
) -> ConversationObject | None:
    """Return the best existing object for a demonstrative follow-up."""
    active_result_set_object = _active_result_set_object(conversation_state)
    if active_result_set_object is not None:
        return active_result_set_object
    active_purchase_object = _active_purchase_object(conversation_state)
    if active_purchase_object is not None:
        return active_purchase_object
    return _page_purchase_object(page_context)


def _pending_refund_product_reference_object(
    message: str,
    conversation_state: Mapping[str, Any],
) -> ConversationObject | None:
    pending_reference = conversation_state.get("pending_refund_product_reference")
    if not isinstance(pending_reference, Mapping):
        return None
    product_reference = pending_reference.get("product_reference")
    if not isinstance(product_reference, str) or not product_reference:
        return None
    candidate = message.strip().strip("?.! ")
    if not candidate:
        return None
    normalized_candidate = candidate.casefold()
    if len(normalized_candidate.split()) > 5:
        return None
    if has_account_fact_intent(candidate):
        return None
    if parse_purchase_type_filter(candidate) is not None:
        return None
    return ConversationObject(
        ConversationObjectKind.PRODUCT_REFERENCE,
        label=candidate,
        product_reference=candidate,
        source="conversation_state",
    )


def _active_result_set_object(
    conversation_state: Mapping[str, Any],
) -> ConversationObject | None:
    active_result_set = conversation_state.get("active_result_set")
    if not isinstance(active_result_set, Mapping):
        return None
    purchase_ids = tuple(
        str(purchase_id)
        for purchase_id in active_result_set.get("purchase_ids", [])
        if isinstance(purchase_id, str)
    )
    if not purchase_ids:
        return None
    purchase_type = conversation_state.get("selected_purchase_type")
    if active_result_set.get("type") == "subscriptions":
        purchase_type = "subscription"
    return ConversationObject(
        ConversationObjectKind.ACTIVE_RESULT_SET,
        label=active_result_set.get("label")
        if isinstance(active_result_set.get("label"), str)
        else None,
        purchase_ids=purchase_ids,
        purchase_type=purchase_type
        if purchase_type in {"digital", "physical", "subscription"}
        else None,
        source="active_result_set",
    )


def _singular_active_result_set_object(
    conversation_state: Mapping[str, Any],
) -> ConversationObject | None:
    """Return active-result context only when it identifies exactly one purchase."""
    result = _active_result_set_object(conversation_state)
    if result is None or len(result.purchase_ids) != 1:
        return None
    return result


def _active_purchase_object(
    conversation_state: Mapping[str, Any],
) -> ConversationObject | None:
    active_purchase = conversation_state.get("active_purchase")
    if not isinstance(active_purchase, Mapping):
        return None
    purchase_id = active_purchase.get("purchase_id")
    product_name = active_purchase.get("product_name")
    purchase_type = active_purchase.get("purchase_type")
    if not isinstance(purchase_id, str) or not isinstance(product_name, str):
        return None
    return ConversationObject(
        ConversationObjectKind.ACTIVE_PURCHASE,
        label=product_name,
        purchase_ids=(purchase_id,),
        purchase_type=purchase_type
        if purchase_type in {"digital", "physical", "subscription"}
        else None,
        source="active_purchase",
    )


def _active_refund_context_object(
    conversation_state: Mapping[str, Any],
) -> ConversationObject | None:
    active_refund_context = conversation_state.get("active_refund_context")
    if not isinstance(active_refund_context, Mapping):
        return None
    purchase_id = active_refund_context.get("purchase_id")
    product_name = active_refund_context.get("product_name")
    purchase_type = active_refund_context.get("purchase_type")
    if not isinstance(purchase_id, str) or not isinstance(product_name, str):
        return None
    return ConversationObject(
        ConversationObjectKind.ACTIVE_PURCHASE,
        label=product_name,
        purchase_ids=(purchase_id,),
        purchase_type=purchase_type
        if purchase_type in {"digital", "physical", "subscription"}
        else None,
        source="conversation_state",
    )


def _page_purchase_object(
    page_context: Mapping[str, Any] | None,
) -> ConversationObject | None:
    normalized_page = normalize_page_context(dict(page_context or {}))
    purchase_id = normalized_page.get("purchase_id")
    if normalized_page.get("surface") != "purchase_detail" or not isinstance(
        purchase_id,
        str,
    ):
        return None
    return ConversationObject(
        ConversationObjectKind.PAGE_PURCHASE,
        purchase_ids=(purchase_id,),
        source="page_context",
    )


def _has_context_reference(message: str) -> bool:
    return _has_plural_follow_up_reference(message) or any(
        has_reference_phrase(message, term)
        for term in (
            "it",
            "its",
            "that",
            "that item",
            "that one",
            "this",
            "this item",
            "this order",
            "this product",
            "this purchase",
            "the first",
            "the last",
            "the latest",
            "latest",
            "most recent",
            "newest",
            "previous",
            "prior",
            "what about",
        )
    )


def _has_plural_follow_up_reference(message: str) -> bool:
    return any(
        has_reference_phrase(message, term)
        for term in (
            "them",
            "those",
            "these",
            "they",
            "what are they",
            "which ones",
            "list them",
            "show them",
        )
    )


def _has_demonstrative_product_reference(message: str) -> bool:
    return any(
        has_reference_phrase(message, term)
        for term in (
            "these products",
            "those products",
            "these purchases",
            "those purchases",
            "these types of products",
            "those types of products",
            "this type of product",
            "that type of product",
            "them",
            "they",
            "those",
            "these",
        )
    )


def _has_policy_to_eligibility_follow_up(
    message: str,
    conversation_state: Mapping[str, Any],
) -> bool:
    active_workflow = conversation_state.get("active_workflow")
    if not isinstance(active_workflow, Mapping):
        return False
    if active_workflow.get("kind") != "refund_policy":
        return False
    normalized_message = " ".join(message.replace(",", " ").strip(" .!?").split())
    follow_up_patterns = (
        "yes",
        "yes please",
        "yes lets check",
        "yes let's check",
        "yes please lets check",
        "yes please let's check",
        "lets check",
        "let's check",
        "check it",
        "check that",
        "check them",
        "check those",
        "check these",
    )
    return normalized_message in follow_up_patterns


def _purchase_type_label(purchase_type: str) -> str:
    return {
        "digital": "your digital purchases",
        "physical": "your physical purchases",
        "subscription": "your subscriptions",
    }.get(purchase_type, "your purchases")
