from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from refunds_ai_api.services.ai_chat import (
    EMPTY_CONVERSATION_STATE,
    AIChatService,
    ModelTurn,
)

from .assertions import assert_customer_safe_response
from .fakes import (
    CUSTOMER_ID,
    PURCHASE_ID,
    DeveloperToolkitApplicationService,
    FailedPersistenceRefundApplicationService,
    MutableRefundApplicationService,
    NoToolModelClient,
)

SUBSCRIPTION_PURCHASE_ID = "40000000-0000-4000-8000-000000000004"
PHYSICAL_PURCHASE_ID = "40000000-0000-4000-8000-000000000003"
AI_ASSISTANT_PRO_PURCHASE_ID = "40000000-0000-4000-8000-000000000009"
DIGITAL_CONFIRMATION_COMMAND = "Confirm invalidate code and issue refund"
PHYSICAL_CONFIRMATION_COMMAND = "Confirm start return and issue label"
SUBSCRIPTION_CONFIRMATION_COMMAND = "Confirm cancel and issue refund"
VALIDATION_FAILED_RESPONSE = (
    "I received your confirmation, but I couldn't verify this purchase against "
    "your account, so I can't start the return process."
)


def assert_refund_completion_cleared_state(conversation_state: dict[str, Any]) -> None:
    expected_state = dict(EMPTY_CONVERSATION_STATE)
    expected_state["current_page"] = conversation_state.get("current_page")
    assert conversation_state == expected_state


class PrematureRefundCompletionModelClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        self.calls.append({"messages": messages, "tools": tools})
        return ModelTurn(
            content="The refund has already been completed.",
            tool_calls=[],
        )


class AIAssistantProApplicationService(MutableRefundApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        purchases = super().list_user_purchases(user_id)
        return [
            {
                "id": AI_ASSISTANT_PRO_PURCHASE_ID,
                "order_number": "RAI-10009",
                "purchase_type": "subscription",
                "product_name": "AI Assistant Pro",
                "sku": "SUB-AI-ASSISTANT-PRO",
                "amount_cents": 1999,
                "purchased_at": datetime(2026, 6, 25, 14, 30, tzinfo=UTC),
                "status": "subscribed",
                "details_url": (
                    f"/api/purchases/{AI_ASSISTANT_PRO_PURCHASE_ID}/details"
                ),
            },
            *purchases,
        ]

    def get_refund_workflow(self, purchase_id: str) -> dict[str, Any]:
        if purchase_id != AI_ASSISTANT_PRO_PURCHASE_ID:
            return super().get_refund_workflow(purchase_id)

        self.refund_workflow_called = True
        self.refund_workflow_requests.append(purchase_id)
        workflow = {
            "purchase_id": AI_ASSISTANT_PRO_PURCHASE_ID,
            "purchase_type": "subscription",
            "can_enter_refund_workflow": True,
            "can_prepare_refund": True,
            "can_issue_funds": False,
            "refund_stage": "eligible",
            "required_action": "cancel_subscription",
            "refundable_amount_cents": 1999,
            "refund_outcome": "full",
            "reasons": [],
            "policy_facts": {
                "purchase_status": "subscribed",
                "subscription_active": True,
            },
        }
        if purchase_id in self.issued_purchase_ids:
            workflow.update(
                {
                    "can_enter_refund_workflow": False,
                    "can_prepare_refund": False,
                    "can_issue_funds": False,
                    "refund_stage": "issued",
                    "required_action": "none",
                }
            )
        elif purchase_id in self.prepared_purchase_ids:
            workflow.update(
                {
                    "can_prepare_refund": False,
                    "can_issue_funds": True,
                    "refund_stage": "prepared",
                    "required_action": "issue_funds",
                }
            )
        return workflow


class StrictCustomerPhysicalApplicationService(MutableRefundApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        if user_id != CUSTOMER_ID:
            self.purchase_requests.append(user_id)
            return []
        return super().list_user_purchases(user_id)


class PreparedPhysicalApplicationService(MutableRefundApplicationService):
    def get_refund_workflow(self, purchase_id: str) -> dict[str, Any]:
        workflow = dict(super().get_refund_workflow(purchase_id))
        if purchase_id == PHYSICAL_PURCHASE_ID:
            workflow.update(
                {
                    "can_enter_refund_workflow": True,
                    "can_prepare_refund": False,
                    "can_issue_funds": False,
                    "refund_stage": "prepared",
                    "required_action": "await_carrier_acceptance",
                }
            )
        return workflow


def _pending_digital_refund_action(action: str = "request_refund") -> dict[str, str]:
    return {
        "action": action,
        "purchase_id": PURCHASE_ID,
        "product_name": "Design Template Pack",
        "purchase_type": "digital",
        "confirmation_expected_command": DIGITAL_CONFIRMATION_COMMAND,
    }


def _pending_physical_refund_action() -> dict[str, str]:
    return {
        "action": "request_refund",
        "purchase_id": PHYSICAL_PURCHASE_ID,
        "product_name": "Keyboard",
        "purchase_type": "physical",
        "required_action": "generate_return_label",
        "confirmation_expected_command": PHYSICAL_CONFIRMATION_COMMAND,
    }

def _pending_prepared_physical_refund_action() -> dict[str, str]:
    return {
        **_pending_physical_refund_action(),
        "required_action": "await_carrier_acceptance",
    }


def _persist_digital_confirmation(
    application_service: MutableRefundApplicationService,
    *,
    customer_id: str = CUSTOMER_ID,
    purchase_id: str = PURCHASE_ID,
    expected_command: str = DIGITAL_CONFIRMATION_COMMAND,
) -> None:
    application_service.refund_confirmations[purchase_id] = {
        "refund_confirmation_granted": True,
        "refund_confirmation_message": f"{expected_command}.",
        "refund_confirmation_granted_at": datetime(2026, 7, 3, 14, tzinfo=UTC),
        "refund_confirmation_expected_command": expected_command,
        "refund_confirmation_matched": True,
        "refund_confirmation_source": "chat_confirmation_validator",
        "refund_confirmation_customer_id": customer_id,
        "refund_confirmation_purchase_id": purchase_id,
        "refund_confirmation_consumed_at": None,
        "refund_confirmation_consumed_by_action": None,
    }


def _ai_assistant_pro_confirmation_state(
    *,
    include_active_purchase: bool = True,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "active_workflow": {
            "kind": "refund_eligibility",
            "object_kind": "full_purchase_history",
            "object_label": "your purchase history",
            "operation": "eligibility",
            "last_user_message": "Can I refund AI Assistant Pro?",
        },
        "active_result_set": {
            "type": "purchase_history",
            "label": "your purchase history",
            "purchase_ids": [PURCHASE_ID, AI_ASSISTANT_PRO_PURCHASE_ID],
        },
        "selected_purchase_id": AI_ASSISTANT_PRO_PURCHASE_ID,
        "selected_purchase_ids": [AI_ASSISTANT_PRO_PURCHASE_ID],
        "selected_purchase_type": "subscription",
        "active_refund_context": {
            "purchase_id": AI_ASSISTANT_PRO_PURCHASE_ID,
            "product_name": "AI Assistant Pro",
            "purchase_type": "subscription",
            "eligible": True,
            "stage": "eligibility_confirmed",
            "next_action": "cancel_subscription",
            "reason_codes": [],
            "confirmation_command": SUBSCRIPTION_CONFIRMATION_COMMAND,
            "confirmation_backend_action": "cancel_subscription",
            "confirmation_mutation_action": "request_refund",
            "confirmation_steps": [
                "cancel the subscription",
                "calculate the final refund",
                "issue the refund",
            ],
        },
    }
    if include_active_purchase:
        state["active_purchase"] = {
            "purchase_id": AI_ASSISTANT_PRO_PURCHASE_ID,
            "product_name": "AI Assistant Pro",
            "purchase_type": "subscription",
        }
    return state


def test_chat_graph_refund_mutation_requires_confirmation_before_digital_issue(
    caplog,
) -> None:
    application_service = MutableRefundApplicationService()
    eligibility_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This purchase is eligible."),
    ).create_response(
        message="Can I refund this item?",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
    )

    pending_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="Start the refund.",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state=eligibility_result.conversation_state,
    )

    assert application_service.request_refund_requests == []
    assert application_service.issue_refund_requests == []
    assert "Confirm invalidate code and issue refund" in pending_result.content
    assert pending_result.conversation_state["pending_refund_action"] is None
    assert pending_result.conversation_state["active_refund_context"][
        "confirmation_command"
    ] == "Confirm invalidate code and issue refund"

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        confirmed_result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("This response should not be used."),
        ).create_response(
            message="Confirm invalidate code and issue refund.",
            customer_id=CUSTOMER_ID,
            purchase_id=PURCHASE_ID,
            page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
            conversation_state=pending_result.conversation_state,
        )

    assert application_service.request_refund_requests == [PURCHASE_ID]
    assert application_service.issue_refund_requests == [PURCHASE_ID]
    assert confirmed_result.content == (
        "The refund process has completed. You should see $45.00 reflected to "
        "your original payment method within 3-10 business days. Do you have "
        "any other questions, or would you like further assistance?"
    )
    assert_customer_safe_response(confirmed_result.content)
    assert_refund_completion_cleared_state(confirmed_result.conversation_state)
    assert confirmed_result.side_effects == [
        {
            "type": "purchase_data_changed",
            "customer_id": CUSTOMER_ID,
            "purchase_ids": [PURCHASE_ID],
            "reason": "refund_mutation_completed",
        }
    ]
    completed_event = next(
        record.event
        for record in caplog.records
        if getattr(record, "event", {}).get("type") == "mutation_completed"
    )
    assert completed_event["data"]["purchase_id"] == PURCHASE_ID
    assert completed_event["data"]["product_name"] == "Design Template Pack"
    assert completed_event["data"]["mutation_action"] == "issue_refund"
    assert completed_event["data"]["persisted_status_or_stage"] == "issued"
    lifecycle_event = next(
        record.event
        for record in caplog.records
        if getattr(record, "event", {}).get("type")
        == "workflow.refund_mutation_lifecycle"
    )
    assert lifecycle_event["data"]["purchase"]["purchase_id"] == PURCHASE_ID
    assert lifecycle_event["data"]["confirmation"]["persisted_granted"] is True
    assert [transition["action"] for transition in lifecycle_event["data"]["transitions"]] == [
        "request_refund",
        "issue_refund",
    ]
    assert {
        getattr(record, "event", {}).get("type")
        for record in caplog.records
    }.isdisjoint(
        {
            "mutation_requested",
            "mutation_target_resolved",
            "mutation_permission_validated",
            "mutation_persistence_validation_started",
            "mutation_persistence_validation_succeeded",
        }
    )


def test_chat_graph_refund_mutation_cancels_subscription_and_issues_refund() -> None:
    application_service = MutableRefundApplicationService()
    eligibility_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This subscription is eligible."),
    ).create_response(
        message="Can I refund this subscription?",
        customer_id=CUSTOMER_ID,
        purchase_id=SUBSCRIPTION_PURCHASE_ID,
        page_context={
            "surface": "purchase_detail",
            "purchase_id": SUBSCRIPTION_PURCHASE_ID,
        },
    )

    assert "Confirm cancel and issue refund" in eligibility_result.content

    confirmed_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="Confirm cancel and issue refund.",
        customer_id=CUSTOMER_ID,
        purchase_id=SUBSCRIPTION_PURCHASE_ID,
        page_context={
            "surface": "purchase_detail",
            "purchase_id": SUBSCRIPTION_PURCHASE_ID,
        },
        conversation_state=eligibility_result.conversation_state,
    )

    assert application_service.request_refund_requests == [SUBSCRIPTION_PURCHASE_ID]
    assert application_service.issue_refund_requests == [SUBSCRIPTION_PURCHASE_ID]
    assert confirmed_result.content == (
        "The subscription has been canceled and the refund process has completed. "
        "You should see $9.99 reflected to your original payment method within "
        "3-10 business days. Do you have any other questions, or would you like "
        "further assistance?"
    )
    assert_customer_safe_response(confirmed_result.content)
    assert_refund_completion_cleared_state(confirmed_result.conversation_state)


def test_chat_graph_subscription_confirmation_hands_off_to_mutation_from_active_target(
    caplog,
) -> None:
    application_service = AIAssistantProApplicationService()
    model_client = PrematureRefundCompletionModelClient()

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=model_client,
        ).create_response(
            message=SUBSCRIPTION_CONFIRMATION_COMMAND,
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            page_context={"surface": "purchase_history"},
            conversation_state=_ai_assistant_pro_confirmation_state(),
        )

    assert application_service.request_refund_requests == [
        AI_ASSISTANT_PRO_PURCHASE_ID
    ]
    assert application_service.issue_refund_requests == [AI_ASSISTANT_PRO_PURCHASE_ID]
    assert "To continue, reply" not in result.content
    assert result.content == (
        "The subscription has been canceled and the refund process has completed. "
        "You should see $19.99 reflected to your original payment method within "
        "3-10 business days. Do you have any other questions, or would you like "
        "further assistance?"
    )
    assert "already been completed" not in result.content
    assert len(model_client.calls) == 1
    assert_refund_completion_cleared_state(result.conversation_state)

    events = [getattr(record, "event", {}) for record in caplog.records]
    event_types = {event.get("type") for event in events}
    assert "workflow.confirmation_command_invalid" not in event_types
    assert "workflow.confirmation_target_resolution_failed" not in event_types
    assert "workflow.confirmation_pending_action_missing" not in event_types
    assert "workflow.confirmation_validated" in event_types
    assert "workflow.refund_mutation_started" in event_types
    assert "workflow.refund_mutation_lifecycle" in event_types
    validated_event = next(
        event for event in events if event.get("type") == "workflow.confirmation_validated"
    )
    assert validated_event["data"]["confirmed"] is True
    assert validated_event["data"]["purchase_id"] == AI_ASSISTANT_PRO_PURCHASE_ID
    classified_event = next(
        event for event in events if event.get("type") == "workflow.classified"
    )
    assert classified_event["data"]["object"] == "active_purchase"
    assert classified_event["data"]["object_label"] == "AI Assistant Pro"


def test_chat_graph_subscription_confirmation_rejects_without_active_target(
    caplog,
) -> None:
    application_service = AIAssistantProApplicationService()

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("This response should not be used."),
        ).create_response(
            message=SUBSCRIPTION_CONFIRMATION_COMMAND,
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            page_context={"surface": "purchase_history"},
            conversation_state=_ai_assistant_pro_confirmation_state(
                include_active_purchase=False
            ),
        )

    assert application_service.request_refund_requests == []
    assert application_service.issue_refund_requests == []
    assert result.content == (
        "To continue, reply:\n\nConfirm cancel and issue refund"
    )
    events = [getattr(record, "event", {}) for record in caplog.records]
    event_types = {event.get("type") for event in events}
    assert "workflow.confirmation_target_resolution_failed" in event_types
    assert "workflow.confirmation_command_invalid" not in event_types
    assert "workflow.confirmation_validated" not in event_types


def test_chat_graph_refund_mutation_validates_persisted_state_before_success() -> None:
    application_service = FailedPersistenceRefundApplicationService()
    eligibility_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This purchase is eligible."),
    ).create_response(
        message="Can I refund this item?",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
    )

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="Confirm invalidate code and issue refund.",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state=eligibility_result.conversation_state,
    )

    assert application_service.request_refund_requests == [PURCHASE_ID]
    assert application_service.issue_refund_requests == []
    assert result.content == (
        "I started the refund process, but I could not verify that the preparation "
        "step was saved. I did not issue funds."
    )
    assert_customer_safe_response(result.content)
    assert result.side_effects == []
    assert result.conversation_state["active_refund_context"]["stage"] == (
        "eligibility_confirmed"
    )

def test_chat_graph_refund_mutation_validates_pending_confirmation_before_execution() -> None:
    application_service = MutableRefundApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message=f"{DIGITAL_CONFIRMATION_COMMAND}.",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state={
            "pending_refund_action": _pending_digital_refund_action(),
        },
    )

    assert application_service.request_refund_requests == [PURCHASE_ID]
    assert application_service.issue_refund_requests == [PURCHASE_ID]
    assert application_service.refund_confirmations[PURCHASE_ID][
        "refund_confirmation_customer_id"
    ] == CUSTOMER_ID
    assert result.conversation_state["pending_refund_action"] is None

def test_chat_graph_refund_mutation_revalidates_stale_confirmation_purchase() -> None:
    application_service = MutableRefundApplicationService()
    _persist_digital_confirmation(
        application_service,
        purchase_id="40000000-0000-4000-8000-000000009999",
    )
    application_service.refund_confirmations[PURCHASE_ID] = {
        **application_service.refund_confirmations[
            "40000000-0000-4000-8000-000000009999"
        ],
        "refund_confirmation_purchase_id": "40000000-0000-4000-8000-000000009999",
    }

    AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message=f"{DIGITAL_CONFIRMATION_COMMAND}.",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state={
            "pending_refund_action": _pending_digital_refund_action(),
        },
    )

    assert application_service.request_refund_requests == [PURCHASE_ID]
    assert application_service.issue_refund_requests == [PURCHASE_ID]
    assert application_service.refund_confirmations[PURCHASE_ID][
        "refund_confirmation_purchase_id"
    ] == PURCHASE_ID

def test_chat_graph_refund_mutation_revalidates_stale_confirmation_customer() -> None:
    application_service = MutableRefundApplicationService()
    _persist_digital_confirmation(
        application_service,
        customer_id="20000000-0000-4000-8000-000000009999",
    )

    AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message=f"{DIGITAL_CONFIRMATION_COMMAND}.",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state={
            "pending_refund_action": _pending_digital_refund_action(),
        },
    )

    assert application_service.request_refund_requests == [PURCHASE_ID]
    assert application_service.issue_refund_requests == [PURCHASE_ID]
    assert application_service.refund_confirmations[PURCHASE_ID][
        "refund_confirmation_customer_id"
    ] == CUSTOMER_ID

def test_chat_graph_refund_mutation_blocks_terminal_issued_state() -> None:
    application_service = MutableRefundApplicationService()
    application_service.issued_purchase_ids.add(PURCHASE_ID)
    _persist_digital_confirmation(application_service)

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message=f"{DIGITAL_CONFIRMATION_COMMAND}.",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state={
            "pending_refund_action": _pending_digital_refund_action("issue_refund"),
        },
    )

    assert result.content == VALIDATION_FAILED_RESPONSE
    assert application_service.request_refund_requests == []
    assert application_service.issue_refund_requests == []

def test_chat_graph_refund_mutation_succeeds_with_valid_persisted_confirmation() -> None:
    application_service = MutableRefundApplicationService()
    _persist_digital_confirmation(application_service)

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message=f"{DIGITAL_CONFIRMATION_COMMAND}.",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state={
            "pending_refund_action": _pending_digital_refund_action(),
        },
    )

    assert application_service.request_refund_requests == [PURCHASE_ID]
    assert application_service.issue_refund_requests == [PURCHASE_ID]
    assert_refund_completion_cleared_state(result.conversation_state)
    assert application_service.refund_confirmations[PURCHASE_ID][
        "refund_confirmation_consumed_by_action"
    ] == "issue_refund"

def test_chat_graph_eligible_physical_refund_sets_pending_refund_action() -> None:
    application_service = MutableRefundApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This physical purchase is eligible."),
    ).create_response(
        message="Can I refund this item?",
        customer_id=CUSTOMER_ID,
        purchase_id=PHYSICAL_PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PHYSICAL_PURCHASE_ID},
    )

    assert result.conversation_state["pending_refund_action"] == {
        "action": "request_refund",
        "purchase_id": PHYSICAL_PURCHASE_ID,
        "product_name": "Keyboard",
        "purchase_type": "physical",
        "required_action": "generate_return_label",
        "confirmation_expected_command": PHYSICAL_CONFIRMATION_COMMAND,
        "refundable_amount_cents": None,
        "refund_outcome": None,
    }

def test_chat_graph_physical_confirmation_with_valid_customer_grants_confirmation() -> None:
    application_service = MutableRefundApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message=PHYSICAL_CONFIRMATION_COMMAND,
        customer_id=CUSTOMER_ID,
        purchase_id=PHYSICAL_PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PHYSICAL_PURCHASE_ID},
        conversation_state={
            "pending_refund_action": _pending_physical_refund_action(),
        },
    )

    assert application_service.request_refund_requests == [PHYSICAL_PURCHASE_ID]
    assert application_service.issue_refund_requests == []
    assert result.conversation_state["pending_refund_action"] is None
    assert application_service.refund_confirmations[PHYSICAL_PURCHASE_ID][
        "refund_confirmation_customer_id"
    ] == CUSTOMER_ID
    assert application_service.refund_confirmations[PHYSICAL_PURCHASE_ID][
        "refund_confirmation_consumed_by_action"
    ] == "request_refund"
    assert_refund_completion_cleared_state(result.conversation_state)

def test_chat_graph_yes_please_after_completed_refund_requires_new_target() -> None:
    application_service = MutableRefundApplicationService()
    completed_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message=PHYSICAL_CONFIRMATION_COMMAND,
        customer_id=CUSTOMER_ID,
        purchase_id=PHYSICAL_PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PHYSICAL_PURCHASE_ID},
        conversation_state={
            "pending_refund_action": _pending_physical_refund_action(),
        },
    )
    application_service.request_refund_requests.clear()
    application_service.issue_refund_requests.clear()

    AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="yes please",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        page_context={"surface": "purchase_history"},
        conversation_state=completed_result.conversation_state,
    )

    assert_refund_completion_cleared_state(completed_result.conversation_state)
    assert application_service.request_refund_requests == []
    assert application_service.issue_refund_requests == []

def test_chat_graph_physical_confirmation_missing_customer_denies_validation() -> None:
    application_service = MutableRefundApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message=PHYSICAL_CONFIRMATION_COMMAND,
        customer_id=None,
        purchase_id=PHYSICAL_PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PHYSICAL_PURCHASE_ID},
        conversation_state={
            "pending_refund_action": _pending_physical_refund_action(),
        },
    )

    assert result.content == VALIDATION_FAILED_RESPONSE
    assert "To continue, reply" not in result.content
    assert application_service.request_refund_requests == []
    assert application_service.issue_refund_requests == []

def test_chat_graph_physical_confirmation_wrong_customer_denies_validation() -> None:
    application_service = StrictCustomerPhysicalApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message=PHYSICAL_CONFIRMATION_COMMAND,
        customer_id="20000000-0000-4000-8000-000000009999",
        purchase_id=PHYSICAL_PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PHYSICAL_PURCHASE_ID},
        conversation_state={
            "pending_refund_action": _pending_physical_refund_action(),
        },
    )

    assert result.content == VALIDATION_FAILED_RESPONSE
    assert "To continue, reply" not in result.content
    assert application_service.request_refund_requests == []
    assert application_service.issue_refund_requests == []

def test_chat_graph_physical_confirmation_for_prepared_return_is_stage_aware() -> None:
    application_service = PreparedPhysicalApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message=PHYSICAL_CONFIRMATION_COMMAND,
        customer_id=CUSTOMER_ID,
        purchase_id=PHYSICAL_PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PHYSICAL_PURCHASE_ID},
        conversation_state={
            "pending_refund_action": _pending_prepared_physical_refund_action(),
        },
    )

    assert result.content == (
        "The return process for Keyboard has already started. The current next "
        "step is carrier acceptance, so I can't issue another start-return "
        "confirmation."
    )
    assert "couldn't verify this purchase" not in result.content
    assert application_service.request_refund_requests == []
    assert application_service.issue_refund_requests == []

def test_chat_graph_refund_confirmation_requires_customer_context() -> None:
    application_service = MutableRefundApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="Confirm invalidate code and issue refund.",
        customer_id=None,
        purchase_id=None,
        conversation_state={
            "pending_refund_action": {
                "action": "request_refund",
                "purchase_id": PURCHASE_ID,
                "product_name": "Design Template Pack",
                "purchase_type": "digital",
            }
        },
    )

    assert result.content == VALIDATION_FAILED_RESPONSE
    assert_customer_safe_response(result.content)
    assert result.conversation_state["pending_refund_action"] is None
    assert application_service.request_refund_requests == []
    assert application_service.issue_refund_requests == []

def test_chat_graph_refund_confirmation_revalidates_pending_purchase_owner() -> None:
    application_service = MutableRefundApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="Confirm invalidate code and issue refund.",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state={
            "pending_refund_action": {
                "action": "request_refund",
                "purchase_id": "40000000-0000-4000-8000-000000009999",
                "product_name": "Forged Product",
                "purchase_type": "digital",
            }
        },
    )

    assert result.content == VALIDATION_FAILED_RESPONSE
    assert_customer_safe_response(result.content)
    assert result.conversation_state["pending_refund_action"] is None
    assert application_service.request_refund_requests == []
    assert application_service.issue_refund_requests == []

def test_chat_graph_refund_mutation_requires_confirmation_before_issue() -> None:
    application_service = MutableRefundApplicationService()
    application_service.prepared_purchase_ids.add(PURCHASE_ID)
    conversation_state = {
        "active_refund_context": {
            "purchase_id": PURCHASE_ID,
            "product_name": "Design Template Pack",
            "purchase_type": "digital",
            "eligible": True,
            "stage": "prepared",
            "next_action": "issue_funds",
            "reason_codes": [],
        }
    }

    pending_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="Close out the refund.",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state=conversation_state,
    )

    assert application_service.issue_refund_requests == []
    assert "Confirm invalidate code and issue refund" in pending_result.content
    assert pending_result.conversation_state["pending_refund_action"] is None
    assert pending_result.conversation_state["active_refund_context"][
        "confirmation_mutation_action"
    ] == "issue_refund"

    confirmed_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="CONFIRM INVALIDATE CODE AND ISSUE REFUND",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state=pending_result.conversation_state,
    )

    assert application_service.issue_refund_requests == [PURCHASE_ID]
    assert confirmed_result.content == (
        "The refund process has completed. You should see $45.00 reflected to "
        "your original payment method within 3-10 business days. Do you have "
        "any other questions, or would you like further assistance?"
    )
    assert_customer_safe_response(confirmed_result.content)
    assert_refund_completion_cleared_state(confirmed_result.conversation_state)

def test_chat_graph_refund_confirmation_command_accepts_punctuation_variation() -> None:
    application_service = MutableRefundApplicationService()
    eligibility_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This purchase is eligible."),
    ).create_response(
        message="Can I refund this item?",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
    )

    confirmed_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="confirm invalidate code & issue refund!",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state=eligibility_result.conversation_state,
    )

    assert application_service.request_refund_requests == [PURCHASE_ID]
    assert application_service.issue_refund_requests == [PURCHASE_ID]
    assert confirmed_result.conversation_state["pending_refund_action"] is None

def test_chat_graph_generic_reply_after_confirmation_command_does_not_mutate() -> None:
    for message in ("Yes", "Proceed", "Do it", "Continue"):
        application_service = MutableRefundApplicationService()
        eligibility_result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("This purchase is eligible."),
        ).create_response(
            message="Can I refund this item?",
            customer_id=CUSTOMER_ID,
            purchase_id=PURCHASE_ID,
            page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        )

        result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("This response should not be used."),
        ).create_response(
            message=message,
            customer_id=CUSTOMER_ID,
            purchase_id=PURCHASE_ID,
            page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
            conversation_state=eligibility_result.conversation_state,
        )

        assert application_service.request_refund_requests == []
        assert result.conversation_state["pending_refund_action"] is None
        assert "Confirm invalidate code and issue refund" in result.content

def test_chat_graph_wrong_confirmation_command_for_purchase_type_is_rejected() -> None:
    application_service = MutableRefundApplicationService()
    eligibility_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This purchase is eligible."),
    ).create_response(
        message="Can I refund this item?",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
    )

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="Confirm cancel and issue refund",
        customer_id=CUSTOMER_ID,
        purchase_id=PURCHASE_ID,
        page_context={"surface": "purchase_detail", "purchase_id": PURCHASE_ID},
        conversation_state=eligibility_result.conversation_state,
    )

    assert application_service.request_refund_requests == []
    assert "Confirm invalidate code and issue refund" in result.content

def test_chat_graph_active_result_set_refund_mutation_requires_single_purchase() -> None:
    application_service = DeveloperToolkitApplicationService()
    first_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("You have paid for 2 subscriptions."),
    ).create_response(
        message="How many subscriptions have I paid for?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )
    second_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Both subscriptions are eligible."),
    ).create_response(
        message="Can I refund them?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    third_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This should not be used."),
    ).create_response(
        message="Let's do that.",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=second_result.conversation_state,
    )

    assert second_result.conversation_state["active_workflow"]["kind"] == (
        "refund_eligibility"
    )
    assert third_result.content == (
        "Please choose one purchase by product name or order number before I "
        "start or issue a refund."
    )
    assert third_result.conversation_state["pending_refund_action"] is None

def test_chat_graph_blocks_refund_workflow_mutations(caplog) -> None:
    application_service = DeveloperToolkitApplicationService()
    model_client = NoToolModelClient("This response should not be used.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Start the refund for the Developer Toolkit.",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == (
        "According to the refund policy, this purchase is eligible for a refund. "
        "To continue, reply:\n\nConfirm cancel and issue refund"
    )
    assert_customer_safe_response(result.content)
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005"
    ]
    assert result.conversation_state["pending_refund_action"] is None
    assert result.conversation_state["active_refund_context"]["purchase_id"] == (
        "40000000-0000-4000-8000-000000000005"
    )
    assert len(model_client.calls) == 1
