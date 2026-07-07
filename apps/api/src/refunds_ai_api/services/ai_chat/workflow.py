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
    "prepared",
    "issued",
}
REFUND_WORKFLOW_NOT_READY_RESPONSE = (
    "I can explain refund policy, but I cannot start or change the refund process yet."
)
REFUND_WORKFLOW_CONFIRMATION_REQUIRED_RESPONSE = (
    "Please confirm the product name or order number before continuing the refund process."
)

REFUND_CONFIRMATION_REQUIRED_SUFFIX = (
    "Reply with the exact confirmation command to continue. "
    "I will not change anything until you confirm."
)

REFUND_CONFIRMATION_COMMANDS: dict[str, dict[str, Any]] = {
    "subscription": {
        "command": "Confirm cancel and issue refund",
        "backend_action": "cancel_subscription",
        "mutation_action": "request_refund",
        "steps": (
            "cancel the subscription",
            "calculate the final refund",
            "issue the refund",
        ),
    },
    "digital": {
        "command": "Confirm invalidate code and issue refund",
        "backend_action": "invalidate_code",
        "mutation_action": "request_refund",
        "steps": (
            "invalidate the issued code",
            "calculate the final refund",
            "issue the refund",
        ),
    },
    "physical": {
        "command": "Confirm start return and issue label",
        "backend_action": "generate_return_label",
        "mutation_action": "request_refund",
        "steps": (
            "start the return",
            "generate the return label",
        ),
    },
}


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
        r"\brelease\s+(?:the\s+)?funds\b",
        r"\bfinali[sz]e\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bcomplete\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bclose\s+out\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bprepare\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bfile\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\brequest\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"^\s*refund\s+(?:it|this|that|them|those|these|me|my\s+card|my\s+payment)\b",
        r"\bgo\s+ahead\s+and\s+refund\b",
        r"\bmake\s+the\s+refund\b",
        r"\bcancel\s+and\s+refund\b",
    )
    if any(re.search(pattern, normalized_message) for pattern in mutation_patterns):
        return "workflow"

    return None


def parse_refund_workflow_mutation_action(message: str) -> str | None:
    """Return the concrete refund mutation action requested by the customer."""
    normalized_message = message.casefold()
    if "refund" not in normalized_message and "return" not in normalized_message:
        return None

    issue_patterns = (
        r"\bissue\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\brelease\s+(?:the\s+)?funds\b",
        r"\bfinali[sz]e\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bcomplete\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bclose\s+out\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bprocess\s+(?:the\s+|a\s+|my\s+)?refund\b",
    )
    if any(re.search(pattern, normalized_message) for pattern in issue_patterns):
        return "issue_refund"

    if parse_refund_workflow_mutation_intent(message) is not None:
        return "request_refund"
    if parse_refund_workflow_continuation_intent(message) is not None:
        return "request_refund"

    return None


def parse_refund_workflow_confirmation_intent(message: str) -> bool:
    """Return whether the message directly confirms a pending refund action."""
    if parse_refund_confirmation_command(message) is not None:
        return True
    normalized_message = message.casefold().strip()
    confirmation_patterns = (
        r"^yes[.!]?$",
        r"^yes,?\s+please[.!]?$",
        r"^yes,?\s+(?:start|begin|request|prepare|issue|process|complete|finali[sz]e|close\s+out)\s+(?:it|the\s+refund|my\s+refund)[.!]?$",
        r"^i\s+confirm[.!]?$",
        r"^confirm[.!]?$",
        r"^confirmed[.!]?$",
        r"^go\s+ahead[.!]?$",
        r"^go\s+ahead\s+and\s+(?:start|begin|request|prepare|issue|process|complete|finali[sz]e|close\s+out)\s+(?:it|the\s+refund|my\s+refund)[.!]?$",
        r"^do\s+it[.!]?$",
        r"^proceed[.!]?$",
    )
    return any(re.search(pattern, normalized_message) for pattern in confirmation_patterns)


def refund_confirmation_command_for_purchase_type(
    purchase_type: str | None,
) -> dict[str, Any] | None:
    """Return deterministic confirmation-command config for one purchase type."""
    if purchase_type not in REFUND_CONFIRMATION_COMMANDS:
        return None
    return REFUND_CONFIRMATION_COMMANDS[purchase_type]


def parse_refund_confirmation_command(message: str) -> str | None:
    """Return the purchase type whose canonical command was received."""
    normalized_message = normalize_refund_confirmation_command(message)
    if not normalized_message:
        return None
    for purchase_type, command_config in REFUND_CONFIRMATION_COMMANDS.items():
        command = command_config["command"]
        if normalized_message == normalize_refund_confirmation_command(command):
            return purchase_type
    return None


def is_refund_confirmation_boundary_reply(message: str) -> bool:
    """Return whether text is a command or generic reply at the mutation boundary."""
    return (
        parse_refund_confirmation_command(message) is not None
        or is_generic_refund_confirmation_reply(message)
        or parse_refund_workflow_mutation_intent(message) is not None
        or parse_refund_workflow_continuation_intent(message) is not None
    )


def is_generic_refund_confirmation_reply(message: str) -> bool:
    """Return whether text is an ambiguous reply that must not mutate state."""
    normalized_message = message.casefold().strip()
    generic_patterns = (
        r"^yes[.!]?$",
        r"^yes,?\s+please[.!]?$",
        r"^yes,?\s+(?:start|begin|request|prepare|issue|process|complete|finali[sz]e|close\s+out)\s+(?:it|the\s+refund|my\s+refund)[.!]?$",
        r"^i\s+confirm[.!]?$",
        r"^confirm[.!]?$",
        r"^confirmed[.!]?$",
        r"^go\s+ahead[.!]?$",
        r"^go\s+ahead\s+and\s+(?:start|begin|request|prepare|issue|process|complete|finali[sz]e|close\s+out)\s+(?:it|the\s+refund|my\s+refund)[.!]?$",
        r"^do\s+it[.!]?$",
        r"^proceed[.!]?$",
        r"^continue[.!]?$",
    )
    return any(re.search(pattern, normalized_message) for pattern in generic_patterns)


def normalize_refund_confirmation_command(message: str) -> str:
    """Normalize command text so formatting changes do not affect parsing."""
    normalized_message = message.casefold().replace("&", " and ")
    normalized_message = re.sub(r"[^a-z0-9]+", " ", normalized_message)
    return " ".join(normalized_message.split())


def build_refund_confirmation_command_guidance(
    active_refund_context: dict[str, Any],
) -> str:
    """Return the customer-facing canonical command guidance."""
    command = _confirmation_command_from_context(active_refund_context)
    if not command:
        return REFUND_WORKFLOW_CONFIRMATION_REQUIRED_RESPONSE
    return f"To continue, reply:\n\n{command}"


def build_refund_confirmation_command_offer(
    active_refund_context: dict[str, Any],
) -> str:
    """Return the post-eligibility canonical confirmation-command instruction."""
    command = _confirmation_command_from_context(active_refund_context)
    if not command:
        return ""

    return (
        "According to the refund policy, this purchase is eligible for a refund. "
        f"To continue, reply:\n\n{command}"
    )


def _confirmation_command_from_context(
    active_refund_context: dict[str, Any],
) -> str | None:
    """Return the expected command from state or deterministic config."""
    command = active_refund_context.get("confirmation_command")
    if not isinstance(command, str) or not command:
        command_config = refund_confirmation_command_for_purchase_type(
            active_refund_context.get("purchase_type")
        )
        command = command_config["command"] if command_config is not None else None
    return command if isinstance(command, str) and command else None


def _confirmation_steps_from_context(
    active_refund_context: dict[str, Any],
) -> list[str]:
    """Return command explanation steps from state or deterministic config."""
    steps = active_refund_context.get("confirmation_steps")
    if not isinstance(steps, list) or not steps:
        command_config = refund_confirmation_command_for_purchase_type(
            active_refund_context.get("purchase_type")
        )
        steps = list(command_config["steps"]) if command_config is not None else []
    return [step for step in steps if isinstance(step, str)]


def parse_refund_workflow_decline_intent(message: str) -> bool:
    """Return whether the message declines a pending refund action."""
    normalized_message = message.casefold().strip()
    decline_patterns = (
        r"^no[.!]?$",
        r"^no,?\s+thanks[.!]?$",
        r"^cancel[.!]?$",
        r"^never\s+mind[.!]?$",
        r"^do\s+not\s+(?:start|issue|process|prepare|complete)\s+(?:it|the\s+refund)[.!]?$",
    )
    return any(re.search(pattern, normalized_message) for pattern in decline_patterns)


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
            f"{product_name} is not eligible for a refund, so there is no refund "
            "process to continue."
        )

    if next_action == "generate_return_label":
        return (
            f"{product_name} is eligible for a refund, but I cannot start the "
            "return process yet."
        )

    if isinstance(next_action, str) and next_action:
        return (
            f"{product_name} is eligible for a refund, but I cannot continue the "
            "refund process yet."
        )

    return (
        f"{product_name} is eligible for a refund, but I cannot continue the "
        "refund process yet."
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
