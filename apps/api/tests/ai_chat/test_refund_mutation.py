from __future__ import annotations

from refunds_ai_api.services.ai_chat import AIChatService

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
    assert confirmed_result.conversation_state["pending_refund_action"] is None
    assert confirmed_result.conversation_state["active_refund_context"]["stage"] == (
        "issued"
    )
    assert confirmed_result.conversation_state["active_refund_context"]["next_action"] is None
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
    assert confirmed_result.conversation_state["active_refund_context"]["stage"] == (
        "issued"
    )

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

    assert result.content == (
        "Please load a mock customer before continuing the refund process."
    )
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

    assert result.content == (
        "I could not verify that refund request against the active customer "
        "account, so I have not changed the refund process."
    )
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
    assert confirmed_result.conversation_state["pending_refund_action"] is None
    assert confirmed_result.conversation_state["active_refund_context"]["stage"] == (
        "issued"
    )

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
