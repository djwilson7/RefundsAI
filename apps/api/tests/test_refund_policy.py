from datetime import UTC, datetime, timedelta

import pytest

from refunds_ai_api.services.refund_policy import (
    RefundWorkflowError,
    assert_can_confirm_carrier_acceptance,
    assert_can_issue_funds,
    assert_can_prepare_refund,
    assert_can_redeem_code,
    calculate_prorated_amount_cents,
    evaluate_refund_workflow,
)

PURCHASE_ID = "40000000-0000-4000-8000-000000000001"
EVALUATED_AT = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


def build_purchase(
    purchase_type: str,
    status: str = "completed",
    amount_cents: int = 12000,
    refund_requested_at: datetime | None = None,
    refunded_at: datetime | None = None,
    refund_amount_cents: int | None = None,
    refund_outcome: str | None = None,
) -> dict:
    return {
        "id": PURCHASE_ID,
        "purchase_type": purchase_type,
        "amount_cents": amount_cents,
        "purchased_at": datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
        "status": status,
        "refund_requested_at": refund_requested_at,
        "refunded_at": refunded_at,
        "refund_amount_cents": refund_amount_cents,
        "refund_outcome": refund_outcome,
    }


def build_physical_detail(
    return_status: str = "not_requested",
    return_barcode_generated: bool = False,
    return_label_created_at: datetime | None = None,
    return_requested_at: datetime | None = None,
    accepted_by_carrier_at: datetime | None = None,
    refund_window_expires_at: datetime | None = None,
) -> dict:
    return {
        "return_status": return_status,
        "return_barcode_generated": return_barcode_generated,
        "return_label_created_at": return_label_created_at,
        "return_requested_at": return_requested_at,
        "accepted_by_carrier_at": accepted_by_carrier_at,
        "refund_window_expires_at": refund_window_expires_at or EVALUATED_AT + timedelta(days=1),
    }


def build_digital_detail(
    code_redeemed: bool = False,
    code_redeemed_at: datetime | None = None,
    code_invalidated_at: datetime | None = None,
    refund_window_expires_at: datetime | None = None,
) -> dict:
    return {
        "code_redeemed": code_redeemed,
        "code_redeemed_at": code_redeemed_at,
        "code_invalidated_at": code_invalidated_at,
        "refund_lock_reason": "code_redeemed" if code_redeemed else None,
        "refund_window_expires_at": refund_window_expires_at or EVALUATED_AT + timedelta(days=1),
    }


def test_physical_refund_workflow_can_enter_and_prepare_inside_window() -> None:
    result = evaluate_refund_workflow(
        build_purchase("physical"),
        build_physical_detail(),
        EVALUATED_AT,
    )

    assert result.can_enter_refund_workflow is True
    assert result.can_prepare_refund is True
    assert result.can_issue_funds is False
    assert result.refund_stage == "eligible"
    assert result.required_action == "generate_return_label"


def test_physical_refund_requires_carrier_acceptance_before_issuance() -> None:
    result = evaluate_refund_workflow(
        build_purchase("physical", status="refund_pending"),
        build_physical_detail(
            return_status="requested",
            return_barcode_generated=True,
            return_label_created_at=EVALUATED_AT,
            return_requested_at=EVALUATED_AT,
        ),
        EVALUATED_AT,
    )

    assert result.can_prepare_refund is False
    assert result.can_issue_funds is False
    assert result.refund_stage == "prepared"
    assert result.required_action == "await_carrier_acceptance"
    assert result.reasons == ["return_not_accepted_by_carrier"]


def test_physical_refund_can_issue_after_carrier_acceptance() -> None:
    result = evaluate_refund_workflow(
        build_purchase("physical", status="refund_pending"),
        build_physical_detail(
            return_status="accepted_by_carrier",
            return_barcode_generated=True,
            return_label_created_at=EVALUATED_AT,
            return_requested_at=EVALUATED_AT,
            accepted_by_carrier_at=EVALUATED_AT,
        ),
        EVALUATED_AT,
    )

    assert result.can_issue_funds is True
    assert result.required_action == "issue_funds"
    assert result.refundable_amount_cents == 12000
    assert result.refund_outcome == "full"


def test_physical_refund_rejects_rejected_return_state() -> None:
    result = evaluate_refund_workflow(
        build_purchase("physical"),
        build_physical_detail(return_status="rejected"),
        EVALUATED_AT,
    )

    assert result.can_enter_refund_workflow is False
    assert result.can_prepare_refund is False
    assert "return_status_rejected" in result.reasons


def test_digital_refund_can_prepare_by_invalidating_unredeemed_code() -> None:
    result = evaluate_refund_workflow(
        build_purchase("digital", amount_cents=4500),
        build_digital_detail(),
        EVALUATED_AT,
    )

    assert result.can_enter_refund_workflow is True
    assert result.can_prepare_refund is True
    assert result.can_issue_funds is False
    assert result.required_action == "invalidate_code"


def test_digital_refund_can_issue_after_preparation_invalidates_code() -> None:
    result = evaluate_refund_workflow(
        build_purchase("digital", status="refund_pending", amount_cents=4500),
        build_digital_detail(code_invalidated_at=EVALUATED_AT),
        EVALUATED_AT,
    )

    assert result.can_prepare_refund is False
    assert result.can_issue_funds is True
    assert result.required_action == "issue_funds"
    assert result.refundable_amount_cents == 4500


def test_digital_refund_rejects_redeemed_code() -> None:
    result = evaluate_refund_workflow(
        build_purchase("digital", status="redeemed"),
        build_digital_detail(code_redeemed=True, code_redeemed_at=EVALUATED_AT),
        EVALUATED_AT,
    )

    assert result.can_enter_refund_workflow is False
    assert result.can_prepare_refund is False
    assert "purchase_status_redeemed" in result.reasons
    assert "code_redeemed" in result.reasons


def test_refunded_purchase_reports_persisted_issued_facts() -> None:
    result = evaluate_refund_workflow(
        build_purchase(
            "digital",
            status="refunded",
            amount_cents=4500,
            refund_requested_at=EVALUATED_AT - timedelta(hours=2),
            refunded_at=EVALUATED_AT - timedelta(hours=1),
            refund_amount_cents=4500,
            refund_outcome="full",
        ),
        build_digital_detail(code_invalidated_at=EVALUATED_AT - timedelta(hours=2)),
        EVALUATED_AT,
    )

    assert result.refund_stage == "issued"
    assert result.can_issue_funds is False
    assert result.refundable_amount_cents == 4500
    assert result.refund_outcome == "full"
    assert result.reasons == ["purchase_status_refunded"]
    assert result.policy_facts["refunded_at"] == EVALUATED_AT - timedelta(hours=1)
    assert result.policy_facts["refund_amount_cents"] == 4500
    assert result.policy_facts["refund_outcome"] == "full"


def test_refund_rejects_expired_window_before_preparation() -> None:
    result = evaluate_refund_workflow(
        build_purchase("digital"),
        build_digital_detail(refund_window_expires_at=EVALUATED_AT - timedelta(seconds=1)),
        EVALUATED_AT,
    )

    assert result.can_enter_refund_workflow is False
    assert result.can_prepare_refund is False
    assert result.reasons == ["refund_window_expired"]


def test_subscription_refund_can_prepare_full_refund_inside_initial_window() -> None:
    period_start = EVALUATED_AT - timedelta(hours=24)
    detail = build_subscription_detail(
        period_start=period_start,
        period_end=period_start + timedelta(days=30),
        full_refund_window_expires_at=period_start + timedelta(hours=48),
    )

    result = evaluate_refund_workflow(
        build_purchase("subscription", status="subscribed", amount_cents=3000),
        detail,
        EVALUATED_AT,
    )

    assert result.can_prepare_refund is True
    assert result.required_action == "cancel_subscription"
    assert result.refund_outcome == "full"


def test_subscription_refund_can_issue_after_preparation() -> None:
    period_start = EVALUATED_AT - timedelta(days=10)
    detail = build_subscription_detail(
        period_start=period_start,
        period_end=EVALUATED_AT + timedelta(days=20),
        full_refund_window_expires_at=period_start + timedelta(hours=48),
        cancelled_at=EVALUATED_AT,
        service_ended_at=EVALUATED_AT,
        auto_renew=False,
        refund_proration_mode="prorated",
    )

    result = evaluate_refund_workflow(
        build_purchase("subscription", status="refund_pending", amount_cents=3000),
        detail,
        EVALUATED_AT,
    )

    assert result.can_issue_funds is True
    assert result.refund_outcome == "prorated"
    assert result.refundable_amount_cents == 2000


def test_subscription_refund_rejects_inactive_period() -> None:
    period_start = EVALUATED_AT - timedelta(days=40)
    detail = build_subscription_detail(
        period_start=period_start,
        period_end=EVALUATED_AT - timedelta(days=10),
        full_refund_window_expires_at=period_start + timedelta(hours=48),
    )

    result = evaluate_refund_workflow(
        build_purchase("subscription", status="subscribed"),
        detail,
        EVALUATED_AT,
    )

    assert result.can_prepare_refund is False
    assert "subscription_period_inactive" in result.reasons


def test_assert_can_prepare_refund_raises_for_blocked_purchase() -> None:
    with pytest.raises(RefundWorkflowError, match="Refund preparation is not allowed"):
        assert_can_prepare_refund(
            build_purchase("digital", status="redeemed"),
            build_digital_detail(code_redeemed=True, code_redeemed_at=EVALUATED_AT),
            EVALUATED_AT,
        )


def test_assert_can_issue_funds_raises_before_preparation() -> None:
    with pytest.raises(RefundWorkflowError, match="Refund issuance is not allowed"):
        assert_can_issue_funds(
            build_purchase("digital"),
            build_digital_detail(),
            EVALUATED_AT,
        )


def test_code_redemption_blocks_invalidated_refund_state() -> None:
    with pytest.raises(RefundWorkflowError, match="code_invalidated"):
        assert_can_redeem_code(
            build_purchase("digital", status="refund_pending"),
            build_digital_detail(code_invalidated_at=EVALUATED_AT),
        )


def test_carrier_acceptance_requires_physical_requested_return() -> None:
    with pytest.raises(RefundWorkflowError, match="return_status_not_requested"):
        assert_can_confirm_carrier_acceptance(
            build_purchase("physical", status="refund_pending"),
            build_physical_detail(return_status="not_requested"),
        )


def test_calculate_prorated_amount_cents_uses_remaining_period_time() -> None:
    amount = calculate_prorated_amount_cents(
        amount_cents=3000,
        period_start=EVALUATED_AT - timedelta(days=10),
        period_end=EVALUATED_AT + timedelta(days=20),
        evaluated_at=EVALUATED_AT,
    )

    assert amount == 2000


def build_subscription_detail(
    period_start: datetime,
    period_end: datetime,
    full_refund_window_expires_at: datetime,
    cancelled_at: datetime | None = None,
    service_ended_at: datetime | None = None,
    auto_renew: bool = True,
    refund_proration_mode: str = "none",
) -> dict:
    return {
        "period_start": period_start,
        "period_end": period_end,
        "cancelled_at": cancelled_at,
        "service_ended_at": service_ended_at,
        "auto_renew": auto_renew,
        "refund_proration_mode": refund_proration_mode,
        "full_refund_window_expires_at": full_refund_window_expires_at,
        "refund_window_expires_at": period_end,
    }
