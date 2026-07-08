"""Product and order-reference text parsing."""

from __future__ import annotations

import re

from refunds_ai_api.services.ai_chat.entity_extraction import (
    clean_entity_text,
    extract_entity,
    is_contextual_reference,
    is_named_entity_candidate,
)
from refunds_ai_api.services.ai_chat.ranking import has_purchase_ranking_reference
from refunds_ai_api.services.ai_chat.responses import SUPPORTED_ACCOUNT_TOPICS
from refunds_ai_api.services.ai_chat.routing import parse_policy_purchase_type


def extract_product_reference(message: str) -> str | None:
    """Extract a likely named product/SKU/order reference from supported follow-up text."""
    normalized_message = message.strip().strip("?.! ").casefold()
    if not normalized_message or has_purchase_ranking_reference(normalized_message):
        return None

    entity = extract_entity(message)
    return (
        entity.entity_value
        if entity.entity_kind in {"named_product", "purchase_id", "sku"}
        else None
    )

def clean_product_reference(value: str) -> str:
    """Remove common trailing policy words around an extracted product reference."""
    return clean_entity_text(value)

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
    if is_contextual_reference(candidate) or is_demonstrative_product_reference(
        normalized_candidate
    ):
        return False
    if is_generic_purchase_type_reference(normalized_candidate):
        return False

    return is_named_entity_candidate(candidate)

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
        "item",
        "items",
        "return",
        "returns",
        "digital",
        "physical",
        "subscription",
        "subscriptions",
        "please",
    }
    return terms.issubset(generic_terms)

def explicit_purchase_type_word(product_reference: str) -> str | None:
    """Return explicit product category words that should constrain resolution."""
    normalized_reference = normalize_match_text(product_reference)
    terms = set(normalized_reference.split())
    if terms & {"subscription", "subscriptions"}:
        return "subscription"
    if terms & {"digital", "download", "downloads"}:
        return "digital"
    if terms & {"physical", "shipped", "shipment"}:
        return "physical"
    return None

def build_unresolved_product_response(product_reference: str) -> str:
    """Return a grounded clarification when product entity resolution fails."""
    return (
        f"I couldn't find a purchase matching '{product_reference}' in your account history. "
        "Could you confirm the product name, order number, SKU, or purchase date? "
        f"I can also help with {SUPPORTED_ACCOUNT_TOPICS}."
    )

def normalize_match_text(value: str) -> str:
    """Normalize text for lightweight product resolution."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())
