"""Deterministic refund workflow policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

PurchaseType = Literal["physical", "digital", "subscription"]
RefundStage = Literal["blocked", "eligible", "prepared", "issued"]
RequiredAction = Literal[
    "none",
    "request_refund",
    "invalidate_code",
    "generate_return_label",
    "cancel_subscription",
    "await_carrier_acceptance",
    "issue_funds",
]
RefundOutcome = Literal["none", "full", "prorated"]

WORKFLOW_ENTRY_STATUSES = {"completed", "subscribed"}
TERMINAL_OR_BLOCKING_STATUSES = {"redeemed", "refunded", "cancelled"}
PREPARED_STATUS = "refund_pending"
PHYSICAL_BLOCKING_RETURN_STATUSES = {"rejected", "cancelled"}


class RefundWorkflowError(RuntimeError):
    """Raised when a refund workflow transition is not allowed."""


@dataclass(frozen=True)
class RefundWorkflowDecision:
    """Backend-evaluated refund workflow decision."""

    purchase_id: str
    purchase_type: PurchaseType
    can_enter_refund_workflow: bool
    can_prepare_refund: bool
    can_issue_funds: bool
    refund_stage: RefundStage
    required_action: RequiredAction
    refundable_amount_cents: int
    refund_outcome: RefundOutcome
    reasons: list[str]
    policy_facts: dict[str, Any]


def evaluate_refund_workflow(
    purchase: dict[str, Any],
    detail: dict[str, Any],
    evaluated_at: datetime,
) -> RefundWorkflowDecision:
    """Evaluate staged refund workflow state from persisted purchase/detail facts."""
    purchase_type = purchase["purchase_type"]

    if purchase_type == "physical":
        return evaluate_physical_refund_workflow(purchase, detail, evaluated_at)
    if purchase_type == "digital":
        return evaluate_digital_refund_workflow(purchase, detail, evaluated_at)
    if purchase_type == "subscription":
        return evaluate_subscription_refund_workflow(purchase, detail, evaluated_at)

    return build_decision(
        purchase=purchase,
        detail=detail,
        evaluated_at=evaluated_at,
        can_enter_refund_workflow=False,
        can_prepare_refund=False,
        can_issue_funds=False,
        refund_stage="blocked",
        required_action="none",
        refundable_amount_cents=0,
        refund_outcome="none",
        reasons=[f"unsupported_purchase_type:{purchase_type}"],
    )


def evaluate_physical_refund_workflow(
    purchase: dict[str, Any],
    detail: dict[str, Any],
    evaluated_at: datetime,
) -> RefundWorkflowDecision:
    """Evaluate physical product refund workflow state."""
    reasons = base_entry_failures(purchase, detail, evaluated_at)
    return_status = detail["return_status"]

    if return_status in PHYSICAL_BLOCKING_RETURN_STATUSES:
        reasons.append(f"return_status_{return_status}")

    prepared = (
        purchase["status"] == PREPARED_STATUS
        and detail["return_requested_at"] is not None
        and detail["return_barcode_generated"]
        and detail["return_label_created_at"] is not None
    )
    accepted_by_carrier = detail["accepted_by_carrier_at"] is not None
    can_enter = not reasons or prepared
    can_prepare = not reasons and not prepared
    can_issue = (
        prepared
        and accepted_by_carrier
        and return_status not in PHYSICAL_BLOCKING_RETURN_STATUSES
        and not common_issue_failures(purchase)
    )

    if purchase["status"] == "refunded":
        return issued_decision(purchase, detail, evaluated_at, physical_policy_facts(detail))
    if prepared and not accepted_by_carrier:
        reasons.append("return_not_accepted_by_carrier")

    return build_decision(
        purchase=purchase,
        detail=detail,
        evaluated_at=evaluated_at,
        can_enter_refund_workflow=can_enter,
        can_prepare_refund=can_prepare,
        can_issue_funds=can_issue,
        refund_stage="prepared" if prepared else ("eligible" if can_prepare else "blocked"),
        required_action=physical_required_action(can_prepare, can_issue, prepared),
        refundable_amount_cents=purchase["amount_cents"] if can_issue else 0,
        refund_outcome="full" if can_issue else "none",
        reasons=reasons,
        policy_facts=physical_policy_facts(detail),
    )


def evaluate_digital_refund_workflow(
    purchase: dict[str, Any],
    detail: dict[str, Any],
    evaluated_at: datetime,
) -> RefundWorkflowDecision:
    """Evaluate digital product refund workflow state."""
    reasons = base_entry_failures(purchase, detail, evaluated_at)

    if detail["code_redeemed"]:
        reasons.append("code_redeemed")

    prepared = purchase["status"] == PREPARED_STATUS and detail["code_invalidated_at"] is not None
    can_enter = not reasons or prepared
    can_prepare = not reasons and detail["code_invalidated_at"] is None
    can_issue = prepared and not detail["code_redeemed"] and not common_issue_failures(purchase)

    if purchase["status"] == "refunded":
        return issued_decision(purchase, detail, evaluated_at, digital_policy_facts(detail))
    if detail["code_invalidated_at"] is not None and not prepared:
        reasons.append("code_already_invalidated")

    required_action: RequiredAction = (
        "issue_funds" if can_issue else ("invalidate_code" if can_prepare else "none")
    )

    return build_decision(
        purchase=purchase,
        detail=detail,
        evaluated_at=evaluated_at,
        can_enter_refund_workflow=can_enter,
        can_prepare_refund=can_prepare,
        can_issue_funds=can_issue,
        refund_stage="prepared" if prepared else ("eligible" if can_prepare else "blocked"),
        required_action=required_action,
        refundable_amount_cents=purchase["amount_cents"] if can_prepare or can_issue else 0,
        refund_outcome="full" if can_prepare or can_issue else "none",
        reasons=reasons,
        policy_facts=digital_policy_facts(detail),
    )


def evaluate_subscription_refund_workflow(
    purchase: dict[str, Any],
    detail: dict[str, Any],
    evaluated_at: datetime,
) -> RefundWorkflowDecision:
    """Evaluate subscription refund workflow state."""
    reasons = base_entry_failures(purchase, detail, evaluated_at)
    period_start = detail["period_start"]
    period_end = detail["period_end"]
    prepared = (
        purchase["status"] == PREPARED_STATUS
        and detail["cancelled_at"] is not None
        and detail["service_ended_at"] is not None
        and detail["auto_renew"] is False
        and detail["refund_proration_mode"] in {"full", "prorated"}
    )

    if evaluated_at < period_start or evaluated_at > period_end:
        reasons.append("subscription_period_inactive")
    already_cancelled = (
        detail["cancelled_at"] is not None or detail["service_ended_at"] is not None
    )
    if already_cancelled and not prepared:
        reasons.append("subscription_already_cancelled")
    if detail["refund_proration_mode"] != "none" and not prepared:
        reasons.append("subscription_already_refunded")

    outcome = subscription_refund_outcome(detail, evaluated_at)
    amount = subscription_refund_amount(purchase, detail, evaluated_at, outcome)
    can_enter = not reasons or prepared
    can_prepare = not reasons and not prepared
    can_issue = prepared and not common_issue_failures(purchase)

    if purchase["status"] == "refunded":
        return issued_decision(purchase, detail, evaluated_at, subscription_policy_facts(detail))

    required_action: RequiredAction = (
        "issue_funds" if can_issue else ("cancel_subscription" if can_prepare else "none")
    )

    return build_decision(
        purchase=purchase,
        detail=detail,
        evaluated_at=evaluated_at,
        can_enter_refund_workflow=can_enter,
        can_prepare_refund=can_prepare,
        can_issue_funds=can_issue,
        refund_stage="prepared" if prepared else ("eligible" if can_prepare else "blocked"),
        required_action=required_action,
        refundable_amount_cents=amount if can_prepare or can_issue else 0,
        refund_outcome=outcome if can_issue or can_prepare else "none",
        reasons=reasons,
        policy_facts=subscription_policy_facts(detail),
    )


def base_entry_failures(
    purchase: dict[str, Any],
    detail: dict[str, Any],
    evaluated_at: datetime,
) -> list[str]:
    """Return failures that block entering or preparing refund workflow."""
    reasons: list[str] = []

    if purchase["status"] in TERMINAL_OR_BLOCKING_STATUSES:
        reasons.append(f"purchase_status_{purchase['status']}")
    elif (
        purchase["status"] not in WORKFLOW_ENTRY_STATUSES
        and purchase["status"] != PREPARED_STATUS
    ):
        reasons.append(f"purchase_status_{purchase['status']}")
    if evaluated_at > detail["refund_window_expires_at"] and purchase["status"] != PREPARED_STATUS:
        reasons.append("refund_window_expired")

    return reasons


def common_issue_failures(purchase: dict[str, Any]) -> list[str]:
    """Return common issue-stage failures."""
    if purchase["status"] != PREPARED_STATUS:
        return [f"purchase_status_{purchase['status']}"]
    return []


def assert_can_prepare_refund(
    purchase: dict[str, Any],
    detail: dict[str, Any],
    evaluated_at: datetime,
) -> RefundWorkflowDecision:
    """Return workflow decision or raise when refund preparation is not allowed."""
    decision = evaluate_refund_workflow(purchase, detail, evaluated_at)
    if not decision.can_prepare_refund:
        message = format_workflow_error("Refund preparation is not allowed", decision)
        raise RefundWorkflowError(message)
    return decision


def assert_can_issue_funds(
    purchase: dict[str, Any],
    detail: dict[str, Any],
    evaluated_at: datetime,
) -> RefundWorkflowDecision:
    """Return workflow decision or raise when fund issuance is not allowed."""
    decision = evaluate_refund_workflow(purchase, detail, evaluated_at)
    if not decision.can_issue_funds:
        raise RefundWorkflowError(format_workflow_error("Refund issuance is not allowed", decision))
    return decision


def assert_can_redeem_code(
    purchase: dict[str, Any],
    detail: dict[str, Any],
) -> None:
    """Raise when a digital issued code cannot be redeemed."""
    reasons = []

    if purchase["purchase_type"] != "digital":
        reasons.append("purchase_type_not_digital")
    if purchase["status"] in {"refund_pending", "refunded", "cancelled"}:
        reasons.append(f"purchase_status_{purchase['status']}")
    if detail["code_redeemed"]:
        reasons.append("code_already_redeemed")
    if detail["code_invalidated_at"] is not None:
        reasons.append("code_invalidated")

    if reasons:
        raise RefundWorkflowError(f"Code redemption is not allowed: {', '.join(reasons)}.")


def assert_can_confirm_carrier_acceptance(
    purchase: dict[str, Any],
    detail: dict[str, Any],
) -> None:
    """Raise when a physical return cannot be marked accepted by carrier."""
    reasons = []

    if purchase["purchase_type"] != "physical":
        reasons.append("purchase_type_not_physical")
    if purchase["status"] != PREPARED_STATUS:
        reasons.append(f"purchase_status_{purchase['status']}")
    if detail["return_status"] != "requested":
        reasons.append(f"return_status_{detail['return_status']}")
    if detail["accepted_by_carrier_at"] is not None:
        reasons.append("return_already_accepted_by_carrier")

    if reasons:
        raise RefundWorkflowError(
            f"Carrier acceptance confirmation is not allowed: {', '.join(reasons)}."
        )


def calculate_prorated_amount_cents(
    amount_cents: int,
    period_start: datetime,
    period_end: datetime,
    evaluated_at: datetime,
) -> int:
    """Calculate unused-time subscription refund amount in cents."""
    total_seconds = (period_end - period_start).total_seconds()
    if total_seconds <= 0:
        return 0

    remaining_seconds = max((period_end - evaluated_at).total_seconds(), 0)
    return round(amount_cents * (remaining_seconds / total_seconds))


def subscription_refund_outcome(detail: dict[str, Any], evaluated_at: datetime) -> RefundOutcome:
    """Return full or prorated subscription refund outcome for the evaluation time."""
    if detail["refund_proration_mode"] in {"full", "prorated"}:
        return detail["refund_proration_mode"]
    return "full" if evaluated_at <= detail["full_refund_window_expires_at"] else "prorated"


def subscription_refund_amount(
    purchase: dict[str, Any],
    detail: dict[str, Any],
    evaluated_at: datetime,
    outcome: RefundOutcome,
) -> int:
    """Return subscription refund amount for the outcome."""
    if outcome == "full":
        return purchase["amount_cents"]
    if outcome == "prorated":
        return calculate_prorated_amount_cents(
            amount_cents=purchase["amount_cents"],
            period_start=detail["period_start"],
            period_end=detail["period_end"],
            evaluated_at=evaluated_at,
        )
    return 0


def physical_required_action(
    can_prepare: bool,
    can_issue: bool,
    prepared: bool,
) -> RequiredAction:
    """Return the next required action for physical refunds."""
    if can_issue:
        return "issue_funds"
    if prepared:
        return "await_carrier_acceptance"
    if can_prepare:
        return "generate_return_label"
    return "none"


def issued_decision(
    purchase: dict[str, Any],
    detail: dict[str, Any],
    evaluated_at: datetime,
    policy_facts: dict[str, Any],
) -> RefundWorkflowDecision:
    """Return normalized decision for already-issued refunds."""
    refund_amount_cents = purchase.get("refund_amount_cents") or 0
    refund_outcome = purchase.get("refund_outcome") or "none"
    return build_decision(
        purchase=purchase,
        detail=detail,
        evaluated_at=evaluated_at,
        can_enter_refund_workflow=False,
        can_prepare_refund=False,
        can_issue_funds=False,
        refund_stage="issued",
        required_action="none",
        refundable_amount_cents=refund_amount_cents,
        refund_outcome=refund_outcome,
        reasons=["purchase_status_refunded"],
        policy_facts=policy_facts,
    )


def build_decision(
    purchase: dict[str, Any],
    detail: dict[str, Any],
    evaluated_at: datetime,
    can_enter_refund_workflow: bool,
    can_prepare_refund: bool,
    can_issue_funds: bool,
    refund_stage: RefundStage,
    required_action: RequiredAction,
    refundable_amount_cents: int,
    refund_outcome: RefundOutcome,
    reasons: list[str],
    policy_facts: dict[str, Any] | None = None,
) -> RefundWorkflowDecision:
    """Build a normalized refund workflow decision."""
    return RefundWorkflowDecision(
        purchase_id=str(purchase["id"]),
        purchase_type=purchase["purchase_type"],
        can_enter_refund_workflow=can_enter_refund_workflow,
        can_prepare_refund=can_prepare_refund,
        can_issue_funds=can_issue_funds,
        refund_stage=refund_stage,
        required_action=required_action,
        refundable_amount_cents=refundable_amount_cents,
        refund_outcome=refund_outcome,
        reasons=dedupe_reasons(reasons),
        policy_facts={
            "purchase_status": purchase["status"],
            "refund_requested_at": purchase.get("refund_requested_at"),
            "refunded_at": purchase.get("refunded_at"),
            "refund_amount_cents": purchase.get("refund_amount_cents"),
            "refund_outcome": purchase.get("refund_outcome"),
            "refund_window_expires_at": detail["refund_window_expires_at"],
            "evaluated_at": evaluated_at,
            **(policy_facts or {}),
        },
    )


def dedupe_reasons(reasons: list[str]) -> list[str]:
    """Return reasons without duplicate values while preserving order."""
    deduped: list[str] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    return deduped


def format_workflow_error(prefix: str, decision: RefundWorkflowDecision) -> str:
    """Format deterministic workflow denial reasons."""
    reasons = ", ".join(decision.reasons) if decision.reasons else decision.required_action
    return f"{prefix}: {reasons}."


def physical_policy_facts(detail: dict[str, Any]) -> dict[str, Any]:
    """Return physical facts used by workflow policy."""
    return {
        "return_status": detail["return_status"],
        "return_barcode_generated": detail["return_barcode_generated"],
        "return_label_created_at": detail["return_label_created_at"],
        "return_requested_at": detail["return_requested_at"],
        "accepted_by_carrier_at": detail["accepted_by_carrier_at"],
    }


def digital_policy_facts(detail: dict[str, Any]) -> dict[str, Any]:
    """Return digital facts used by workflow policy."""
    return {
        "code_redeemed": detail["code_redeemed"],
        "code_redeemed_at": detail["code_redeemed_at"],
        "code_invalidated_at": detail["code_invalidated_at"],
        "refund_lock_reason": detail["refund_lock_reason"],
    }


def subscription_policy_facts(detail: dict[str, Any]) -> dict[str, Any]:
    """Return subscription facts used by workflow policy."""
    return {
        "period_start": detail["period_start"],
        "period_end": detail["period_end"],
        "cancelled_at": detail["cancelled_at"],
        "service_ended_at": detail["service_ended_at"],
        "auto_renew": detail["auto_renew"],
        "refund_proration_mode": detail["refund_proration_mode"],
        "full_refund_window_expires_at": detail["full_refund_window_expires_at"],
    }
