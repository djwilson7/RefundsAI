"""Deterministic entity extraction for purchase-scoped chat requests."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

RejectedEntityReason = Literal[
    "action_phrase",
    "pronoun",
    "generic_reference",
    "support_phrase",
    "too_broad",
]
EntityKind = Literal[
    "named_product",
    "purchase_id",
    "sku",
    "contextual_reference",
    "purchase_type",
    "none",
]
ResolutionScope = Literal[
    "full_purchase_history",
    "page_reference",
    "active_purchase",
    "active_result_set",
    "purchase_type",
    "none",
]
ContextResolutionSource = Literal[
    "active_purchase",
    "page_reference",
    "active_result_set",
    "last_completed_refund",
    "none",
]


@dataclass(frozen=True)
class RejectedEntityCandidate:
    """Candidate phrase rejected before purchase search."""

    text: str
    reason: RejectedEntityReason

    def as_dict(self) -> dict[str, str]:
        return {"text": self.text, "reason": self.reason}


@dataclass(frozen=True)
class EntityExtractionResult:
    """Resolved entity signal for one user message."""

    intent: str
    raw_entity_text: str | None
    entity_kind: EntityKind
    entity_value: str | None
    rejected_entity_candidates: list[RejectedEntityCandidate] = field(default_factory=list)
    context_resolution_source: ContextResolutionSource = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "raw_entity_text": self.raw_entity_text,
            "entity_kind": self.entity_kind,
            "entity_value": self.entity_value,
            "rejected_entity_candidates": [
                candidate.as_dict() for candidate in self.rejected_entity_candidates
            ],
            "context_resolution_source": self.context_resolution_source,
        }


@dataclass(frozen=True)
class CurrentMessageEntity:
    """Normalized current-message entity and deterministic match metadata."""

    raw_text: str | None
    normalized_text: str | None
    entity_kind: EntityKind
    resolution_scope: ResolutionScope
    matched_purchase_id: str | None = None
    match_confidence: float | None = None
    rejected_reason: RejectedEntityReason | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "entity_kind": self.entity_kind,
            "resolution_scope": self.resolution_scope,
            "matched_purchase_id": self.matched_purchase_id,
            "match_confidence": self.match_confidence,
            "rejected_reason": self.rejected_reason,
        }


_ENTITY_PATTERNS = (
    r"\bi(?:'d|d| would)\s+like\s+to\s+get\s+a\s+refund\s+for\s+(?:my\s+|the\s+)?(.+)$",
    r"\bi(?:'d|d| would)\s+like\s+a\s+refund\s+for\s+(?:my\s+|the\s+)?(.+)$",
    r"\bi\s+want\s+to\s+return\s+(?:my\s+|the\s+)?(.+)$",
    r"\bi\s+want\s+to\s+refund\s+(?:my\s+|the\s+)?(.+)$",
    r"\bcan\s+you\s+please\s+refund\s+(?:my\s+|the\s+)?(.+)$",
    r"\bcan\s+you\s+refund\s+(?:my\s+|the\s+)?(.+)$",
    r"\bwhy\s+can(?:'|no)?t\s+you\s+refund\s+(?:my\s+|the\s+)?(.+)$",
    r"\bare\s+we\s+able\s+to\s+refund\s+(?:my\s+|the\s+)?(.+)$",
    r"\bare\s+we\s+able\s+to\s+get\s+a\s+refund\s+for\s+(?:my\s+|the\s+)?(.+)$",
    r"\bcan\s+we\s+refund\s+(?:my\s+|the\s+)?(.+)$",
    r"\bcan\s+we\s+get\s+a\s+refund\s+for\s+(?:my\s+|the\s+)?(.+)$",
    r"\bcan\s+i\s+refund\s+(?:my\s+|the\s+)?(.+)$",
    r"\bam\s+i\s+able\s+to\s+refund\s+(?:my\s+|the\s+)?(.+)$",
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
    r"^refund\s+(?:my\s+|the\s+)?(.+)$",
    r"^return\s+(?:my\s+|the\s+)?(.+)$",
)

_ACTION_TERMS = {
    "cancel",
    "cancellation",
    "check",
    "fund",
    "funds",
    "issue",
    "refund",
    "refunded",
    "release",
    "return",
    "status",
}
_PRONOUN_TERMS = {"it", "its", "one", "them", "they"}
_DETERMINER_TERMS = {"a", "an", "my", "our", "that", "the", "these", "this", "those"}
_GENERIC_NOUN_TERMS = {
    "item",
    "items",
    "order",
    "orders",
    "product",
    "products",
    "purchase",
    "purchases",
    "subscription",
    "subscriptions",
}
_SUPPORT_TERMS = {"please", "help", "support"}
_PURCHASE_TYPE_TERMS = {"digital", "physical", "subscription", "subscriptions"}


def extract_entity(
    message: str,
    *,
    context_resolution_source: ContextResolutionSource = "none",
) -> EntityExtractionResult:
    """Extract the best entity candidate without treating generic phrases as products."""
    intent = extract_intent(message)
    rejected: list[RejectedEntityCandidate] = []

    for raw_candidate in _candidate_entity_texts(message):
        candidate = clean_entity_text(raw_candidate)
        if not candidate:
            continue
        kind = classify_entity_text(candidate)
        if kind == "named_product":
            return EntityExtractionResult(
                intent=intent,
                raw_entity_text=candidate,
                entity_kind=kind,
                entity_value=candidate,
                rejected_entity_candidates=rejected,
                context_resolution_source="none",
            )
        if kind in {"purchase_id", "sku", "purchase_type", "contextual_reference"}:
            return EntityExtractionResult(
                intent=intent,
                raw_entity_text=candidate,
                entity_kind=kind,
                entity_value=candidate,
                rejected_entity_candidates=rejected,
                context_resolution_source=(
                    context_resolution_source
                    if kind == "contextual_reference"
                    else "none"
                ),
            )
        rejected.append(
            RejectedEntityCandidate(
                text=candidate,
                reason=rejection_reason(candidate),
            )
        )

    return EntityExtractionResult(
        intent=intent,
        raw_entity_text=None,
        entity_kind="none",
        entity_value=None,
        rejected_entity_candidates=rejected,
        context_resolution_source=context_resolution_source,
    )


def extract_intent(message: str) -> str:
    """Return the broad action/intent separate from entity text."""
    normalized = normalize_entity_text(message)
    if any(term in normalized for term in ("policy", "rule", "requirement", "window")):
        return "refund_policy"
    if any(term in normalized for term in ("eligible", "refundable", "able to refund")):
        return "eligibility"
    if "cancel" in normalized and "subscription" in normalized:
        return "cancel_subscription"
    if any(term in normalized for term in ("status", "where is", "check")):
        return "refund_status"
    if any(term in normalized for term in ("release funds", "issue funds", "money back")):
        return "refund_mutation"
    if "return" in normalized or "refund" in normalized or "cancel" in normalized:
        return "refund_mutation"
    return "unknown"


def clean_entity_text(value: str) -> str:
    """Trim filler around a raw candidate."""
    candidate = value.strip().strip("?.! ")
    candidate = re.sub(r"\bplease\b$", "", candidate, flags=re.IGNORECASE).strip()
    candidate = re.sub(
        r"\b(refund|return)\s+(policy|rules?|requirements?|window)\b",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"\bi\s+purchased\b.*$", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(
        r"\bpurchased\s+back\s+in\s+\w+\b.*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"\bback\s+in\s+\w+\b.*$", "", candidate, flags=re.IGNORECASE)
    return " ".join(candidate.split())


def classify_entity_text(candidate: str) -> EntityKind:
    """Classify a candidate entity before purchase lookup."""
    normalized = normalize_entity_text(candidate)
    terms = set(normalized.split())
    if not normalized:
        return "none"
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{27,}", normalized):
        return "purchase_id"
    if re.fullmatch(r"(?:rai|dig|phy|sub)[-\s][a-z0-9][a-z0-9-\s]+", normalized):
        return "sku"
    if is_contextual_reference(candidate):
        return "contextual_reference"
    if (
        terms
        and bool(terms & _PURCHASE_TYPE_TERMS)
        and terms.issubset(
            _PURCHASE_TYPE_TERMS | _DETERMINER_TERMS | _GENERIC_NOUN_TERMS
        )
    ):
        return "purchase_type"
    if not is_named_entity_candidate(candidate):
        return "none"
    return "named_product"


def is_named_entity_candidate(candidate: str) -> bool:
    """Return whether a phrase is specific enough to send to purchase search."""
    normalized = normalize_entity_text(candidate)
    terms = set(normalized.split())
    if not terms:
        return False
    if terms.issubset(_ACTION_TERMS):
        return False
    if terms.issubset(_PRONOUN_TERMS | _DETERMINER_TERMS):
        return False
    if terms.issubset(
        _ACTION_TERMS
        | _PRONOUN_TERMS
        | _DETERMINER_TERMS
        | _GENERIC_NOUN_TERMS
        | _SUPPORT_TERMS
    ):
        return False
    meaningful_terms = terms - (
        _ACTION_TERMS | _PRONOUN_TERMS | _DETERMINER_TERMS | _SUPPORT_TERMS
    )
    return bool(meaningful_terms)


def is_contextual_reference(candidate: str) -> bool:
    """Return whether candidate should be resolved through context, not search."""
    normalized = normalize_entity_text(candidate)
    terms = set(normalized.split())
    if normalized in {
        "it",
        "its",
        "that one",
        "the first one",
        "the last one",
        "this item",
        "this order",
        "this product",
        "this purchase",
        "the product",
        "the return",
        "that item",
        "that purchase",
        "that product",
        "this please",
    }:
        return True
    return bool(
        terms
        and terms.issubset(
            _PRONOUN_TERMS | _DETERMINER_TERMS | _GENERIC_NOUN_TERMS | _SUPPORT_TERMS
        )
        and bool(terms & (_PRONOUN_TERMS | _DETERMINER_TERMS))
    )


def rejection_reason(candidate: str) -> RejectedEntityReason:
    """Return the stable reason a candidate is not searchable."""
    normalized = normalize_entity_text(candidate)
    terms = set(normalized.split())
    if terms and terms.issubset(_ACTION_TERMS):
        return "action_phrase"
    if terms and terms.issubset(_PRONOUN_TERMS | _DETERMINER_TERMS):
        return "pronoun"
    if is_contextual_reference(candidate):
        return "generic_reference"
    if terms and terms.issubset(_SUPPORT_TERMS | _DETERMINER_TERMS):
        return "support_phrase"
    return "too_broad"


def normalize_entity_text(value: str) -> str:
    """Normalize text for candidate classification."""
    return " ".join(re.sub(r"[^a-z0-9-]+", " ", value.casefold()).split())


def build_current_message_entity(
    result: EntityExtractionResult,
) -> CurrentMessageEntity:
    """Build the normalized entity contract before contextual resolution."""
    scope: ResolutionScope = "none"
    if result.entity_kind in {"named_product", "purchase_id", "sku"}:
        scope = "full_purchase_history"
    elif result.entity_kind == "purchase_type":
        scope = "purchase_type"
    elif result.entity_kind == "contextual_reference":
        source_to_scope: dict[ContextResolutionSource, ResolutionScope] = {
            "page_reference": "page_reference",
            "active_purchase": "active_purchase",
            "active_result_set": "active_result_set",
            "last_completed_refund": "active_purchase",
            "none": "none",
        }
        scope = source_to_scope[result.context_resolution_source]

    rejected_reason = (
        result.rejected_entity_candidates[0].reason
        if result.entity_kind == "none" and result.rejected_entity_candidates
        else None
    )
    return CurrentMessageEntity(
        raw_text=result.raw_entity_text,
        normalized_text=(
            normalize_entity_text(result.raw_entity_text)
            if result.raw_entity_text is not None
            else None
        ),
        entity_kind=result.entity_kind,
        resolution_scope=scope,
        rejected_reason=rejected_reason,
    )


def _candidate_entity_texts(message: str) -> list[str]:
    stripped = message.strip().strip("?.! ")
    candidates: list[str] = []
    for pattern in _ENTITY_PATTERNS:
        match = re.search(pattern, stripped, flags=re.IGNORECASE)
        if match is not None:
            candidates.append(match.group(1))
    return candidates
