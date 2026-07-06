"""Refund workflow continuation and blocked-mutation helpers for chat."""

from __future__ import annotations

import re
from typing import Any

REFUND_CONTEXT_STAGES = {
    "eligibility_confirmed",
    "ineligible",
    "awaiting_customer_confirmation",
    "awaiting_return_label",
    "return_label_ready",
}
REFUND_WORKFLOW_NOT_READY_RESPONSE = (
    "I can explain refund policy, but I cannot start or change a refund workflow yet."
)
REFUND_WORKFLOW_CONFIRMATION_REQUIRED_RESPONSE = (
    "Please confirm the product name or order number before continuing the refund workflow."
)

def parse_refund_workflow_mutation_intent(message: str) -> str | None:
    """Return a blocked future-phase refund workflow mutation intent, if present."""
    normalized_message = message.casefold()
    if "refund" not in normalized_message and "return" not in normalized_message:
        return None

    mutation_patterns = (
        r"\bstart\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bbegin\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bsubmit\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bprocess\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bissue\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bprepare\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bfile\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\brequest\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"^\s*refund\s+(?:it|this|that|me|my\s+card|my\s+payment)\b",
        r"\bgo\s+ahead\s+and\s+refund\b",
        r"\bmake\s+the\s+refund\b",
        r"\bcancel\s+and\s+refund\b",
    )
    if any(re.search(pattern, normalized_message) for pattern in mutation_patterns):
        return "workflow"

    return None


def parse_refund_workflow_continuation_intent(message: str) -> str | None:
    """Return whether text asks to continue the active refund workflow."""
    normalized_message = message.casefold()
    continuation_patterns = (
        r"\bgenerate\s+(?:the\s+|a\s+)?return\s+label\b",
        r"\bcreate\s+(?:the\s+|a\s+)?return\s+label\b",
        r"\bstart\s+(?:the\s+|a\s+|my\s+)?return\b",
        r"\bi(?:'d| would)\s+like\s+to\s+return\s+(?:it|the\s+item|this\s+item|that\s+item)\b",
        r"\breturn\s+(?:it|the\s+item|this\s+item|that\s+item)\b",
        r"^\s*proceed\s*[.!?]*\s*$",
        r"^\s*yes,?\s+continue\s*[.!?]*\s*$",
    )
    if any(re.search(pattern, normalized_message) for pattern in continuation_patterns):
        return "workflow_continuation"

    return None


def build_refund_workflow_action_not_wired_response(
    active_refund_context: dict[str, Any],
) -> str:
    """Return a deterministic Phase 3 response for a resolved workflow action."""
    product_name = active_refund_context["product_name"]
    next_action = active_refund_context.get("next_action")

    if active_refund_context.get("eligible") is not True:
        return (
            f"{product_name} is not eligible for a refund workflow, so there is "
            "no refund action to continue."
        )

    if next_action == "generate_return_label":
        return (
            f"{product_name} is eligible, and the next required step is generating "
            "a return label. That workflow action is not wired yet."
        )

    if isinstance(next_action, str) and next_action:
        return (
            f"{product_name} is eligible, and the next required step is "
            f"{humanize_refund_action(next_action)}. That workflow action is not "
            "wired yet."
        )

    return (
        f"{product_name} is eligible for a refund workflow. The next workflow "
        "action is not wired yet."
    )


def humanize_refund_action(action: str) -> str:
    """Return user-facing text for backend refund action keys."""
    labels = {
        "generate_return_label": "generating a return label",
        "invalidate_code": "invalidating the issued code",
        "invalidate_digital_entitlement": "invalidating the issued code",
        "cancel_subscription": "cancelling the subscription",
        "await_carrier_acceptance": "waiting for carrier acceptance",
        "issue_funds": "issuing funds",
        "request_refund": "preparing the refund",
    }
    return labels.get(action, action.replace("_", " "))
