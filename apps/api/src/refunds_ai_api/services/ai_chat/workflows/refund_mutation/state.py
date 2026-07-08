"""Refund mutation validation and conversation-state shaping."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.models import ChatGraphState
from refunds_ai_api.services.ai_chat.workflow import (
    parse_refund_workflow_mutation_action,
    refund_confirmation_command_for_purchase_type,
)
from refunds_ai_api.services.ai_chat.workflows.context import WorkflowContext
from refunds_ai_api.services.money import format_cents


def _pending_action_from_active_refund_context(
    active_refund_context: dict[str, Any],
) -> dict[str, Any] | None:
    """Build the internal pending action after command verification."""
    command_config = refund_confirmation_command_for_purchase_type(
        active_refund_context.get("purchase_type")
    )
    action = active_refund_context.get("confirmation_mutation_action")
    if action not in {"request_refund", "issue_refund"} and command_config is not None:
        action = command_config["mutation_action"]
    if action not in {"request_refund", "issue_refund"}:
        return None
    return {
        "action": action,
        "purchase_id": active_refund_context["purchase_id"],
        "product_name": active_refund_context["product_name"],
        "purchase_type": active_refund_context["purchase_type"],
        "required_action": active_refund_context.get("next_action"),
        "confirmation_expected_command": active_refund_context.get("confirmation_command"),
        "refundable_amount_cents": None,
        "refund_outcome": None,
    }

def _resolve_refund_mutation_action(
    message: str,
    mutation_target: dict[str, Any],
) -> str:
    """Return the mutation command requested for the resolved purchase."""
    action = parse_refund_workflow_mutation_action(message)
    if action is not None:
        return action
    del mutation_target
    return "request_refund"

def _validate_refund_mutation_allowed(
    action: str,
    mutation_target: dict[str, Any],
    workflow: dict[str, Any],
) -> tuple[bool, str]:
    """Return whether the current backend workflow allows the requested command."""
    product_name = mutation_target["product_name"]
    if action == "request_refund":
        if workflow.get("can_prepare_refund") is True:
            return True, ""
        return (
            False,
            (
                f"I cannot start a refund for {product_name} because the current "
                "refund status does not allow it."
            ),
        )

    if workflow.get("can_issue_funds") is True:
        return True, ""
    return (
        False,
        (
            f"I cannot issue the refund for {product_name} because the current "
            "refund status is not ready to release funds."
        ),
    )

def _expected_refund_stage_for_mutation(action: str) -> str:
    if action == "issue_refund":
        return "issued"
    return "prepared"

def _mutation_persistence_matches(action: str, workflow: dict[str, Any]) -> bool:
    return workflow.get("refund_stage") == _expected_refund_stage_for_mutation(action)

def _build_refund_validation_failed_response(action: str) -> str:
    if action == "issue_refund":
        return (
            "The refund was submitted, but I could not verify that the final "
            "refund status was saved. Please check the purchase status."
        )
    return (
        "I started the refund process, but I could not verify that the "
        "preparation step was saved. I did not issue funds."
    )

def _build_refund_mutation_success_response(
    action: str,
    pending_action: dict[str, Any],
    result: dict[str, Any],
) -> str:
    """Return a concise deterministic response after a confirmed mutation."""
    product_name = pending_action["product_name"]
    if action == "issue_refund":
        amount_cents = result.get("refundable_amount_cents")
        amount = format_cents(amount_cents) if isinstance(amount_cents, int) else None
        amount_text = f"{amount} " if amount is not None else "the refunded amount "
        if pending_action.get("purchase_type") == "subscription":
            return (
                "The subscription has been canceled and the refund process has "
                f"completed. You should see {amount_text}reflected to your "
                "original payment method within 3-10 business days. Do you have "
                "any other questions, or would you like further assistance?"
            )
        return (
            "The refund process has completed. You should see "
            f"{amount_text}reflected to your original payment method within "
            "3-10 business days. Do you have any other questions, or would you "
            "like further assistance?"
        )

    required_action = result.get("required_action")
    if required_action == "await_carrier_acceptance":
        return (
            "The return process has started, and your return label is ready. "
            "Please send the item back using the provided label. Once the "
            "carrier accepts or scans the package, the refund can be released."
        )
    if result.get("can_issue_funds") is True:
        return (
            f"The refund process has started for {product_name}. The refund has "
            "not been released yet."
        )
    return f"The refund process has started for {product_name}."

def _active_refund_context_from_workflow(
    pending_action: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Build active refund context after a mutation updates backend state."""
    stage = workflow.get("refund_stage")
    required_action = workflow.get("required_action")
    if stage == "issued":
        next_action = None
        active_stage = "issued"
    elif stage == "prepared":
        next_action = required_action if isinstance(required_action, str) else None
        if next_action == "none":
            next_action = None
        active_stage = "prepared"
    else:
        next_action = required_action if isinstance(required_action, str) else None
        active_stage = "eligibility_confirmed"
    reasons = workflow.get("reasons")
    if not isinstance(reasons, list):
        reasons = []

    from refunds_ai_api.services.ai_chat.state import RefundStateMachine
    state_machine_stage = RefundStateMachine.get_stage(workflow, pending_action)

    active_refund_context: dict[str, Any] = {
        "purchase_id": pending_action["purchase_id"],
        "product_name": pending_action["product_name"],
        "purchase_type": pending_action["purchase_type"],
        "eligible": workflow.get("refund_stage") != "blocked",
        "stage": active_stage,
        "refund_state_machine_stage": state_machine_stage.value,
        "next_action": next_action,
        "reason_codes": [reason for reason in reasons if isinstance(reason, str)],
    }
    command_config = refund_confirmation_command_for_purchase_type(
        pending_action.get("purchase_type")
    )
    if (
        active_refund_context["eligible"] is True
        and active_stage in {"eligibility_confirmed", "awaiting_return_label", "prepared"}
        and command_config is not None
    ):
        backend_action = command_config["backend_action"]
        mutation_action = command_config["mutation_action"]
        confirmation_steps = list(command_config["steps"])
        if active_stage == "prepared" and next_action == "issue_funds":
            backend_action = "issue_funds"
            mutation_action = "issue_refund"
            confirmation_steps = ["issue the refund"]
        active_refund_context.update(
            {
                "confirmation_command": command_config["command"],
                "confirmation_backend_action": backend_action,
                "confirmation_mutation_action": mutation_action,
                "confirmation_steps": confirmation_steps,
            }
        )
    return active_refund_context

def _active_refund_context_from_pending_action(
    pending_action: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Build command-ready active refund context before any mutation is executed."""
    return _active_refund_context_from_workflow(pending_action, workflow)

def _active_mutation_workflow_state(
    state: ChatGraphState,
    context: WorkflowContext,
    action: str,
    pending_action: dict[str, Any],
    workflow: dict[str, Any],
    *,
    last_tool_name: str | None = None,
) -> dict[str, Any]:
    """Return compact active workflow metadata for refund mutation turns."""
    conversation_object = (
        context.classification.conversation_object
        if context.classification is not None
        else None
    )
    return {
        "kind": "refund_mutation",
        "object_kind": conversation_object.kind.value
        if conversation_object is not None
        else None,
        "object_label": pending_action.get("product_name"),
        "operation": action,
        "last_user_message": state["message"],
        "last_tool_name": last_tool_name,
        "last_tool_result_summary": {
            "purchase_id": pending_action.get("purchase_id"),
            "refund_stage": workflow.get("refund_stage"),
            "required_action": workflow.get("required_action"),
        },
    }
