"""Deterministic refund policy catalog used by AI policy lookup tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PolicyScope = Literal["general", "product_type", "funds_release", "administrative_review"]
PolicyPurchaseType = Literal["digital", "physical", "subscription"]

POLICY_SOURCE = "docs/REFUND_POLICY.md"
POLICY_EFFECTIVE_DATE = "July 3, 2026"


@dataclass(frozen=True)
class PolicySection:
    """One structured refund policy section."""

    key: str
    title: str
    facts: tuple[str, ...]


PRODUCT_POLICY_SECTIONS: dict[PolicyPurchaseType, PolicySection] = {
    "physical": PolicySection(
        key="physical",
        title="Physical Products",
        facts=(
            "Physical products may be returned within 30 calendar days of the original "
            "purchase date.",
            "The refund request must be submitted before the 31st calendar day following "
            "the original purchase.",
            "After approval, the product must be returned using the designated shipping carrier.",
            "The return package must be accepted by the carrier before the refund begins "
            "processing.",
            "Requests submitted after the 30-day return window are not eligible for refund.",
        ),
    ),
    "digital": PolicySection(
        key="digital",
        title="Digital Products",
        facts=(
            "Digital products may be refunded within 15 calendar days of the original purchase.",
            "The issued activation code, license, or digital entitlement must not have "
            "been redeemed.",
            "Approved digital refunds permanently invalidate the associated digital "
            "entitlement before processing.",
            "Digital products that have already been redeemed are not eligible for refund.",
        ),
    ),
    "subscription": PolicySection(
        key="subscription",
        title="Subscription Products",
        facts=(
            "Subscription purchases may be cancelled at any time.",
            "Customers may request a full refund within 48 hours of the original purchase "
            "if the subscription remains active.",
            "After the first 48 hours, eligible refunds are prorated based on the unused "
            "portion of the current active billing period.",
            "Refunds are limited to the current active billing period and cannot be "
            "applied retroactively to previous billing cycles.",
            "Subscriptions that have expired without an active billing period are not "
            "eligible for refund.",
            "Approved subscription refunds cancel the subscription and disable auto-renewal.",
        ),
    ),
}

GLOBAL_POLICY_SECTIONS: dict[str, PolicySection] = {
    "refund_processing": PolicySection(
        key="refund_processing",
        title="Refund Processing",
        facts=(
            "Approved refunds are processed using the original payment method whenever possible.",
            "Most refunds are completed within 3-10 business days, depending on the "
            "financial institution or payment provider.",
        ),
    ),
    "administrative_review": PolicySection(
        key="administrative_review",
        title="Administrative Review",
        facts=(
            "Certain refund requests may require additional review before a final decision "
            "is made.",
            "Review examples include incomplete purchase information, suspected fraud or "
            "abuse, unverifiable requests, or circumstances requiring investigation.",
            "Additional review does not guarantee refund approval.",
        ),
    ),
    "policy_updates": PolicySection(
        key="policy_updates",
        title="Policy Updates",
        facts=(
            "Refund policy updates may apply to future purchases unless otherwise required "
            "by applicable law.",
        ),
    ),
}


def get_refund_policy(
    *,
    scope: PolicyScope,
    purchase_type: PolicyPurchaseType | None = None,
) -> dict[str, object]:
    """Return deterministic refund policy sections for one policy lookup scope."""
    sections: list[PolicySection] = []

    if scope == "general":
        sections.extend(PRODUCT_POLICY_SECTIONS.values())
        sections.extend(GLOBAL_POLICY_SECTIONS.values())
    elif scope == "product_type":
        if purchase_type is None:
            sections.extend(PRODUCT_POLICY_SECTIONS.values())
        else:
            sections.append(PRODUCT_POLICY_SECTIONS[purchase_type])
    elif scope == "funds_release":
        if purchase_type is not None:
            sections.append(PRODUCT_POLICY_SECTIONS[purchase_type])
        sections.append(GLOBAL_POLICY_SECTIONS["refund_processing"])
    elif scope == "administrative_review":
        if purchase_type is not None:
            sections.append(PRODUCT_POLICY_SECTIONS[purchase_type])
        sections.append(GLOBAL_POLICY_SECTIONS["administrative_review"])

    return {
        "scope": scope,
        "purchase_type": purchase_type,
        "effective_date": POLICY_EFFECTIVE_DATE,
        "sections": [serialize_policy_section(section) for section in sections],
        "source": POLICY_SOURCE,
    }


def serialize_policy_section(section: PolicySection) -> dict[str, object]:
    """Serialize one policy section for model-facing tool output."""
    return {
        "key": section.key,
        "title": section.title,
        "facts": list(section.facts),
    }
