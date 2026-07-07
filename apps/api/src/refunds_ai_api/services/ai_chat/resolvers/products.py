"""Product and order-reference text parsing."""

from __future__ import annotations

import re

from refunds_ai_api.services.ai_chat.ranking import has_purchase_ranking_reference
from refunds_ai_api.services.ai_chat.responses import SUPPORTED_ACCOUNT_TOPICS
from refunds_ai_api.services.ai_chat.routing import parse_policy_purchase_type


def extract_product_reference(message: str) -> str | None:
    """Extract a likely named product/SKU/order reference from supported follow-up text."""
    stripped_message = message.strip().strip("?.! ")
    normalized_message = stripped_message.casefold()
    if not stripped_message or has_purchase_ranking_reference(normalized_message):
        return None

    patterns = (
        r"\bi(?:'d|d| would)\s+like\s+to\s+get\s+a\s+refund\s+for\s+(?:my\s+|the\s+)?(.+)$",
        r"\bi(?:'d|d| would)\s+like\s+a\s+refund\s+for\s+(?:my\s+|the\s+)?(.+)$",
        r"\bare\s+we\s+able\s+to\s+refund\s+(?:my\s+|the\s+)?(.+)$",
        r"\bare\s+we\s+able\s+to\s+get\s+a\s+refund\s+for\s+(?:my\s+|the\s+)?(.+)$",
        r"\bcan\s+we\s+refund\s+(?:my\s+|the\s+)?(.+)$",
        r"\bcan\s+we\s+get\s+a\s+refund\s+for\s+(?:my\s+|the\s+)?(.+)$",
        r"\bcan\s+i\s+refund\s+(?:my\s+|the\s+)?(.+)$",
        r"\bcan\s+i\s+get\s+a\s+refund\s+for\s+(?:my\s+|the\s+)?(.+)$",
        r"\bam\s+i\s+able\s+to\s+get\s+a\s+refund\s+for\s+(?:my\s+|the\s+)?(.+)$",
        r"\bcan\s+i\s+get\s+my\s+money\s+back\s+for\s+(?:my\s+|the\s+)?(.+)$",
        r"\bcan\s+(?:my\s+|the\s+)?(.+?)\s+be\s+refunded\b",
        r"\bis\s+(?:my\s+|the\s+)?(.+?)\s+refund(?:ed|able)\b",
        r"\bis\s+(?:my\s+|the\s+)?(.+?)\s+eligible\s+for\s+(?:a\s+)?refund\b",
        r"\bcheck\s+if\s+(?:my\s+|the\s+)?(.+?)\s+is\s+refund(?:ed|able)\b",
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
    candidate = re.sub(
        r"\bi\s+purchased\b.*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(
        r"\bpurchased\s+back\s+in\s+\w+\b.*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(
        r"\bback\s+in\s+\w+\b.*$",
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
