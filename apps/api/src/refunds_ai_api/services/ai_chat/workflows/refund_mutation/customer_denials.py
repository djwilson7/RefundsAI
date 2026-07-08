"""Customer-facing explanations for denied refund process actions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from refunds_ai_api.services.money import format_cents


def build_customer_denial_explanation(
    *,
    action: str,
    mutation_target: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Return normalized customer-facing context for a denied refund action."""
    purchase_type = mutation_target.get("purchase_type")
    reason = _controlling_reason(workflow)
    context = {
        "action_attempted": action,
        "purchase_type": purchase_type,
        "refund_stage": workflow.get("refund_stage"),
        "refund_outcome": workflow.get("refund_outcome"),
        "refund_lock_reason": _policy_facts(workflow).get("refund_lock_reason"),
        "reasons": [
            item for item in workflow.get("reasons", []) if isinstance(item, str)
        ],
        "policy_facts": _policy_facts(workflow),
        "relevant_policy_section": _policy_section(purchase_type, reason),
        "controlling_reason": reason,
    }
    parts = _message_parts(
        action=action,
        mutation_target=mutation_target,
        workflow=workflow,
        reason=reason,
    )
    context.update(parts)
    context["message"] = " ".join(
        part
        for part in (
            parts["system_shows"],
            parts["policy_requires"],
            parts["cannot_proceed"],
            parts["next_step"],
        )
        if part
    )
    return context


def _message_parts(
    *,
    action: str,
    mutation_target: dict[str, Any],
    workflow: dict[str, Any],
    reason: str,
) -> dict[str, str]:
    purchase_type = mutation_target.get("purchase_type")
    product_name = mutation_target.get("product_name")
    policy_facts = _policy_facts(workflow)
    if reason in {"code_redeemed", "digital_entitlement_redeemed"}:
        return {
            "system_shows": "The system shows the code was redeemed.",
            "policy_requires": (
                "According to the return policy, digital items can only be "
                "refunded when the request is within 15 days of purchase and "
                "the code has not been redeemed."
            ),
            "cannot_proceed": (
                "Because this code was redeemed, we're unable to issue a "
                "refund for this item."
            ),
            "next_step": "",
        }

    if reason in {"return_not_accepted_by_carrier", "physical_return_not_in_transit"}:
        return {
            "system_shows": (
                "The system shows the return process has started, but the item "
                "has not been scanned by the courier yet."
            ),
            "policy_requires": (
                "According to the return policy, funds can be released once "
                "the returned package is with the courier or in transit."
            ),
            "cannot_proceed": (
                "Because the package has not been scanned by the courier yet, "
                "we're unable to release the funds right now."
            ),
            "next_step": (
                "As soon as you deliver the package to the courier and it is "
                "scanned, I can help check whether the funds are ready to be issued."
            ),
        }

    if reason in {"purchase_status_refunded", "already_refunded"}:
        amount = _completed_refund_amount(policy_facts)
        date = _completed_refund_date(policy_facts)
        refund_phrase = (
            f" and a refund of {amount} was issued{f' on {date}' if date else ''}"
            if amount
            else f" and a refund was issued{f' on {date}' if date else ''}"
            if date
            else " and a refund was already issued"
        )
        if purchase_type == "subscription":
            system_shows = (
                "The system shows this subscription was already canceled,"
                f"{refund_phrase}."
            )
        else:
            date_suffix = f" on {date}" if date else ""
            system_shows = (
                "The system shows this purchase was already refunded"
                f"{date_suffix}."
            )
        return {
            "system_shows": system_shows,
            "policy_requires": (
                "According to the return policy, a completed refund cannot be "
                "canceled or refunded again."
            ),
            "cannot_proceed": (
                "There is no additional cancellation or refund action "
                "available for this subscription."
                if purchase_type == "subscription"
                else "There is no additional refund action available for this purchase."
            ),
            "next_step": "",
        }

    if reason in {"refund_window_expired", "outside_refund_window"}:
        window = _format_date(policy_facts.get("refund_window_expires_at"))
        return {
            "system_shows": (
                f"The system shows the refund window ended on {window}."
                if window
                else "The system shows the refund window has ended."
            ),
            "policy_requires": _policy_window_requirement(purchase_type),
            "cannot_proceed": (
                "Because the request is outside the refund window, we're "
                "unable to continue with this refund."
            ),
            "next_step": "",
        }

    if reason in {"subscription_period_inactive", "subscription_not_active"}:
        return {
            "system_shows": (
                "The system shows this subscription is not active in the "
                "current billing cycle."
            ),
            "policy_requires": (
                "According to the return policy, subscription refunds require "
                "an active subscription in the current billing cycle."
            ),
            "cannot_proceed": (
                "Because the subscription is not active, we're unable to "
                "cancel it or issue a refund through this process."
            ),
            "next_step": "",
        }

    action_label = "start the refund process" if action == "request_refund" else "issue the refund"
    return {
        "system_shows": (
            f"The system shows {product_name} is not eligible for that refund "
            "action right now."
            if isinstance(product_name, str)
            else "The system shows this purchase is not eligible for that refund action right now."
        ),
        "policy_requires": _policy_window_requirement(purchase_type),
        "cannot_proceed": (
            "Because the policy requirements are not met, we're unable to "
            f"{action_label}."
        ),
        "next_step": "Please contact support if you think this purchase needs a manual review.",
    }


def _controlling_reason(workflow: dict[str, Any]) -> str:
    policy_facts = _policy_facts(workflow)
    lock_reason = policy_facts.get("refund_lock_reason")
    if isinstance(lock_reason, str) and lock_reason:
        return lock_reason
    reasons = workflow.get("reasons")
    if isinstance(reasons, list):
        for reason in reasons:
            if isinstance(reason, str) and reason:
                if reason == "purchase_status_redeemed":
                    return "code_redeemed"
                if reason == "purchase_status_refunded":
                    return "already_refunded"
                return reason
    required_action = workflow.get("required_action")
    if required_action == "await_carrier_acceptance":
        return "physical_return_not_in_transit"
    if workflow.get("refund_stage") == "issued":
        return "already_refunded"
    return "unknown"


def _policy_facts(workflow: dict[str, Any]) -> dict[str, Any]:
    policy_facts = workflow.get("policy_facts")
    return policy_facts if isinstance(policy_facts, dict) else {}


def _policy_section(purchase_type: Any, reason: str) -> str:
    if reason in {"return_not_accepted_by_carrier", "physical_return_not_in_transit"}:
        return "funds_release"
    if purchase_type in {"digital", "physical", "subscription"}:
        return f"{purchase_type}_refund_policy"
    return "general_refund_policy"


def _policy_window_requirement(purchase_type: Any) -> str:
    if purchase_type == "digital":
        return (
            "According to the return policy, digital items can only be "
            "refunded when the request is within 15 days of purchase and the "
            "code has not been redeemed."
        )
    if purchase_type == "physical":
        return (
            "According to the return policy, physical items must be within the "
            "return window and follow the return process before funds are released."
        )
    if purchase_type == "subscription":
        return (
            "According to the return policy, subscription refunds require an "
            "active subscription in the current billing cycle."
        )
    return "According to the return policy, the purchase must meet the refund requirements."


def _completed_refund_amount(policy_facts: dict[str, Any]) -> str | None:
    amount_cents = policy_facts.get("refund_amount_cents")
    if isinstance(amount_cents, int):
        return format_cents(amount_cents)
    return None


def _completed_refund_date(policy_facts: dict[str, Any]) -> str | None:
    return _format_date(policy_facts.get("refunded_at"))


def _format_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return value.split("T", 1)[0]
    return None
