"""Frontend-facing business services for users and purchases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from refunds_ai_api.repositories.application import RepositoryConflictError
from refunds_ai_api.services.refund_policy import (
    RefundWorkflowError,
    assert_can_confirm_carrier_acceptance,
    assert_can_issue_funds,
    assert_can_prepare_refund,
    assert_can_redeem_code,
    evaluate_refund_workflow,
)


class ApplicationRepositoryProtocol(Protocol):
    """Repository operations required by the application service."""

    def list_mock_users(self) -> list[dict[str, Any]]:
        """Return selectable mock users."""
        ...

    def get_user(self, user_id: str) -> dict[str, Any]:
        """Return one user."""
        ...

    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        """Return purchase rows for one user."""
        ...

    def get_purchase_detail(self, purchase_id: str) -> dict[str, Any]:
        """Return the matching detail row for a purchase."""
        ...

    def get_purchase_for_refund_policy(self, purchase_id: str) -> dict[str, Any]:
        """Return purchase and detail facts for refund policy evaluation."""
        ...

    def update_physical_refund_requested(self, purchase_id: str, requested_at: datetime) -> None:
        """Prepare a physical purchase for refund."""
        ...

    def update_digital_refund_requested(self, purchase_id: str, requested_at: datetime) -> None:
        """Prepare a digital purchase for refund."""
        ...

    def update_subscription_refund_requested(
        self,
        purchase_id: str,
        requested_at: datetime,
        refund_proration_mode: str,
    ) -> None:
        """Prepare a subscription purchase for refund."""
        ...

    def update_refund_issued(
        self,
        purchase_id: str,
        issued_at: datetime,
        refund_amount_cents: int,
        refund_outcome: str,
    ) -> None:
        """Mark a refund as issued."""
        ...

    def update_digital_code_redeemed(self, purchase_id: str, redeemed_at: datetime) -> None:
        """Redeem a digital issued code."""
        ...

    def update_physical_carrier_acceptance(self, purchase_id: str, accepted_at: datetime) -> None:
        """Confirm carrier acceptance for a physical return."""
        ...


@dataclass(frozen=True)
class ApplicationService:
    """Expose frontend-ready read models and guarded workflow mutations."""

    repository: ApplicationRepositoryProtocol

    def list_mock_users(self) -> list[dict[str, Any]]:
        """Return selectable mock users."""
        return self.repository.list_mock_users()

    def get_user(self, user_id: str) -> dict[str, Any]:
        """Return one selected user with role information."""
        return self.repository.get_user(user_id)

    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        """Return purchase history with detail URLs for frontend navigation."""
        purchases = self.repository.list_user_purchases(user_id)

        return [
            {
                **purchase,
                "details_url": f"/api/purchases/{purchase['id']}/details",
            }
            for purchase in purchases
        ]

    def get_purchase_detail(self, purchase_id: str) -> dict[str, Any]:
        """Return type-specific purchase detail data without exposing table routing."""
        return self.repository.get_purchase_detail(purchase_id)

    def get_refund_workflow(
        self,
        purchase_id: str,
        evaluated_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Return deterministic refund workflow state for one purchase."""
        policy_input = self.repository.get_purchase_for_refund_policy(purchase_id)
        decision = evaluate_refund_workflow(
            purchase=policy_input["purchase"],
            detail=policy_input["detail"],
            evaluated_at=evaluated_at or datetime.now(UTC),
        )
        return serialize_workflow_decision(decision)

    def get_refund_eligibility(
        self,
        purchase_id: str,
        evaluated_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Return refund workflow state with legacy eligibility aliases."""
        decision = self.get_refund_workflow(purchase_id, evaluated_at)
        return {
            **decision,
            "can_request_refund": decision["can_enter_refund_workflow"],
            "can_issue_refund": decision["can_issue_funds"],
        }

    def request_refund(
        self,
        purchase_id: str,
        requested_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Prepare a purchase for refund without issuing funds."""
        effective_time = requested_at or datetime.now(UTC)
        policy_input = self.repository.get_purchase_for_refund_policy(purchase_id)
        decision = assert_can_prepare_refund(
            policy_input["purchase"],
            policy_input["detail"],
            effective_time,
        )

        if decision.purchase_type == "physical":
            try:
                self.repository.update_physical_refund_requested(purchase_id, effective_time)
            except RepositoryConflictError as exc:
                raise RefundWorkflowError(
                    "Refund preparation is not allowed: stale_or_duplicate_mutation."
                ) from exc
        elif decision.purchase_type == "digital":
            try:
                self.repository.update_digital_refund_requested(purchase_id, effective_time)
            except RepositoryConflictError as exc:
                raise RefundWorkflowError(
                    "Refund preparation is not allowed: stale_or_duplicate_mutation."
                ) from exc
        elif decision.purchase_type == "subscription":
            try:
                self.repository.update_subscription_refund_requested(
                    purchase_id,
                    effective_time,
                    decision.refund_outcome,
                )
            except RepositoryConflictError as exc:
                raise RefundWorkflowError(
                    "Refund preparation is not allowed: stale_or_duplicate_mutation."
                ) from exc

        return self.get_refund_workflow(purchase_id, effective_time)

    def issue_refund(
        self,
        purchase_id: str,
        issued_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Issue mock refund funds for a prepared purchase."""
        effective_time = issued_at or datetime.now(UTC)
        policy_input = self.repository.get_purchase_for_refund_policy(purchase_id)
        decision = assert_can_issue_funds(
            policy_input["purchase"],
            policy_input["detail"],
            effective_time,
        )
        try:
            self.repository.update_refund_issued(
                purchase_id,
                effective_time,
                decision.refundable_amount_cents,
                decision.refund_outcome,
            )
        except RepositoryConflictError as exc:
            raise RefundWorkflowError(
                "Refund issuance is not allowed: stale_or_duplicate_mutation."
            ) from exc
        return serialize_issued_workflow_decision(decision, effective_time)

    def redeem_digital_code(
        self,
        purchase_id: str,
        redeemed_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Redeem a digital issued code when no refund state blocks redemption."""
        effective_time = redeemed_at or datetime.now(UTC)
        policy_input = self.repository.get_purchase_for_refund_policy(purchase_id)
        assert_can_redeem_code(policy_input["purchase"], policy_input["detail"])
        try:
            self.repository.update_digital_code_redeemed(purchase_id, effective_time)
        except RepositoryConflictError as exc:
            raise RefundWorkflowError(
                "Code redemption is not allowed: stale_or_duplicate_mutation."
            ) from exc
        return self.repository.get_purchase_detail(purchase_id)

    def confirm_carrier_acceptance(
        self,
        purchase_id: str,
        accepted_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Confirm that a physical return package was accepted by the carrier."""
        effective_time = accepted_at or datetime.now(UTC)
        policy_input = self.repository.get_purchase_for_refund_policy(purchase_id)
        assert_can_confirm_carrier_acceptance(policy_input["purchase"], policy_input["detail"])
        try:
            self.repository.update_physical_carrier_acceptance(purchase_id, effective_time)
        except RepositoryConflictError as exc:
            raise RefundWorkflowError(
                "Carrier acceptance confirmation is not allowed: stale_or_duplicate_mutation."
            ) from exc
        return self.get_refund_workflow(purchase_id, effective_time)


def serialize_workflow_decision(decision) -> dict[str, Any]:
    """Serialize a refund workflow decision for API responses."""
    return {
        "purchase_id": decision.purchase_id,
        "purchase_type": decision.purchase_type,
        "can_enter_refund_workflow": decision.can_enter_refund_workflow,
        "can_prepare_refund": decision.can_prepare_refund,
        "can_issue_funds": decision.can_issue_funds,
        "refund_stage": decision.refund_stage,
        "required_action": decision.required_action,
        "refundable_amount_cents": decision.refundable_amount_cents,
        "refund_outcome": decision.refund_outcome,
        "reasons": decision.reasons,
        "policy_facts": decision.policy_facts,
    }


def serialize_issued_workflow_decision(decision, issued_at: datetime) -> dict[str, Any]:
    """Serialize the pre-issue decision as an issued workflow without recomputing funds."""
    return {
        "purchase_id": decision.purchase_id,
        "purchase_type": decision.purchase_type,
        "can_enter_refund_workflow": False,
        "can_prepare_refund": False,
        "can_issue_funds": False,
        "refund_stage": "issued",
        "required_action": "none",
        "refundable_amount_cents": decision.refundable_amount_cents,
        "refund_outcome": decision.refund_outcome,
        "reasons": ["purchase_status_refunded"],
        "policy_facts": {
            **decision.policy_facts,
            "purchase_status": "refunded",
            "refunded_at": issued_at,
            "refund_amount_cents": decision.refundable_amount_cents,
            "refund_outcome": decision.refund_outcome,
        },
    }
