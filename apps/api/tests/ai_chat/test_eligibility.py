from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat import (
    ACCOUNT_DATA_REQUIRED_RESPONSE,
    CHAT_UNAVAILABLE_RESPONSE,
    CUSTOMER_CONTEXT_REQUIRED_RESPONSE,
    AIChatResult,
    AIChatService,
    ModelToolCall,
)
from refunds_ai_api.services.ai_chat.workflows.classification import WorkflowKind, classify_workflow

from .assertions import assert_customer_safe_response, assert_refund_command_response
from .fakes import (
    CUSTOMER_ID,
    PURCHASE_ID,
    BroadHistoryForDateRangeModelClient,
    DeveloperToolkitApplicationService,
    FailingPurchaseApplicationService,
    FakeApplicationService,
    FakeModelClient,
    FinalFailureModelClient,
    GuardedNoToolChatService,
    LastWeekApplicationService,
    MusicCollectionApplicationService,
    NoToolModelClient,
    ToolCallingModelClient,
    WindowsLicenseApplicationService,
)

GAMING_MOUSE_PURCHASE_ID = "40000000-0000-4000-8000-000000000010"
LAPTOP_STAND_PURCHASE_ID = "40000000-0000-4000-8000-000000000011"


import contextlib
from unittest.mock import patch
from refunds_ai_api.services.ai_chat.workflows.classification import WorkflowClassification
from refunds_ai_api.services.ai_chat.workflows.operations import OperationResolution, WorkflowOperation

@contextlib.contextmanager
def mock_model_assisted_classification(kind, reason, operation):
    mock_classification = WorkflowClassification(
        kind=kind,
        confidence="model_assisted",
        reason=reason,
        conversation_object=None,
        operation=OperationResolution(
            operation=operation,
            confidence="model_assisted",
            reason=reason,
        )
    )
    with patch("refunds_ai_api.services.ai_chat.workflows.classification.classify_workflow", return_value=mock_classification):
        with patch("refunds_ai_api.services.ai_chat.classify_workflow", return_value=mock_classification, create=True):
            with patch("refunds_ai_api.services.ai_chat.nodes.validation.classify_workflow", return_value=mock_classification, create=True):
                with patch("refunds_ai_api.services.ai_chat.nodes.tool_selection.classify_workflow", return_value=mock_classification, create=True):
                    with patch("refunds_ai_api.services.ai_chat.nodes.tool_execution.classify_workflow", return_value=mock_classification, create=True):
                        yield


class GamingMouseApplicationService(FakeApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        purchases = super().list_user_purchases(user_id)
        physical_purchase = purchases[2]
        return [
            {
                **physical_purchase,
                "id": GAMING_MOUSE_PURCHASE_ID,
                "order_number": "RAI-10010",
                "product_name": "Gaming Mouse",
                "sku": "PHY-GAMING-MOUSE",
                "details_url": f"/api/purchases/{GAMING_MOUSE_PURCHASE_ID}/details",
            },
            {
                **physical_purchase,
                "id": LAPTOP_STAND_PURCHASE_ID,
                "order_number": "RAI-10011",
                "product_name": "Laptop Stand",
                "sku": "PHY-LAPTOP-STAND",
                "details_url": f"/api/purchases/{LAPTOP_STAND_PURCHASE_ID}/details",
            },
            *purchases,
        ]

    def get_refund_workflow(self, purchase_id: str) -> dict[str, Any]:
        if purchase_id in {GAMING_MOUSE_PURCHASE_ID, LAPTOP_STAND_PURCHASE_ID}:
            self.refund_workflow_called = True
            self.refund_workflow_requests.append(purchase_id)
            workflow = {
                "purchase_id": purchase_id,
                "purchase_type": "physical",
                "can_enter_refund_workflow": True,
                "can_prepare_refund": True,
                "can_issue_funds": False,
                "refund_stage": "eligible",
                "required_action": "generate_return_label",
                "refundable_amount_cents": 12500,
                "refund_outcome": "full",
                "reasons": [],
                "policy_facts": {
                    "purchase_status": "completed",
                    "carrier_accepted_at": None,
                },
            }
            return workflow
        return super().get_refund_workflow(purchase_id)


def test_chat_graph_get_refund_phrase_routes_to_eligibility_not_policy(
    caplog,
) -> None:
    application_service = MusicCollectionApplicationService()
    first_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("You have paid for 2 subscriptions."),
    ).create_response(
        message="How many subscriptions have I paid for?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("This response should not be used."),
        ).create_response(
            message="Am i able to get a refund for my music collection subscription?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=first_result.conversation_state,
        )

    assert result.content == (
        "I couldn't find a purchase matching 'music collection subscription' "
        "in your account history. Could you confirm the product name, order "
        "number, SKU, or purchase date? I can also help with account, "
        "purchases, orders, refund policies, refund-related questions, and "
        "account activity."
    )
    assert application_service.refund_workflow_requests == []
    classified_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "workflow.classified"
    )
    assert classified_event["data"]["kind"] == "refund_eligibility"
    assert classified_event["data"]["operation"] == "eligibility"
    assert classified_event["data"]["operation_reason"] == (
        "refund_eligibility_phrase_matched"
    )
    blocked_event = next(
        record.event
        for record in caplog.records
        if hasattr(record, "event") and record.event["type"] == "workflow.blocked"
    )
    assert blocked_event["data"]["reason"] == (
        "scoped_product_resolution_type_mismatch"
    )

def test_chat_graph_policy_follow_up_confirmation_promotes_to_eligibility(
    caplog,
) -> None:
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
    policy_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Subscriptions follow the subscription policy."),
    ).create_response(
        message="What is the refund policy for them?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("Both subscriptions are eligible."),
        ).create_response(
            message="yes please, let's check",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=policy_result.conversation_state,
        )

    assert result.content == "Both subscriptions are eligible."
    assert result.conversation_state["active_workflow"]["kind"] == "refund_eligibility"
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005",
        "40000000-0000-4000-8000-000000000004",
    ]
    classified_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "workflow.classified"
    )
    assert classified_event["data"]["operation_reason"] == (
        "policy_follow_up_confirmation_promoted"
    )

def test_policy_follow_up_bare_yes_only_promotes_with_active_object() -> None:
    without_active_object = classify_workflow(
        "yes",
        conversation_state={
            "active_workflow": {
                "kind": "refund_policy",
                "object_kind": None,
                "operation": "policy",
            },
            "selected_policy_scope": "general",
        },
        page_context={},
    )
    with_active_object = classify_workflow(
        "yes",
        conversation_state={
            "active_workflow": {
                "kind": "refund_policy",
                "object_kind": "active_result_set",
                "operation": "policy",
            },
            "active_result_set": {
                "type": "subscriptions",
                "purchase_ids": [
                    "40000000-0000-4000-8000-000000000005",
                    "40000000-0000-4000-8000-000000000004",
                ],
                "label": "your subscriptions",
            },
        },
        page_context={},
    )

    assert without_active_object.kind is not WorkflowKind.REFUND_ELIGIBILITY
    assert with_active_object.kind is WorkflowKind.REFUND_ELIGIBILITY
    assert with_active_object.reason == "active_result_set_refund_query"

def test_chat_graph_explicit_product_without_type_word_can_escape_active_scope() -> None:
    application_service = MusicCollectionApplicationService()
    first_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("You have paid for 2 subscriptions."),
    ).create_response(
        message="How many subscriptions have I paid for?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Music Collection is eligible."),
    ).create_response(
        message="Can I refund Music Collection?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert_refund_command_response(
        result.content,
        "Music Collection is eligible.",
        "Confirm invalidate code and issue refund",
    )
    assert application_service.refund_workflow_requests == [
        MusicCollectionApplicationService.music_collection_id
    ]
    assert result.conversation_state["selected_product"] == "Music Collection"
    assert result.conversation_state["selected_purchase_type"] == "digital"

def test_product_reference_eligibility_uses_resolved_purchase_over_stale_scope() -> None:
    application_service = MusicCollectionApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Music Collection is eligible."),
    ).create_response(
        message="Can I refund Music Collection?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state={
            "selected_purchase_ids": ["missing-purchase-id"],
            "active_result_set": {
                "type": "subscriptions",
                "purchase_ids": ["missing-purchase-id"],
                "label": "your subscriptions",
            },
        },
    )

    assert application_service.refund_workflow_requests == [
        MusicCollectionApplicationService.music_collection_id
    ]
    assert result.conversation_state["selected_refund_purchase_ids"] == [
        MusicCollectionApplicationService.music_collection_id
    ]
    assert result.conversation_state["selected_refund_context"] == "selected_purchase"

def test_empty_eligibility_result_retries_active_purchase() -> None:
    application_service = FakeApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Design Template Pack is eligible."),
    ).create_response(
        message="Can I refund those?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state={
            "selected_purchase_ids": ["missing-purchase-id"],
            "active_purchase": {
                "purchase_id": PURCHASE_ID,
                "product_name": "Design Template Pack",
                "purchase_type": "digital",
            },
            "active_result_set": {
                "type": "digital",
                "purchase_ids": ["missing-purchase-id"],
                "label": "your digital purchases",
            },
        },
    )

    assert application_service.refund_workflow_requests == [PURCHASE_ID]
    assert result.content.startswith("Design Template Pack is eligible.")
    assert result.conversation_state["selected_refund_purchase_ids"] == [PURCHASE_ID]

def test_empty_eligibility_result_without_recoverable_purchase_returns_clarification() -> None:
    application_service = FakeApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This should not be used."),
    ).create_response(
        message="Can I refund those?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state={
            "selected_purchase_ids": ["missing-purchase-id"],
            "active_result_set": {
                "type": "digital",
                "purchase_ids": ["missing-purchase-id"],
                "label": "your digital purchases",
            },
        },
    )

    assert result.content == (
        "I could not determine which purchase to check. Please choose one "
        "purchase by product name or order number."
    )
    assert application_service.refund_workflow_requests == []

def test_refund_denial_explanation_routes_to_eligibility_result() -> None:
    application_service = FakeApplicationService()
    first_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Icon Set is not eligible."),
    ).create_response(
        message="Can I refund Icon Set?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )
    application_service.refund_workflow_requests.clear()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient(
            "Icon Set is blocked because the digital entitlement was redeemed."
        ),
    ).create_response(
        message="Why can't I get a refund for it?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert result.conversation_state["active_workflow"]["kind"] == "refund_eligibility"
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000002"
    ]
    assert "digital entitlement was redeemed" in result.content

def test_chat_graph_digital_result_set_follow_up_routes_to_eligibility() -> None:
    application_service = FakeApplicationService()
    first_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("You have 2 digital purchases."),
    ).create_response(
        message="How many digital purchases have I made?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )
    second_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("your digital purchases: Design Template Pack, Icon Set."),
    ).create_response(
        message="List them.",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    third_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("One digital purchase is eligible."),
    ).create_response(
        message="Can I refund them?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=second_result.conversation_state,
    )

    assert third_result.conversation_state["active_workflow"]["kind"] == (
        "refund_eligibility"
    )
    assert third_result.conversation_state["active_workflow"]["object_kind"] == (
        "active_result_set"
    )
    assert third_result.conversation_state["active_workflow"]["operation"] == (
        "eligibility"
    )
    assert application_service.refund_workflow_requests == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
    ]

def test_chat_graph_selected_purchase_follow_up_routes_to_single_eligibility() -> None:
    application_service = LastWeekApplicationService()
    first_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Here are your purchases from last week."),
    ).create_response(
        message="Show my purchases from last week.",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )
    second_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("The first purchase was Design Template Pack."),
    ).create_response(
        message="What was the first one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    third_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Design Template Pack is eligible."),
    ).create_response(
        message="Is it refundable?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=second_result.conversation_state,
    )

    assert third_result.conversation_state["active_workflow"]["kind"] == (
        "refund_eligibility"
    )
    assert third_result.conversation_state["active_workflow"]["object_kind"] == (
        "active_purchase"
    )
    assert application_service.refund_workflow_requests == [PURCHASE_ID]

def test_chat_graph_active_result_set_policy_follow_up_routes_to_policy() -> None:
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
        model_client=NoToolModelClient("Subscriptions follow the subscription policy."),
    ).create_response(
        message="What is the policy for them?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert second_result.conversation_state["active_workflow"]["kind"] == "refund_policy"
    assert second_result.conversation_state["active_workflow"]["object_kind"] == (
        "active_result_set"
    )
    assert second_result.conversation_state["active_workflow"]["operation"] == "policy"
    assert second_result.conversation_state["selected_policy_scope"] == "product_type"
    assert second_result.conversation_state["selected_purchase_type"] == "subscription"

def test_chat_graph_digital_result_set_demonstrative_policy_uses_digital_policy(
    caplog,
) -> None:
    application_service = FakeApplicationService()
    first_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("You have 2 digital purchases."),
    ).create_response(
        message="How many digital purchases have I made?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        second_result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("Digital products can be refunded within 15 days."),
        ).create_response(
            message="What is the refund policy for these types of products?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=first_result.conversation_state,
        )

    assert second_result.conversation_state["active_workflow"]["kind"] == "refund_policy"
    assert second_result.conversation_state["active_workflow"]["object_kind"] == (
        "active_result_set"
    )
    assert second_result.conversation_state["active_workflow"]["object_label"] == (
        "your digital purchases"
    )
    assert second_result.conversation_state["active_workflow"]["operation"] == "policy"
    assert second_result.conversation_state["selected_policy_scope"] == "product_type"
    assert second_result.conversation_state["selected_purchase_type"] == "digital"
    classified_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "workflow.classified"
    )
    assert classified_event["data"]["kind"] == "refund_policy"
    assert classified_event["data"]["reason"] == "active_result_set_policy"
    assert classified_event["data"]["object"] == "active_result_set"
    assert classified_event["data"]["object_label"] == "your digital purchases"
    assert classified_event["data"]["operation"] == "policy"
    completed_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "tool_call.completed"
    )
    assert completed_event["data"]["tool_name"] == "get_refund_policy"
    assert completed_event["data"]["result"]["purchase_type"] == "digital"
    assert not any(
        record.event["type"] == "response.blocked"
        and record.event["data"].get("reason") == "product_reference_unresolved"
        for record in caplog.records
    )

def test_chat_graph_subscription_result_set_demonstrative_policy_uses_subscription_policy(
    caplog,
) -> None:
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

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        second_result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("Subscriptions follow the subscription policy."),
        ).create_response(
            message="What is the refund policy for these types of products?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=first_result.conversation_state,
        )

    assert second_result.conversation_state["active_workflow"]["object_kind"] == (
        "active_result_set"
    )
    assert second_result.conversation_state["selected_purchase_type"] == "subscription"
    completed_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "tool_call.completed"
    )
    assert completed_event["data"]["tool_name"] == "get_refund_policy"
    assert completed_event["data"]["result"]["purchase_type"] == "subscription"

def test_chat_graph_generic_demonstrative_policy_uses_active_result_set(
    caplog,
) -> None:
    application_service = FakeApplicationService()
    first_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("You have 2 digital purchases."),
    ).create_response(
        message="How many digital purchases have I made?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        second_result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("Digital products can be refunded within 15 days."),
        ).create_response(
            message="What is the policy for those products?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=first_result.conversation_state,
        )

    assert second_result.conversation_state["active_workflow"]["kind"] == "refund_policy"
    assert second_result.conversation_state["active_workflow"]["object_kind"] == (
        "active_result_set"
    )
    assert second_result.conversation_state["selected_purchase_type"] == "digital"
    assert not any(
        record.event["type"] == "response.blocked"
        and record.event["data"].get("product_reference") == "those products"
        for record in caplog.records
    )

def test_chat_graph_concrete_product_policy_still_uses_product_reference() -> None:
    result = AIChatService(
        application_service=WindowsLicenseApplicationService(),
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Windows License follows the digital policy."),
    ).create_response(
        message="What is the policy for Windows License?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert result.conversation_state["active_workflow"]["kind"] == "refund_policy"
    assert result.conversation_state["active_workflow"]["object_kind"] == (
        "product_reference"
    )
    assert result.conversation_state["active_workflow"]["object_label"] == (
        "Windows License"
    )
    assert result.conversation_state["selected_product"] == "Windows License"
    assert result.conversation_state["selected_purchase_type"] == "digital"

def test_chat_graph_demonstrative_policy_without_active_state_is_not_product_reference(
    caplog,
) -> None:
    model_client = NoToolModelClient("Here is the general refund policy.")
    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = AIChatService(
            application_service=FakeApplicationService(),
            model="gpt-5.4-mini",
            model_client=model_client,
        ).create_response(
            message="What is the policy for these products?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.conversation_state["active_workflow"] is None
    classified_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "workflow.classified"
    )
    assert classified_event["data"]["kind"] == "off_domain"
    assert classified_event["data"]["object"] == "unknown"
    assert classified_event["data"]["operation"] == "policy"
    assert not any(
        record.event["type"] == "response.blocked"
        and record.event["data"].get("product_reference") == "these products"
        for record in caplog.records
    )

def test_chat_graph_account_fact_list_follow_up_stays_account_fact() -> None:
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
        model_client=NoToolModelClient("Here are your subscriptions."),
    ).create_response(
        message="List them.",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert second_result.conversation_state["active_workflow"]["kind"] == "account_fact"
    assert second_result.conversation_state["active_workflow"]["object_kind"] == (
        "active_result_set"
    )
    assert second_result.conversation_state["active_workflow"]["operation"] == "list"

def test_workflow_lookup_routes_digital_count_as_purchase_type_account_fact() -> None:
    classification = classify_workflow(
        "How many digital purchases have I made?",
        conversation_state={},
        page_context={},
    )

    assert classification.kind is WorkflowKind.ACCOUNT_FACT
    assert classification.conversation_object.kind.value == "purchase_type"
    assert classification.conversation_object.purchase_type == "digital"
    assert classification.operation.operation.value == "count"

def test_chat_graph_model_history_conflict_overridden_to_result_set_eligibility(
    caplog,
) -> None:
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
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-history-conflict",
            name="get_customer_purchase_history",
            arguments={},
        ),
        "Both subscriptions are eligible.",
    )

    with mock_model_assisted_classification(
        WorkflowKind.REFUND_ELIGIBILITY,
        "eligibility_lookup_intent",
        WorkflowOperation.ELIGIBILITY,
    ):
        with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
            result = AIChatService(
                application_service=application_service,
                model="gpt-5.4-mini",
                model_client=model_client,
            ).create_response(
                message="Am I able to refund them?",
                customer_id=CUSTOMER_ID,
                purchase_id=None,
                conversation_state=first_result.conversation_state,
            )

    assert result.conversation_state["active_workflow"]["kind"] == "refund_eligibility"
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005",
        "40000000-0000-4000-8000-000000000004",
    ]
    override_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "workflow.tool_overridden"
    )
    assert override_event["data"]["requested_tool_name"] == "get_customer_purchase_history"
    assert override_event["data"]["tool_name"] == "get_refund_eligibility"

def test_chat_graph_uses_current_detail_page_for_policy_context(caplog) -> None:
    model_client = NoToolModelClient("Digital products can be refunded within 15 days.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for this item?",
            customer_id=CUSTOMER_ID,
            purchase_id=PURCHASE_ID,
            page_context={
                "surface": "purchase_detail",
                "purchase_id": PURCHASE_ID,
            },
        )

    assert result.content == "Digital products can be refunded within 15 days."
    assert result.conversation_state["selected_product"] == "Design Template Pack"
    assert result.conversation_state["selected_purchase_id"] == PURCHASE_ID
    assert result.conversation_state["selected_purchase_type"] == "digital"
    assert result.conversation_state["current_page"] == {
        "surface": "purchase_detail",
        "purchase": {
            "id": PURCHASE_ID,
            "product_name": "Design Template Pack",
            "sku": "DIG-TEMPLATE-001",
            "order_number": "RAI-10001",
            "purchase_type": "digital",
        },
    }
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_refund_policy",
        "reason": "policy_lookup_intent",
        "scope": "product_type",
        "purchase_type": "digital",
    }
    final_page_message = next(
        message
        for message in model_client.calls[1]["messages"]
        if message["content"].startswith("Current page reference:")
    )
    assert "Design Template Pack" in final_page_message["content"]
    assert "DIG-TEMPLATE-001" in final_page_message["content"]

def test_chat_graph_routes_general_policy_lookup(caplog) -> None:
    model_client = NoToolModelClient("Refund policy depends on product type.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is your refund policy?",
            customer_id=None,
            purchase_id=None,
        )

    assert result.content == "Refund policy depends on product type."
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_refund_policy",
        "reason": "policy_lookup_intent",
        "scope": "general",
        "purchase_type": None,
    }

def test_chat_graph_routes_funds_release_policy_lookup(caplog) -> None:
    model_client = NoToolModelClient("Most refunds are completed within 3-10 business days.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="When do funds get released for a physical return?",
            customer_id=None,
            purchase_id=None,
        )

    assert result.content == "Most refunds are completed within 3-10 business days."
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_refund_policy",
        "reason": "policy_lookup_intent",
        "scope": "funds_release",
        "purchase_type": "physical",
    }

def test_chat_graph_routes_digital_group_eligibility(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient(
        "Design Template Pack is eligible; Icon Set is blocked because it was redeemed."
    )
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Which of my digital products can be refunded?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == (
        "Design Template Pack is eligible; Icon Set is blocked because it was redeemed."
    )
    assert application_service.refund_workflow_requests == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
    ]
    assert result.conversation_state["selected_refund_purchase_ids"] == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
    ]
    assert result.conversation_state["selected_refund_context"] == "digital"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_refund_eligibility",
        "reason": "eligibility_lookup_intent",
        "purchase_ids": [
            PURCHASE_ID,
            "40000000-0000-4000-8000-000000000002",
        ],
        "context": "digital",
    }
    final_tool_message = next(
        message
        for message in model_client.calls[1]["messages"]
        if message["content"].startswith("Read-only account tool result:")
    )
    assert "digital_entitlement_redeemed" in final_tool_message["content"]

def test_chat_graph_group_eligibility_clears_active_refund_context(
    caplog,
) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("One digital purchase is eligible and one is blocked.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Which of my digital products can be refunded?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "active_refund_context": {
                    "purchase_id": "40000000-0000-4000-8000-000000000003",
                    "product_name": "Keyboard",
                    "purchase_type": "physical",
                    "eligible": True,
                    "stage": "awaiting_return_label",
                    "next_action": "generate_return_label",
                    "reason_codes": [],
                }
            },
        )

    assert result.content == "One digital purchase is eligible and one is blocked."
    assert result.conversation_state["active_refund_context"] is None
    assert result.conversation_state["selected_refund_purchase_ids"] == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
    ]

def test_chat_graph_overrides_broad_history_tool_for_eligibility_intent(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = BroadHistoryForDateRangeModelClient("Only refund eligibility was used.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with mock_model_assisted_classification(
        WorkflowKind.REFUND_ELIGIBILITY,
        "eligibility_lookup_intent",
        WorkflowOperation.ELIGIBILITY,
    ):
        with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
            result = chat_service.create_response(
                message="Which of my digital products can be refunded?",
                customer_id=CUSTOMER_ID,
                purchase_id=None,
            )

    assert result.content == "Only refund eligibility was used."
    assert application_service.refund_workflow_requests == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
    ]
    overridden_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.overridden"
    )
    assert overridden_event["data"] == {
        "requested_tool_name": "get_customer_purchase_history",
        "tool_name": "get_refund_eligibility",
        "reason": "eligibility_lookup_intent",
        "purchase_ids": [
            PURCHASE_ID,
            "40000000-0000-4000-8000-000000000002",
        ],
        "context": "digital",
    }

def test_chat_graph_routes_all_purchase_eligibility(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("Three purchases are eligible and one is blocked.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Which purchases can be refunded?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == (
        "I could not determine which purchase to check. Please choose one "
        "purchase by product name or order number."
    )
    assert application_service.refund_workflow_requests == []
    assert len(model_client.calls) == 0

def test_chat_graph_routes_specific_product_eligibility(caplog) -> None:
    application_service = DeveloperToolkitApplicationService()
    model_client = NoToolModelClient("Developer Toolkit is eligible under subscription rules.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Can I refund the Developer Toolkit?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert_refund_command_response(
        result.content,
        "Developer Toolkit is eligible under subscription rules.",
        "Confirm cancel and issue refund",
    )
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005"
    ]
    assert result.conversation_state["selected_product"] == "Developer Toolkit"
    assert result.conversation_state["selected_purchase_id"] == (
        "40000000-0000-4000-8000-000000000005"
    )
    assert result.conversation_state["selected_purchase_type"] == "subscription"
    assert result.conversation_state["selected_refund_purchase_ids"] == [
        "40000000-0000-4000-8000-000000000005"
    ]
    assert result.conversation_state["selected_refund_context"] == "selected_purchase"
    final_tool_message = next(
        message
        for message in model_client.calls[1]["messages"]
        if message["content"].startswith("Read-only account tool result:")
    )
    assert "cancel_subscription" in final_tool_message["content"]

def test_chat_graph_executes_model_requested_eligibility_tool(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-eligibility",
            name="get_refund_eligibility",
            arguments={"purchase_ids": [PURCHASE_ID], "context": "model_requested"},
        ),
        "The purchase is eligible.",
    )
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with mock_model_assisted_classification(
        WorkflowKind.REFUND_ELIGIBILITY,
        "eligibility_lookup_intent",
        WorkflowOperation.ELIGIBILITY,
    ):
        with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
            result = chat_service.create_response(
                message="Please check refund handling.",
                customer_id=CUSTOMER_ID,
                purchase_id=None,
            )

    assert_refund_command_response(
        result.content,
        "The purchase is eligible.",
        "Confirm invalidate code and issue refund",
    )
    assert application_service.refund_workflow_requests == [PURCHASE_ID]
    completed_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "tool_call.completed"
    )
    assert completed_event["data"]["tool_name"] == "get_refund_eligibility"

def test_chat_graph_overrides_model_requested_eligibility_arguments(caplog) -> None:
    application_service = DeveloperToolkitApplicationService()
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-eligibility",
            name="get_refund_eligibility",
            arguments={"purchase_ids": [PURCHASE_ID], "context": "model_requested"},
        ),
        "Developer Toolkit is eligible.",
    )
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with mock_model_assisted_classification(
        WorkflowKind.REFUND_ELIGIBILITY,
        "eligibility_lookup_intent",
        WorkflowOperation.ELIGIBILITY,
    ):
        with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
            result = chat_service.create_response(
                message="Can I refund the Developer Toolkit?",
                customer_id=CUSTOMER_ID,
                purchase_id=None,
            )

    assert_refund_command_response(
        result.content,
        "Developer Toolkit is eligible.",
        "Confirm cancel and issue refund",
    )
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005"
    ]
    overridden_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.overridden"
    )
    assert overridden_event["data"]["reason"] == "resolved_eligibility_context"
    assert overridden_event["data"]["purchase_ids"] == [
        "40000000-0000-4000-8000-000000000005"
    ]

def test_chat_graph_ignores_invalid_model_eligibility_arguments(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-eligibility",
            name="get_refund_eligibility",
            arguments={"purchase_ids": [], "context": "model_requested"},
        ),
        "I can only help with account topics.",
    )
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with mock_model_assisted_classification(
        WorkflowKind.REFUND_ELIGIBILITY,
        "eligibility_lookup_intent",
        WorkflowOperation.ELIGIBILITY,
    ):
        with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
            result = chat_service.create_response(
                message="Hello",
                customer_id=CUSTOMER_ID,
                purchase_id=None,
            )

    assert result.content == "I can only help with account topics."
    assert application_service.refund_workflow_requests == []
    ignored_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.ignored"
    )
    assert ignored_event["data"]["tool_name"] == "get_refund_eligibility"

def test_chat_graph_resolves_fuzzy_product_eligibility(caplog) -> None:
    application_service = DeveloperToolkitApplicationService()
    model_client = NoToolModelClient("Developer Toolkit is eligible.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Can I refund the devloper toolkt?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert_refund_command_response(
        result.content,
        "Developer Toolkit is eligible.",
        "Confirm cancel and issue refund",
    )
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005"
    ]
    assert result.conversation_state["selected_product"] == "Developer Toolkit"

def test_chat_graph_unresolved_product_eligibility_asks_for_clarification(
    caplog,
) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("This response should not be used.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Can I refund the Developer Toolkit?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == (
        "I couldn't find a purchase matching 'Developer Toolkit' in your account history. "
        "Could you confirm the product name, order number, SKU, or purchase date? "
        "I can also help with account, purchases, orders, refund policies, "
        "refund-related questions, and account activity."
    )
    assert application_service.refund_workflow_requests == []
    assert len(model_client.calls) == 0
    assert result.conversation_state["selected_purchase_type"] is None

def test_chat_graph_resolves_latest_eligibility_inside_selected_set(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("The latest selected digital purchase is blocked.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What about the latest one?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "selected_refund_purchase_ids": [
                    PURCHASE_ID,
                    "40000000-0000-4000-8000-000000000002",
                ],
                "selected_refund_context": "digital",
                "selected_purchase_ids": [
                    PURCHASE_ID,
                    "40000000-0000-4000-8000-000000000002",
                ],
            },
        )

    assert result.content == "The latest selected digital purchase is blocked."
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000002"
    ]
    assert result.conversation_state["selected_product"] == "Icon Set"
    assert result.conversation_state["selected_refund_purchase_ids"] == [
        "40000000-0000-4000-8000-000000000002"
    ]
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"]["context"] == "selected_set"

def test_chat_graph_uses_current_detail_page_for_eligibility(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("This item is eligible to begin refund handling.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Can I refund this item?",
            customer_id=CUSTOMER_ID,
            purchase_id=PURCHASE_ID,
            page_context={
                "surface": "purchase_detail",
                "purchase_id": PURCHASE_ID,
            },
        )

    assert_refund_command_response(
        result.content,
        "This item is eligible to begin refund handling.",
        "Confirm invalidate code and issue refund",
    )
    assert application_service.refund_workflow_requests == [PURCHASE_ID]
    assert result.conversation_state["selected_product"] == "Design Template Pack"
    assert result.conversation_state["selected_refund_context"] == "current_page"

def test_chat_graph_uses_current_detail_page_for_this_product_policy(
    caplog,
) -> None:
    application_service = DeveloperToolkitApplicationService()
    model_client = NoToolModelClient("Digital products can be refunded within 15 days.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the return policy for this product?",
            customer_id=CUSTOMER_ID,
            purchase_id=PURCHASE_ID,
            page_context={
                "surface": "purchase_detail",
                "purchase_id": PURCHASE_ID,
            },
            conversation_state={
                "selected_purchase_id": "40000000-0000-4000-8000-000000000005",
                "selected_product": "Developer Toolkit",
                "selected_purchase_type": "subscription",
                "selected_purchase_ids": [
                    "40000000-0000-4000-8000-000000000005",
                ],
            },
        )

    assert result.content == "Digital products can be refunded within 15 days."
    assert result.conversation_state["selected_product"] == "Design Template Pack"
    assert result.conversation_state["selected_purchase_id"] == PURCHASE_ID
    assert result.conversation_state["selected_purchase_type"] == "digital"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"]["purchase_type"] == "digital"

def test_chat_graph_stores_active_refund_context_after_single_eligibility(
    caplog,
) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("Keyboard is eligible for a return label.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Can I refund the Keyboard?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert_refund_command_response(
        result.content,
        "Keyboard is eligible for a return label.",
        "Confirm start return and issue label",
    )
    assert result.conversation_state["active_refund_context"] == {
        "purchase_id": "40000000-0000-4000-8000-000000000003",
        "product_name": "Keyboard",
        "purchase_type": "physical",
        "eligible": True,
        "stage": "awaiting_return_label",
        "next_action": "generate_return_label",
        "reason_codes": [],
        "confirmation_command": "Confirm start return and issue label",
        "confirmation_backend_action": "generate_return_label",
        "confirmation_mutation_action": "request_refund",
        "confirmation_steps": [
            "start the return",
            "generate the return label",
        ],
    }

def test_chat_graph_follow_up_return_label_uses_active_refund_context(
    caplog,
) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("This response should not be used.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Can you generate a return label please. I'd like to return the item.",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "active_refund_context": {
                    "purchase_id": "40000000-0000-4000-8000-000000000003",
                    "product_name": "Keyboard",
                    "purchase_type": "physical",
                    "eligible": True,
                    "stage": "awaiting_return_label",
                    "next_action": "generate_return_label",
                    "reason_codes": [],
                }
            },
        )

    assert result.content == (
        "To continue, reply:\n\nConfirm start return and issue label"
    )
    assert_customer_safe_response(result.content)
    assert application_service.purchase_requests == []
    assert application_service.refund_workflow_requests == []
    assert len(model_client.calls) == 0
    confirmation_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "workflow.confirmation_command_invalid"
    )
    assert confirmation_event["data"]["purchase_id"] == (
        "40000000-0000-4000-8000-000000000003"
    )

def test_chat_graph_follow_up_workflow_without_active_context_requires_confirmation(
    caplog,
) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("This response should not be used.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Please generate the return label.",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == (
        "Please choose one purchase by product name or order number before I "
        "start or issue a refund."
    )
    assert application_service.purchase_requests == []
    assert application_service.refund_workflow_requests == []
    assert len(model_client.calls) == 0

def test_chat_graph_different_explicit_product_replaces_active_refund_context(
    caplog,
) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("Design Template Pack is eligible.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Can I refund the Design Template Pack?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "active_refund_context": {
                    "purchase_id": "40000000-0000-4000-8000-000000000003",
                    "product_name": "Keyboard",
                    "purchase_type": "physical",
                    "eligible": True,
                    "stage": "awaiting_return_label",
                    "next_action": "generate_return_label",
                    "reason_codes": [],
                }
            },
        )

    assert_refund_command_response(
        result.content,
        "Design Template Pack is eligible.",
        "Confirm invalidate code and issue refund",
    )
    assert result.conversation_state["active_refund_context"] == {
        "purchase_id": PURCHASE_ID,
        "product_name": "Design Template Pack",
        "purchase_type": "digital",
        "eligible": True,
        "stage": "eligibility_confirmed",
        "next_action": "invalidate_digital_entitlement",
        "reason_codes": [],
        "confirmation_command": "Confirm invalidate code and issue refund",
        "confirmation_backend_action": "invalidate_code",
        "confirmation_mutation_action": "request_refund",
        "confirmation_steps": [
            "invalidate the issued code",
            "calculate the final refund",
            "issue the refund",
        ],
    }

def test_chat_graph_explicit_product_eligibility_escapes_selected_set(caplog) -> None:
    application_service = DeveloperToolkitApplicationService()
    model_client = NoToolModelClient("Developer Toolkit is eligible as a subscription.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Can I refund the Developer Toolkit?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "selected_purchase_type": "digital",
                "selected_purchase_ids": [
                    PURCHASE_ID,
                    "40000000-0000-4000-8000-000000000002",
                ],
                "selected_refund_purchase_ids": [
                    PURCHASE_ID,
                    "40000000-0000-4000-8000-000000000002",
                ],
                "selected_refund_context": "digital",
                "selected_scope_label": "your digital purchases",
            },
        )

    assert_refund_command_response(
        result.content,
        "Developer Toolkit is eligible as a subscription.",
        "Confirm cancel and issue refund",
    )
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005"
    ]
    assert result.conversation_state["selected_product"] == "Developer Toolkit"
    assert result.conversation_state["selected_purchase_type"] == "subscription"
    assert result.conversation_state["selected_purchase_ids"] == [
        "40000000-0000-4000-8000-000000000005"
    ]
    assert result.conversation_state["selected_scope_label"] is None

def test_chat_graph_refund_phrase_with_typo_resolves_customer_purchase(caplog) -> None:
    application_service = GamingMouseApplicationService()
    model_client = NoToolModelClient("Gaming Mouse is eligible for a return label.")

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=model_client,
        ).create_response(
            message=(
                "Id like to get a refund for the gamining mouse i purchased "
                "back in june."
            ),
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "active_purchase": {
                    "purchase_id": LAPTOP_STAND_PURCHASE_ID,
                    "product_name": "Laptop Stand",
                    "purchase_type": "physical",
                }
            },
        )

    assert result.conversation_state["selected_purchase_id"] == GAMING_MOUSE_PURCHASE_ID
    assert result.conversation_state["selected_product"] == "Gaming Mouse"
    assert result.conversation_state["pending_refund_product_reference"] is None
    assert application_service.refund_workflow_requests == [GAMING_MOUSE_PURCHASE_ID]
    classified_event = next(
        record.event for record in caplog.records if record.event["type"] == "workflow.classified"
    )
    assert classified_event["data"]["kind"] == "refund_eligibility"
    assert classified_event["data"]["object_label"] == "gamining mouse"

def test_chat_graph_pending_product_reference_follow_up_continues_refund_lookup() -> None:
    application_service = GamingMouseApplicationService()
    first_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("This response should not be used."),
    ).create_response(
        message="Can I refund the Studio Monitor?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert first_result.conversation_state["pending_refund_product_reference"] == {
        "product_reference": "Studio Monitor",
        "reason": "product_reference_unresolved",
    }
    application_service.refund_workflow_requests.clear()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Gaming Mouse is eligible for a return label."),
    ).create_response(
        message="the gaming mouse",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert result.conversation_state["selected_purchase_id"] == GAMING_MOUSE_PURCHASE_ID
    assert result.conversation_state["pending_refund_product_reference"] is None
    assert application_service.refund_workflow_requests == [GAMING_MOUSE_PURCHASE_ID]

def test_chat_graph_model_account_validation_request_does_not_override_refund_lookup(
    caplog,
) -> None:
    application_service = GamingMouseApplicationService()
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-account-validation",
            name="validate_customer_account",
            arguments={},
        ),
        "Gaming Mouse is eligible for a return label.",
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=model_client,
        ).create_response(
            message=(
                "Id like to get a refund for the gamining mouse i purchased "
                "back in june."
            ),
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.conversation_state["selected_purchase_id"] == GAMING_MOUSE_PURCHASE_ID
    assert application_service.refund_workflow_requests == [GAMING_MOUSE_PURCHASE_ID]
    assert not any(
        record.event["type"] == "tool_call.completed"
        and record.event["data"]["tool_name"] == "validate_customer_account"
        for record in caplog.records
    )

def test_chat_graph_explicit_music_collection_switches_from_completed_physical_refund() -> None:
    application_service = MusicCollectionApplicationService()

    result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Music Collection is eligible."),
    ).create_response(
        message="Can we refund the Music Collection?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state={
            "selected_purchase_type": "physical",
            "selected_scope_label": "your physical purchases",
            "selected_purchase_ids": ["40000000-0000-4000-8000-000000000003"],
            "active_result_set": {
                "type": "purchase_history",
                "purchase_ids": ["40000000-0000-4000-8000-000000000003"],
                "label": "your physical purchases",
            },
            "active_purchase": {
                "purchase_id": "40000000-0000-4000-8000-000000000003",
                "product_name": "Gaming Mouse",
                "purchase_type": "physical",
            },
            "active_refund_context": {
                "purchase_id": "40000000-0000-4000-8000-000000000003",
                "product_name": "Gaming Mouse",
                "purchase_type": "physical",
                "eligible": True,
                "stage": "prepared",
                "next_action": "await_carrier_acceptance",
                "reason_codes": [],
                "confirmation_closed": True,
            },
            "refund_context_status": "completed",
            "last_completed_refund": {
                "purchase_id": "40000000-0000-4000-8000-000000000003",
                "product_name": "Gaming Mouse",
                "purchase_type": "physical",
                "action": "request_refund",
                "final_stage": "prepared",
                "required_action": "await_carrier_acceptance",
            },
        },
    )

    assert result.conversation_state["selected_purchase_id"] == (
        MusicCollectionApplicationService.music_collection_id
    )
    assert result.conversation_state["selected_product"] == "Music Collection"
    assert result.conversation_state["selected_purchase_type"] == "digital"
    assert result.conversation_state["selected_scope_label"] is None
    assert result.conversation_state["active_result_set"] is None
    assert result.conversation_state["active_purchase"] == {
        "purchase_id": MusicCollectionApplicationService.music_collection_id,
        "product_name": "Music Collection",
        "purchase_type": "digital",
    }
    assert application_service.refund_workflow_requests == [
        MusicCollectionApplicationService.music_collection_id
    ]

def test_chat_graph_missing_customer_blocks_eligibility_lookup() -> None:
    model_client = NoToolModelClient("This response should not be used.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    result = chat_service.create_response(
        message="Which purchases can be refunded?",
        customer_id=None,
        purchase_id=None,
    )

    assert result.content == CUSTOMER_CONTEXT_REQUIRED_RESPONSE
    assert len(model_client.calls) == 0

def test_chat_graph_overrides_broad_history_tool_for_date_range_intent(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = BroadHistoryForDateRangeModelClient("You made 4 purchases last week.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with mock_model_assisted_classification(
        WorkflowKind.ACCOUNT_FACT,
        "date_range_intent",
        WorkflowOperation.LIST,
    ):
        with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
            result = chat_service.create_response(
                message="How many purchases did I make last week?",
                customer_id=CUSTOMER_ID,
                purchase_id=None,
            )

    assert result.content == "You made 4 purchases last week."
    assert application_service.purchase_requests == [CUSTOMER_ID]
    event_types = [record.event["type"] for record in caplog.records]
    assert "tool_call.overridden" in event_types
    overridden_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.overridden"
    )
    assert overridden_event["data"] == {
        "requested_tool_name": "get_customer_purchase_history",
        "tool_name": "get_purchase_history_by_date_range",
        "reason": "date_range_intent",
        "start_date": "2026-06-28",
        "end_date": "2026-07-04",
        "timezone": "America/Chicago",
    }
    final_tool_message = next(
        message
        for message in model_client.calls[1]["messages"]
        if message["content"].startswith("Read-only account tool result:")
    )
    assert "get_purchase_history_by_date_range" in final_tool_message["content"]
    assert "get_customer_purchase_history" not in final_tool_message["content"]

def test_chat_graph_executes_model_requested_threshold_tool(caplog) -> None:
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-threshold",
            name="get_purchase_count_by_amount_threshold",
            arguments={"threshold_cents": 10_000, "comparison": "gte"},
        ),
        "You made 1 purchase at or above $100.",
    )
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="How many purchases did I make at least $100?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "You made 1 purchase at or above $100."
    completed_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "tool_call.completed"
    )
    assert completed_event["data"]["tool_name"] == "get_purchase_count_by_amount_threshold"
    assert result.conversation_state["selected_purchase_ids"] == [
        "40000000-0000-4000-8000-000000000003"
    ]

def test_chat_graph_ignores_invalid_model_threshold_arguments(caplog) -> None:
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-threshold",
            name="get_purchase_count_by_amount_threshold",
            arguments={"threshold_cents": -1, "comparison": "gte"},
        ),
        "You made 4 purchases.",
    )
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with mock_model_assisted_classification(
        WorkflowKind.ACCOUNT_FACT,
        "amount_threshold_intent",
        WorkflowOperation.COUNT,
    ):
        with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
            result = chat_service.create_response(
                message="Summarize my purchases",
                customer_id=CUSTOMER_ID,
                purchase_id=None,
            )

    assert result.content == "You made 4 purchases."
    ignored_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.ignored"
    )
    assert ignored_event["data"]["tool_name"] == "get_purchase_count_by_amount_threshold"

def test_chat_graph_executes_model_requested_date_range_tool(caplog) -> None:
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-date-range",
            name="get_purchase_history_by_date_range",
            arguments={
                "start_date": "2026-06-20",
                "end_date": "2026-06-22",
                "timezone": "America/Chicago",
                "label": "June 20 through June 22, 2026",
            },
        ),
        "You made 3 purchases from June 20 through June 22.",
    )
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Show my purchases from June 20 to June 22",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "You made 3 purchases from June 20 through June 22."
    completed_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "tool_call.completed"
    )
    assert completed_event["data"]["tool_name"] == "get_purchase_history_by_date_range"
    assert result.conversation_state["selected_date_range"]["label"] == (
        "June 20, 2026 through June 22, 2026"
    )

def test_chat_graph_ignores_invalid_model_date_range_arguments(caplog) -> None:
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-date-range",
            name="get_purchase_history_by_date_range",
            arguments={
                "start_date": "not-a-date",
                "end_date": "2026-06-22",
                "timezone": "America/Chicago",
            },
        ),
        "You made 4 purchases.",
    )
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with mock_model_assisted_classification(
        WorkflowKind.ACCOUNT_FACT,
        "date_range_intent",
        WorkflowOperation.LIST,
    ):
        with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
            result = chat_service.create_response(
                message="Summarize my purchases",
                customer_id=CUSTOMER_ID,
                purchase_id=None,
            )

    assert result.content == "You made 4 purchases."
    ignored_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.ignored"
    )
    assert ignored_event["data"]["tool_name"] == "get_purchase_history_by_date_range"

def test_chat_graph_blocks_account_fact_answer_without_tool_result(caplog) -> None:
    chat_service = GuardedNoToolChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("I found 2 purchases over $100."),
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="How many purchases have I made over $100?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == ACCOUNT_DATA_REQUIRED_RESPONSE
    warning_events = [
        record.event["type"]
        for record in caplog.records
        if record.levelname == "WARNING" and hasattr(record, "event")
    ]
    assert warning_events == ["response.blocked"]

def test_chat_graph_returns_graceful_response_when_final_model_call_fails(caplog) -> None:
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=FinalFailureModelClient(),
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Summarize my purchases",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == CHAT_UNAVAILABLE_RESPONSE
    assert result.graph_ready is True
    assert result.conversation_state["current_page"] == {
        "surface": "purchase_history",
        "purchase": None,
    }
    assert caplog.records[0].event["type"] == "model.failure"
    failure_data = caplog.records[0].event["data"]
    assert failure_data["reason"] == "RuntimeError"
    assert failure_data["detail"] == "final model offline"
    assert failure_data["model"] == "gpt-5.4-mini"
    assert failure_data["status"] == "failed"
    assert failure_data["phase"] == "final_response"
    assert failure_data["model_call_id"]
    assert failure_data["latency_ms"] >= 0

def test_chat_graph_returns_graceful_response_when_tool_execution_fails(caplog) -> None:
    chat_service = AIChatService(
        application_service=FailingPurchaseApplicationService(),
        model="gpt-5.4-mini",
        model_client=FakeModelClient(),
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Summarize my purchases",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result == AIChatResult(content=CHAT_UNAVAILABLE_RESPONSE, graph_ready=True)
    assert caplog.records[0].event == {
        "type": "model.failure",
        "reason": "RuntimeError",
        "detail": "database offline",
        "model": "gpt-5.4-mini",
    }
