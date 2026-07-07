from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from refunds_ai_api.services.refund_confirmation import (
    authorize_persisted_refund_confirmation,
    validate_refund_confirmation,
)

from .fakes import CUSTOMER_ID, PURCHASE_ID, MutableRefundApplicationService

DIGITAL_CONFIRMATION_COMMAND = "Confirm invalidate code and issue refund"


class StrictCustomerRefundApplicationService(MutableRefundApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        if user_id != CUSTOMER_ID:
            return []
        return super().list_user_purchases(user_id)


class UuidPurchaseIdRefundApplicationService(MutableRefundApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        return [
            {
                **purchase,
                "id": UUID(str(purchase["id"])),
            }
            for purchase in super().list_user_purchases(user_id)
        ]


def test_refund_confirmation_validator_grants_and_persists_exact_message() -> None:
    application_service = MutableRefundApplicationService()
    granted_at = datetime(2026, 7, 3, 14, 30, tzinfo=UTC)

    result = validate_refund_confirmation(
        application_service=application_service,
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        purchase_type="digital",
        user_message=f"{DIGITAL_CONFIRMATION_COMMAND}.",
        expected_confirmation_command=DIGITAL_CONFIRMATION_COMMAND,
        current_refund_stage="eligible",
        required_action="invalidate_digital_entitlement",
        granted_at=granted_at,
    )

    confirmation = application_service.get_refund_confirmation(PURCHASE_ID, "digital")
    assert result.confirmed is True
    assert result.matched is True
    assert result.confirmation_granted_at == granted_at
    assert confirmation["refund_confirmation_granted"] is True
    assert confirmation["refund_confirmation_message"] == (
        f"{DIGITAL_CONFIRMATION_COMMAND}."
    )
    assert confirmation["refund_confirmation_expected_command"] == (
        DIGITAL_CONFIRMATION_COMMAND
    )
    assert confirmation["refund_confirmation_granted_at"] == granted_at
    assert confirmation["refund_confirmation_customer_id"] == CUSTOMER_ID
    assert confirmation["refund_confirmation_purchase_id"] == PURCHASE_ID


def test_refund_confirmation_validator_accepts_database_uuid_purchase_ids() -> None:
    application_service = UuidPurchaseIdRefundApplicationService()

    result = validate_refund_confirmation(
        application_service=application_service,
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        purchase_type="digital",
        user_message=DIGITAL_CONFIRMATION_COMMAND,
        expected_confirmation_command=DIGITAL_CONFIRMATION_COMMAND,
        current_refund_stage="eligible",
        required_action="invalidate_digital_entitlement",
    )

    assert result.confirmed is True
    assert result.denial_reason is None


def test_refund_confirmation_validator_rejects_wrong_command() -> None:
    application_service = MutableRefundApplicationService()

    result = validate_refund_confirmation(
        application_service=application_service,
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        purchase_type="digital",
        user_message="Yes, go ahead.",
        expected_confirmation_command=DIGITAL_CONFIRMATION_COMMAND,
        current_refund_stage="eligible",
        required_action="invalidate_digital_entitlement",
    )

    confirmation = application_service.get_refund_confirmation(PURCHASE_ID, "digital")
    assert result.confirmed is False
    assert result.denial_reason == "confirmation_command_mismatch"
    assert confirmation["refund_confirmation_granted"] is False


def test_refund_confirmation_validator_rejects_wrong_customer() -> None:
    application_service = StrictCustomerRefundApplicationService()

    result = validate_refund_confirmation(
        application_service=application_service,
        customer_id="20000000-0000-4000-8000-000000009999",
        purchase_id=PURCHASE_ID,
        purchase_type="digital",
        user_message=DIGITAL_CONFIRMATION_COMMAND,
        expected_confirmation_command=DIGITAL_CONFIRMATION_COMMAND,
        current_refund_stage="eligible",
        required_action="invalidate_digital_entitlement",
    )

    assert result.confirmed is False
    assert result.denial_reason == "purchase_not_owned_by_customer"
    assert (
        application_service.get_refund_confirmation(PURCHASE_ID, "digital")[
            "refund_confirmation_granted"
        ]
        is False
    )


def test_refund_confirmation_validator_rejects_wrong_purchase_type_command() -> None:
    application_service = MutableRefundApplicationService()

    result = validate_refund_confirmation(
        application_service=application_service,
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        purchase_type="digital",
        user_message="Confirm cancel and issue refund",
        expected_confirmation_command="Confirm cancel and issue refund",
        current_refund_stage="eligible",
        required_action="invalidate_digital_entitlement",
    )

    assert result.confirmed is False
    assert result.denial_reason == "stale_or_wrong_expected_command"


def test_refund_confirmation_validator_rejects_stale_refund_stage() -> None:
    application_service = MutableRefundApplicationService()

    result = validate_refund_confirmation(
        application_service=application_service,
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        purchase_type="digital",
        user_message=DIGITAL_CONFIRMATION_COMMAND,
        expected_confirmation_command=DIGITAL_CONFIRMATION_COMMAND,
        current_refund_stage="prepared",
        required_action="invalidate_digital_entitlement",
    )

    assert result.confirmed is False
    assert result.denial_reason == "stale_refund_stage"


def test_refund_confirmation_validator_rejects_terminal_issued_state() -> None:
    application_service = MutableRefundApplicationService()
    application_service.issued_purchase_ids.add(PURCHASE_ID)

    result = validate_refund_confirmation(
        application_service=application_service,
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        purchase_type="digital",
        user_message=DIGITAL_CONFIRMATION_COMMAND,
        expected_confirmation_command=DIGITAL_CONFIRMATION_COMMAND,
        current_refund_stage="issued",
        required_action="none",
    )

    assert result.confirmed is False
    assert result.denial_reason == "refund_stage_not_confirmable"


def test_persisted_refund_authorization_denies_without_validator_grant() -> None:
    application_service = MutableRefundApplicationService()

    authorization = authorize_persisted_refund_confirmation(
        application_service=application_service,
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        purchase_type="digital",
        expected_confirmation_command=DIGITAL_CONFIRMATION_COMMAND,
        action="request_refund",
        current_workflow=application_service.get_refund_workflow(PURCHASE_ID),
    )

    assert authorization.authorized is False
    assert authorization.denial_reason == "confirmation_not_granted"
