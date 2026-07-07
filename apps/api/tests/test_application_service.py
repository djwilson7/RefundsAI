from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from refunds_ai_api.repositories.application import RepositoryConflictError
from refunds_ai_api.services.application import ApplicationService
from refunds_ai_api.services.refund_policy import RefundWorkflowError

EVALUATED_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
PURCHASE_ID = "40000000-0000-4000-8000-000000000001"


class DummyRepository:
    def __init__(self, raise_conflict: bool = False) -> None:
        self.raise_conflict = raise_conflict
        self.called_methods: list[str] = []

    def list_mock_users(self) -> list[dict[str, Any]]:
        self.called_methods.append("list_mock_users")
        return [{"id": "user-1"}]

    def get_user(self, user_id: str) -> dict[str, Any]:
        self.called_methods.append("get_user")
        return {"id": user_id}

    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        self.called_methods.append("list_user_purchases")
        return [{"id": PURCHASE_ID}]

    def get_purchase_detail(self, purchase_id: str) -> dict[str, Any]:
        self.called_methods.append("get_purchase_detail")
        return {"purchase_id": purchase_id}

    def get_purchase_for_refund_policy(self, purchase_id: str) -> dict[str, Any]:
        self.called_methods.append("get_purchase_for_refund_policy")
        # Return digital by default
        purchase = {
            "id": purchase_id,
            "purchase_type": "digital",
            "amount_cents": 1000,
            "purchased_at": EVALUATED_AT - timedelta(days=1),
            "status": "completed",
            "refund_requested_at": None,
            "refunded_at": None,
            "refund_amount_cents": None,
            "refund_outcome": None,
        }
        detail = {
            "code_redeemed": False,
            "code_redeemed_at": None,
            "code_invalidated_at": None,
            "refund_lock_reason": None,
            "refund_window_expires_at": EVALUATED_AT + timedelta(days=1),
        }
        return {"purchase": purchase, "detail": detail}

    def update_digital_refund_requested(self, purchase_id: str, requested_at: Any) -> None:
        self.called_methods.append("update_digital_refund_requested")
        if self.raise_conflict:
            raise RepositoryConflictError("conflict")

    def update_physical_refund_requested(self, purchase_id: str, requested_at: Any) -> None:
        self.called_methods.append("update_physical_refund_requested")
        if self.raise_conflict:
            raise RepositoryConflictError("conflict")

    def update_subscription_refund_requested(
        self,
        purchase_id: str,
        requested_at: Any,
        outcome: Any,
    ) -> None:
        self.called_methods.append("update_subscription_refund_requested")
        if self.raise_conflict:
            raise RepositoryConflictError("conflict")

    def update_refund_issued(
        self,
        purchase_id: str,
        issued_at: Any,
        amount: Any,
        outcome: Any,
    ) -> None:
        self.called_methods.append("update_refund_issued")
        if self.raise_conflict:
            raise RepositoryConflictError("conflict")

    def record_refund_confirmation(self, **kwargs: Any) -> dict[str, Any]:
        self.called_methods.append("record_refund_confirmation")
        if self.raise_conflict:
            raise RepositoryConflictError("conflict")
        return {"refund_confirmation_granted": True}

    def get_refund_confirmation(self, purchase_id: str, purchase_type: str) -> dict[str, Any]:
        self.called_methods.append("get_refund_confirmation")
        return {"refund_confirmation_granted": True}

    def consume_refund_confirmation(self, **kwargs: Any) -> dict[str, Any]:
        self.called_methods.append("consume_refund_confirmation")
        if self.raise_conflict:
            raise RepositoryConflictError("conflict")
        return {"refund_confirmation_granted": True}

    def update_digital_code_redeemed(self, purchase_id: str, redeemed_at: Any) -> None:
        self.called_methods.append("update_digital_code_redeemed")
        if self.raise_conflict:
            raise RepositoryConflictError("conflict")

    def update_physical_carrier_acceptance(self, purchase_id: str, accepted_at: Any) -> None:
        self.called_methods.append("update_physical_carrier_acceptance")
        if self.raise_conflict:
            raise RepositoryConflictError("conflict")

def test_application_service_simple_reads() -> None:
    repo = DummyRepository()
    service = ApplicationService(repo)

    assert service.list_mock_users() == [{"id": "user-1"}]
    assert repo.called_methods == ["list_mock_users"]

    repo.called_methods.clear()
    assert service.get_user("user-2") == {"id": "user-2"}
    assert repo.called_methods == ["get_user"]

    repo.called_methods.clear()
    assert service.get_purchase_detail(PURCHASE_ID) == {"purchase_id": PURCHASE_ID}
    assert repo.called_methods == ["get_purchase_detail"]

    repo.called_methods.clear()
    assert service.get_refund_confirmation(PURCHASE_ID, "digital") == {
        "refund_confirmation_granted": True
    }
    assert repo.called_methods == ["get_refund_confirmation"]


def test_application_service_conflict_digital_preparation() -> None:
    repo = DummyRepository(raise_conflict=True)
    service = ApplicationService(repo)

    with pytest.raises(RefundWorkflowError, match="Refund preparation is not allowed"):
        service.request_refund(PURCHASE_ID, requested_at=EVALUATED_AT)

def test_application_service_conflict_physical_preparation() -> None:
    repo = DummyRepository(raise_conflict=True)
    service = ApplicationService(repo)

    # Override get_purchase_for_refund_policy to return physical
    def get_physical_policy(purchase_id: str) -> dict[str, Any]:
        purchase = {
            "id": purchase_id,
            "purchase_type": "physical",
            "amount_cents": 1000,
            "purchased_at": EVALUATED_AT - timedelta(days=1),
            "status": "completed",
            "refund_requested_at": None,
            "refunded_at": None,
            "refund_amount_cents": None,
            "refund_outcome": None,
        }
        detail = {
            "return_status": "not_requested",
            "return_barcode_generated": False,
            "return_label_created_at": None,
            "return_requested_at": None,
            "accepted_by_carrier_at": None,
            "refund_window_expires_at": EVALUATED_AT + timedelta(days=1),
        }
        return {"purchase": purchase, "detail": detail}

    repo.get_purchase_for_refund_policy = get_physical_policy
    with pytest.raises(RefundWorkflowError, match="Refund preparation is not allowed"):
        service.request_refund(PURCHASE_ID, requested_at=EVALUATED_AT)

def test_application_service_conflict_subscription_preparation() -> None:
    repo = DummyRepository(raise_conflict=True)
    service = ApplicationService(repo)

    # Override get_purchase_for_refund_policy to return subscription
    def get_subscription_policy(purchase_id: str) -> dict[str, Any]:
        purchase = {
            "id": purchase_id,
            "purchase_type": "subscription",
            "amount_cents": 1000,
            "purchased_at": EVALUATED_AT - timedelta(days=1),
            "status": "subscribed",
            "refund_requested_at": None,
            "refunded_at": None,
            "refund_amount_cents": None,
            "refund_outcome": None,
        }
        detail = {
            "period_start": EVALUATED_AT - timedelta(hours=1),
            "period_end": EVALUATED_AT + timedelta(days=20),
            "cancelled_at": None,
            "service_ended_at": None,
            "auto_renew": True,
            "refund_proration_mode": "none",
            "full_refund_window_expires_at": EVALUATED_AT + timedelta(hours=24),
            "refund_window_expires_at": EVALUATED_AT + timedelta(days=20),
        }
        return {"purchase": purchase, "detail": detail}

    repo.get_purchase_for_refund_policy = get_subscription_policy
    with pytest.raises(RefundWorkflowError, match="Refund preparation is not allowed"):
        service.request_refund(PURCHASE_ID, requested_at=EVALUATED_AT)

def test_application_service_conflict_issuance() -> None:
    repo = DummyRepository(raise_conflict=True)
    service = ApplicationService(repo)

    # Override get_purchase_for_refund_policy to return a prepared digital purchase
    def get_prepared_policy(purchase_id: str) -> dict[str, Any]:
        purchase = {
            "id": purchase_id,
            "purchase_type": "digital",
            "amount_cents": 1000,
            "purchased_at": EVALUATED_AT - timedelta(days=1),
            "status": "refund_pending",
            "refund_requested_at": EVALUATED_AT - timedelta(hours=1),
            "refunded_at": None,
            "refund_amount_cents": None,
            "refund_outcome": None,
        }
        detail = {
            "code_redeemed": False,
            "code_redeemed_at": None,
            "code_invalidated_at": EVALUATED_AT - timedelta(hours=1),
            "refund_lock_reason": None,
            "refund_window_expires_at": EVALUATED_AT + timedelta(days=1),
        }
        return {"purchase": purchase, "detail": detail}

    repo.get_purchase_for_refund_policy = get_prepared_policy
    with pytest.raises(RefundWorkflowError, match="Refund issuance is not allowed"):
        service.issue_refund(PURCHASE_ID, issued_at=EVALUATED_AT)

def test_application_service_conflict_confirmation_recording() -> None:
    repo = DummyRepository(raise_conflict=True)
    service = ApplicationService(repo)

    with pytest.raises(RefundWorkflowError, match="Refund confirmation could not be persisted"):
        service.record_refund_confirmation(
            customer_id="user-1",
            purchase_id=PURCHASE_ID,
            purchase_type="digital",
            received_message="message",
            expected_command="command",
            granted_at=EVALUATED_AT,
            matched=True,
            source="test",
        )

def test_application_service_conflict_confirmation_consumption() -> None:
    repo = DummyRepository(raise_conflict=True)
    service = ApplicationService(repo)

    with pytest.raises(RefundWorkflowError, match="Refund confirmation is not valid"):
        service.consume_refund_confirmation(
            customer_id="user-1",
            purchase_id=PURCHASE_ID,
            purchase_type="digital",
            expected_command="command",
            consumed_at=EVALUATED_AT,
            consumed_by_action="request_refund",
        )

def test_application_service_conflict_code_redemption() -> None:
    repo = DummyRepository(raise_conflict=True)
    service = ApplicationService(repo)

    # To test code redemption, we must mock assert_can_redeem_code success.
    # Digital purchase with code not redeemed.
    def get_redeemable_policy(purchase_id: str) -> dict[str, Any]:
        purchase = {
            "id": purchase_id,
            "purchase_type": "digital",
            "amount_cents": 1000,
            "purchased_at": EVALUATED_AT - timedelta(days=1),
            "status": "completed",
            "refund_requested_at": None,
            "refunded_at": None,
            "refund_amount_cents": None,
            "refund_outcome": None,
        }
        detail = {
            "code_redeemed": False,
            "code_redeemed_at": None,
            "code_invalidated_at": None,
            "refund_lock_reason": None,
            "refund_window_expires_at": EVALUATED_AT + timedelta(days=1),
        }
        return {"purchase": purchase, "detail": detail}

    repo.get_purchase_for_refund_policy = get_redeemable_policy
    with pytest.raises(RefundWorkflowError, match="Code redemption is not allowed"):
        service.redeem_digital_code(PURCHASE_ID, redeemed_at=EVALUATED_AT)

def test_application_service_conflict_carrier_acceptance() -> None:
    repo = DummyRepository(raise_conflict=True)
    service = ApplicationService(repo)

    # To test carrier acceptance, return status must be 'requested'.
    def get_carrier_acceptance_policy(purchase_id: str) -> dict[str, Any]:
        purchase = {
            "id": purchase_id,
            "purchase_type": "physical",
            "amount_cents": 1000,
            "purchased_at": EVALUATED_AT - timedelta(days=1),
            "status": "refund_pending",
            "refund_requested_at": EVALUATED_AT - timedelta(hours=1),
            "refunded_at": None,
            "refund_amount_cents": None,
            "refund_outcome": None,
        }
        detail = {
            "return_status": "requested",
            "return_barcode_generated": True,
            "return_label_created_at": EVALUATED_AT - timedelta(hours=1),
            "return_requested_at": EVALUATED_AT - timedelta(hours=1),
            "accepted_by_carrier_at": None,
            "refund_window_expires_at": EVALUATED_AT + timedelta(days=1),
        }
        return {"purchase": purchase, "detail": detail}

    repo.get_purchase_for_refund_policy = get_carrier_acceptance_policy
    with pytest.raises(RefundWorkflowError, match="Carrier acceptance confirmation is not allowed"):
        service.confirm_carrier_acceptance(PURCHASE_ID, accepted_at=EVALUATED_AT)
