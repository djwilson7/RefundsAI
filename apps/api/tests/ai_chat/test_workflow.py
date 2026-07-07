from __future__ import annotations

from typing import Any
import pytest

from refunds_ai_api.services.ai_chat.workflow import (
    parse_refund_workflow_mutation_intent,
    parse_refund_workflow_mutation_action,
    parse_refund_workflow_confirmation_intent,
    is_refund_confirmation_boundary_reply,
    is_generic_refund_confirmation_reply,
    build_refund_confirmation_command_guidance,
    build_refund_confirmation_command_offer,
    parse_refund_workflow_decline_intent,
    parse_refund_workflow_continuation_intent,
    build_refund_workflow_action_not_wired_response,
    humanize_refund_action,
)

def test_workflow_parsers() -> None:
    # parse_refund_workflow_mutation_intent
    assert parse_refund_workflow_mutation_intent("please start my refund") == "workflow"
    assert parse_refund_workflow_mutation_intent("hello") is None

    # parse_refund_workflow_mutation_action
    assert parse_refund_workflow_mutation_action("hello") is None
    assert parse_refund_workflow_mutation_action("issue the refund") == "issue_refund"
    assert parse_refund_workflow_mutation_action("start my refund") == "request_refund"
    assert parse_refund_workflow_mutation_action("generate return label") == "request_refund"

    # parse_refund_workflow_confirmation_intent
    assert parse_refund_workflow_confirmation_intent("Confirm invalidate code and issue refund") is True
    assert parse_refund_workflow_confirmation_intent("yes, please") is True
    assert parse_refund_workflow_confirmation_intent("no") is False

    # is_refund_confirmation_boundary_reply
    assert is_refund_confirmation_boundary_reply("yes") is True
    assert is_refund_confirmation_boundary_reply("hello") is False

    # is_generic_refund_confirmation_reply
    assert is_generic_refund_confirmation_reply("yes") is True
    assert is_generic_refund_confirmation_reply("hello") is False

    # parse_refund_workflow_decline_intent
    assert parse_refund_workflow_decline_intent("no thanks") is True
    assert parse_refund_workflow_decline_intent("hello") is False

    # parse_refund_workflow_continuation_intent
    assert parse_refund_workflow_continuation_intent("generate the return label") == "workflow_continuation"
    assert parse_refund_workflow_continuation_intent("hello") is None

def test_guidance_and_offer() -> None:
    # build_refund_confirmation_command_guidance
    assert build_refund_confirmation_command_guidance({"confirmation_command": "Command"}) == "To continue, reply:\n\nCommand"
    assert build_refund_confirmation_command_guidance({"purchase_type": "digital"}) == "To continue, reply:\n\nConfirm invalidate code and issue refund"
    assert build_refund_confirmation_command_guidance({"purchase_type": "invalid"}) == "Please confirm the product name or order number before continuing the refund process."

    # build_refund_confirmation_command_offer
    assert build_refund_confirmation_command_offer({"confirmation_command": "Command"}) == "According to the refund policy, this purchase is eligible for a refund. To continue, reply:\n\nCommand"
    assert build_refund_workflow_action_not_wired_response({"product_name": "Product", "eligible": True, "next_action": "generate_return_label"}) == "Product is eligible for a refund, but I cannot start the return process yet."
    assert build_refund_confirmation_command_offer({"purchase_type": "invalid"}) == ""

def test_build_refund_workflow_action_not_wired_response() -> None:
    # not eligible
    context = {"product_name": "Product", "eligible": False}
    assert build_refund_workflow_action_not_wired_response(context) == "Product is not eligible for a refund, so there is no refund process to continue."

    # next_action == "generate_return_label"
    context = {"product_name": "Product", "eligible": True, "next_action": "generate_return_label"}
    assert build_refund_workflow_action_not_wired_response(context) == "Product is eligible for a refund, but I cannot start the return process yet."

    # next_action is other string
    context = {"product_name": "Product", "eligible": True, "next_action": "other_action"}
    assert build_refund_workflow_action_not_wired_response(context) == "Product is eligible for a refund, but I cannot continue the refund process yet."

    # next_action is None or empty
    context = {"product_name": "Product", "eligible": True, "next_action": None}
    assert build_refund_workflow_action_not_wired_response(context) == "Product is eligible for a refund, but I cannot continue the refund process yet."

def test_humanize_refund_action() -> None:
    assert humanize_refund_action("generate_return_label") == "generating a return label"
    assert humanize_refund_action("cancel_subscription") == "cancelling the subscription"
    assert humanize_refund_action("some_random_action") == "some random action"
