"""Deterministic refund confirmation validation and authorization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from refunds_ai_api.services.refund_policy import RefundWorkflowError

REFUND_CONFIRMATION_SOURCE = "chat_confirmation_validator"

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


@dataclass(frozen=True)
class RefundConfirmationResult:
    """Structured result for deterministic refund confirmation validation."""

    confirmed: bool
    purchase_id: str
    purchase_type: str
    expected_command: str
    received_message: str
    matched: bool
    confirmation_granted_at: datetime | None
    denial_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a stable dictionary shape for logs and tests."""
        return {
            "confirmed": self.confirmed,
            "purchase_id": self.purchase_id,
            "purchase_type": self.purchase_type,
            "expected_command": self.expected_command,
            "received_message": self.received_message,
            "matched": self.matched,
            "confirmation_granted_at": self.confirmation_granted_at,
            "denial_reason": self.denial_reason,
        }


@dataclass(frozen=True)
class RefundConfirmationAuthorization:
    """Structured result for persisted confirmation authorization checks."""

    authorized: bool
    confirmation: dict[str, Any] | None
    denial_reason: str | None = None


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


def normalize_refund_confirmation_command(message: str) -> str:
    """Normalize command text so formatting changes do not affect parsing."""
    normalized_message = message.casefold().replace("&", " and ")
    normalized_message = re.sub(r"[^a-z0-9]+", " ", normalized_message)
    return " ".join(normalized_message.split())


def validate_refund_confirmation(
    *,
    application_service: Any,
    customer_id: str | None,
    purchase_id: str,
    purchase_type: str,
    user_message: str,
    expected_confirmation_command: str,
    current_refund_stage: str | None,
    required_action: str | None,
    granted_at: datetime | None = None,
) -> RefundConfirmationResult:
    """Validate and persist explicit refund consent for one purchase."""
    matched = messages_match_expected_command(
        user_message,
        expected_confirmation_command,
    )
    denial_reason = _confirmation_denial_reason(
        application_service=application_service,
        customer_id=customer_id,
        purchase_id=purchase_id,
        purchase_type=purchase_type,
        expected_confirmation_command=expected_confirmation_command,
        current_refund_stage=current_refund_stage,
        required_action=required_action,
        matched=matched,
    )
    if denial_reason is not None:
        return RefundConfirmationResult(
            confirmed=False,
            purchase_id=purchase_id,
            purchase_type=purchase_type,
            expected_command=expected_confirmation_command,
            received_message=user_message,
            matched=matched,
            confirmation_granted_at=None,
            denial_reason=denial_reason,
        )

    effective_time = granted_at or datetime.now(UTC)
    try:
        application_service.record_refund_confirmation(
            customer_id=customer_id,
            purchase_id=purchase_id,
            purchase_type=purchase_type,
            received_message=user_message,
            expected_command=expected_confirmation_command,
            granted_at=effective_time,
            matched=matched,
            source=REFUND_CONFIRMATION_SOURCE,
        )
    except RefundWorkflowError:
        return RefundConfirmationResult(
            confirmed=False,
            purchase_id=purchase_id,
            purchase_type=purchase_type,
            expected_command=expected_confirmation_command,
            received_message=user_message,
            matched=matched,
            confirmation_granted_at=None,
            denial_reason="confirmation_persistence_failed",
        )
    return RefundConfirmationResult(
        confirmed=True,
        purchase_id=purchase_id,
        purchase_type=purchase_type,
        expected_command=expected_confirmation_command,
        received_message=user_message,
        matched=matched,
        confirmation_granted_at=effective_time,
    )


def messages_match_expected_command(
    user_message: str,
    expected_confirmation_command: str,
) -> bool:
    """Return whether user text matches the expected canonical command."""
    return normalize_refund_confirmation_command(
        user_message
    ) == normalize_refund_confirmation_command(expected_confirmation_command)


def authorize_persisted_refund_confirmation(
    *,
    application_service: Any,
    customer_id: str | None,
    purchase_id: str,
    purchase_type: str,
    expected_confirmation_command: str,
    action: str,
    current_workflow: dict[str, Any],
) -> RefundConfirmationAuthorization:
    """Authorize one atomic mutation from persisted confirmation facts."""
    if application_service is None or customer_id is None:
        return RefundConfirmationAuthorization(False, None, "customer_context_required")

    confirmation = application_service.get_refund_confirmation(purchase_id, purchase_type)
    denial_reason = _authorization_denial_reason(
        customer_id=customer_id,
        purchase_id=purchase_id,
        purchase_type=purchase_type,
        expected_confirmation_command=expected_confirmation_command,
        action=action,
        current_workflow=current_workflow,
        confirmation=confirmation,
    )
    return RefundConfirmationAuthorization(
        authorized=denial_reason is None,
        confirmation=confirmation,
        denial_reason=denial_reason,
    )


def _confirmation_denial_reason(
    *,
    application_service: Any,
    customer_id: str | None,
    purchase_id: str,
    purchase_type: str,
    expected_confirmation_command: str,
    current_refund_stage: str | None,
    required_action: str | None,
    matched: bool,
) -> str | None:
    """Return why confirmation is not valid, or None when valid."""
    if application_service is None or customer_id is None:
        return "customer_context_required"

    command_config = refund_confirmation_command_for_purchase_type(purchase_type)
    if command_config is None:
        return "unsupported_purchase_type"
    if expected_confirmation_command != command_config["command"]:
        return "stale_or_wrong_expected_command"
    if not matched:
        return "confirmation_command_mismatch"

    resolved_purchase = _resolve_customer_purchase(
        application_service,
        customer_id,
        purchase_id,
    )
    if resolved_purchase is None:
        return "purchase_not_owned_by_customer"
    if resolved_purchase.get("purchase_type") != purchase_type:
        return "purchase_type_mismatch"

    current_workflow = application_service.get_refund_workflow(purchase_id)
    workflow_stage = current_workflow.get("refund_stage")
    if workflow_stage not in {"eligible", "prepared"}:
        return "refund_stage_not_confirmable"
    if current_refund_stage not in {
        None,
        workflow_stage,
        "eligibility_confirmed",
        "awaiting_return_label",
    }:
        return "stale_refund_stage"
    if workflow_stage == "eligible" and current_workflow.get("can_prepare_refund") is not True:
        return "refund_preparation_not_allowed"
    if workflow_stage == "prepared" and current_workflow.get("can_issue_funds") is not True:
        return "refund_issuance_not_allowed"
    if required_action not in {None, current_workflow.get("required_action")}:
        return "stale_required_action"

    return None


def _authorization_denial_reason(
    *,
    customer_id: str,
    purchase_id: str,
    purchase_type: str,
    expected_confirmation_command: str,
    action: str,
    current_workflow: dict[str, Any],
    confirmation: dict[str, Any],
) -> str | None:
    """Return why persisted confirmation cannot authorize a mutation."""
    if confirmation.get("refund_confirmation_granted") is not True:
        return "confirmation_not_granted"
    if confirmation.get("refund_confirmation_matched") is not True:
        return "confirmation_not_matched"
    if str(confirmation.get("refund_confirmation_purchase_id")) != purchase_id:
        return "confirmation_purchase_mismatch"
    if str(confirmation.get("refund_confirmation_customer_id")) != customer_id:
        return "confirmation_customer_mismatch"
    if confirmation.get("refund_confirmation_expected_command") != expected_confirmation_command:
        return "confirmation_expected_command_mismatch"
    if confirmation.get("refund_confirmation_consumed_at") is not None:
        return "confirmation_already_consumed"
    if confirmation.get("refund_confirmation_consumed_by_action") is not None:
        return "confirmation_already_consumed"

    command_config = refund_confirmation_command_for_purchase_type(purchase_type)
    if command_config is None or command_config["command"] != expected_confirmation_command:
        return "confirmation_command_not_valid_for_purchase_type"

    stage = current_workflow.get("refund_stage")
    if stage in {"issued", "blocked"}:
        return "refund_stage_not_mutable"
    if action == "request_refund" and current_workflow.get("can_prepare_refund") is not True:
        return "refund_preparation_not_allowed"
    if action == "issue_refund" and current_workflow.get("can_issue_funds") is not True:
        return "refund_issuance_not_allowed"
    return None


def _resolve_customer_purchase(
    application_service: Any,
    customer_id: str,
    purchase_id: str,
) -> dict[str, Any] | None:
    """Return the customer's purchase row when the purchase belongs to them."""
    for purchase in application_service.list_user_purchases(customer_id):
        if str(purchase.get("id")) == purchase_id:
            return purchase
    return None
