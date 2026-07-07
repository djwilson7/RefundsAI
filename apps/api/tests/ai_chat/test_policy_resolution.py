from __future__ import annotations

import json

from refunds_ai_api.services.ai_chat import AIChatService, ModelToolCall

from .assertions import assert_customer_safe_response, assert_refund_command_response
from .fakes import (
    CUSTOMER_ID,
    PURCHASE_ID,
    ActiveResultSetAnswerModelClient,
    AmbiguousProductApplicationService,
    BroadHistoryForDateRangeModelClient,
    DeveloperToolkitApplicationService,
    FakeApplicationService,
    LastWeekApplicationService,
    LeakyFinalResponseModelClient,
    NoToolModelClient,
    ToolCallingModelClient,
)


def test_chat_graph_forces_policy_lookup_without_customer_context(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("Digital products can be refunded within 15 days.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for my digital products?",
            customer_id=None,
            purchase_id=None,
        )

    assert result.content == "Digital products can be refunded within 15 days."
    assert application_service.purchase_requests == []
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_refund_policy",
        "reason": "policy_lookup_intent",
        "scope": "product_type",
        "purchase_type": "digital",
    }
    final_tool_message = next(
        message
        for message in model_client.calls[1]["messages"]
        if message["content"].startswith("Read-only account tool result:")
    )
    assert "get_refund_policy" in final_tool_message["content"]
    assert "15 calendar days" in final_tool_message["content"]
    assert "30 calendar days" not in final_tool_message["content"]

def test_chat_graph_executes_model_requested_refund_policy_tool(caplog) -> None:
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-policy",
            name="get_refund_policy",
            arguments={"scope": "product_type", "purchase_type": "digital"},
        ),
        "Digital products can be refunded within 15 days.",
    )
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for digital products?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "Digital products can be refunded within 15 days."
    completed_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "tool_call.completed"
    )
    assert completed_event["data"]["tool_name"] == "get_refund_policy"

def test_chat_graph_overrides_model_refund_policy_arguments(caplog) -> None:
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-policy",
            name="get_refund_policy",
            arguments={"scope": "general"},
        ),
        "Digital products can be refunded within 15 days.",
    )
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for digital products?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "Digital products can be refunded within 15 days."
    overridden_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.overridden"
    )
    assert overridden_event["data"]["reason"] == "resolved_policy_context"
    assert overridden_event["data"]["purchase_type"] == "digital"

def test_chat_graph_ignores_invalid_model_refund_policy_arguments(caplog) -> None:
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-policy",
            name="get_refund_policy",
            arguments={"scope": "not-a-scope", "purchase_type": "digital"},
        ),
        "Refund policy depends on product type.",
    )
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is your refund policy?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "Refund policy depends on product type."
    ignored_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.ignored"
    )
    assert ignored_event["data"]["tool_name"] == "get_refund_policy"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"]["scope"] == "general"

def test_chat_graph_overrides_broad_history_tool_for_policy_intent(caplog) -> None:
    model_client = BroadHistoryForDateRangeModelClient(
        "Digital products can be refunded within 15 days."
    )
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for digital products?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "Digital products can be refunded within 15 days."
    overridden_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.overridden"
    )
    assert overridden_event["data"] == {
        "requested_tool_name": "get_customer_purchase_history",
        "tool_name": "get_refund_policy",
        "reason": "policy_lookup_intent",
        "scope": "product_type",
        "purchase_type": "digital",
    }

def test_chat_graph_uses_selected_purchase_type_for_policy_follow_up(caplog) -> None:
    model_client = NoToolModelClient("Digital products can be refunded within 15 days.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for those purchases?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={"selected_purchase_type": "digital"},
        )

    assert result.content == "Digital products can be refunded within 15 days."
    assert result.conversation_state["selected_purchase_type"] == "digital"
    assert result.conversation_state["selected_policy_scope"] == "product_type"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_refund_policy",
        "reason": "policy_lookup_intent",
        "scope": "product_type",
        "purchase_type": "digital",
    }

def test_chat_graph_resolves_product_follow_up_to_policy_type(caplog) -> None:
    model_client = NoToolModelClient("Physical products can be returned within 30 days.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What about the keyboard?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "selected_purchase_type": "digital",
                "selected_policy_scope": "product_type",
            },
        )

    assert result.content == "Physical products can be returned within 30 days."
    assert result.conversation_state["selected_product"] == "Keyboard"
    assert result.conversation_state["selected_purchase_id"] == (
        "40000000-0000-4000-8000-000000000003"
    )
    assert result.conversation_state["selected_purchase_type"] == "physical"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_refund_policy",
        "reason": "policy_lookup_intent",
        "scope": "product_type",
        "purchase_type": "physical",
    }

def test_chat_graph_resolves_product_name_exact_match(caplog) -> None:
    model_client = NoToolModelClient("Developer Toolkit follows the subscription refund policy.")
    chat_service = AIChatService(
        application_service=DeveloperToolkitApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What about the Developer Toolkit?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={"selected_policy_scope": "product_type"},
        )

    assert result.content == "Developer Toolkit follows the subscription refund policy."
    assert result.conversation_state["selected_product"] == "Developer Toolkit"
    assert result.conversation_state["selected_purchase_id"] == (
        "40000000-0000-4000-8000-000000000005"
    )
    assert result.conversation_state["selected_purchase_type"] == "subscription"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_refund_policy",
        "reason": "policy_lookup_intent",
        "scope": "product_type",
        "purchase_type": "subscription",
    }
    assert forced_event["data"]["purchase_type"] == "subscription"

def test_chat_graph_resolves_product_name_partial_match(caplog) -> None:
    model_client = NoToolModelClient("Developer Toolkit follows the subscription refund policy.")
    chat_service = AIChatService(
        application_service=DeveloperToolkitApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for Toolkit?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "Developer Toolkit follows the subscription refund policy."
    assert result.conversation_state["selected_product"] == "Developer Toolkit"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"]["purchase_type"] == "subscription"

def test_chat_graph_resolves_product_name_fuzzy_match(caplog) -> None:
    model_client = NoToolModelClient("Developer Toolkit follows the subscription refund policy.")
    chat_service = AIChatService(
        application_service=DeveloperToolkitApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for Devloper Toolkt?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "Developer Toolkit follows the subscription refund policy."
    assert result.conversation_state["selected_product"] == "Developer Toolkit"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"]["purchase_type"] == "subscription"

def test_chat_graph_named_product_follow_up_escapes_selected_purchase_set(caplog) -> None:
    model_client = NoToolModelClient("Developer Toolkit follows the subscription refund policy.")
    chat_service = AIChatService(
        application_service=DeveloperToolkitApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What about the Developer Toolkit?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "selected_purchase_type": "digital",
                "selected_purchase_ids": [
                    PURCHASE_ID,
                    "40000000-0000-4000-8000-000000000002",
                ],
                "selected_policy_scope": "product_type",
            },
        )

    assert result.content == "Developer Toolkit follows the subscription refund policy."
    assert result.conversation_state["selected_product"] == "Developer Toolkit"
    assert result.conversation_state["selected_purchase_id"] == (
        "40000000-0000-4000-8000-000000000005"
    )
    assert result.conversation_state["selected_purchase_type"] == "subscription"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_refund_policy",
        "reason": "policy_lookup_intent",
        "scope": "product_type",
        "purchase_type": "subscription",
    }

def test_chat_graph_unresolved_product_reference_asks_for_clarification(caplog) -> None:
    model_client = NoToolModelClient("This response should not be used.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for Developer Toolkit?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == (
        "I couldn't find a purchase matching 'Developer Toolkit' in your account history. "
        "Could you confirm the product name, order number, SKU, or purchase date? "
        "I can also help with account, purchases, orders, refund policies, "
        "refund-related questions, and account activity."
    )
    assert len(model_client.calls) == 1
    assert not any(
        record.event["type"] in {"tool_call.forced", "tool_call.completed"}
        for record in caplog.records
        if hasattr(record, "event")
    )

def test_chat_graph_does_not_infer_policy_type_from_unresolved_product_name(caplog) -> None:
    model_client = NoToolModelClient("This response should not be used.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for Enterprise Subscription Platform?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
    )

    assert "Enterprise Subscription Platform" in result.content
    assert result.conversation_state["selected_purchase_type"] is None
    assert len(model_client.calls) == 1
    assert not any(
        record.event["type"] in {"tool_call.forced", "tool_call.completed"}
        for record in caplog.records
        if hasattr(record, "event")
    )

def test_chat_graph_ambiguous_product_reference_asks_for_clarification(
    caplog,
) -> None:
    model_client = NoToolModelClient("This response should not be used.")
    chat_service = AIChatService(
        application_service=AmbiguousProductApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Can I refund Developer?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
    )

    assert "Developer" in result.content
    assert "Could you confirm" in result.content
    assert result.conversation_state["selected_purchase_id"] is None
    assert len(model_client.calls) == 1
    assert not any(
        record.event["type"] == "tool_call.completed"
        for record in caplog.records
        if hasattr(record, "event")
    )

def test_chat_graph_resolves_latest_follow_up_inside_selected_set(caplog) -> None:
    model_client = NoToolModelClient("Digital products can be refunded within 15 days.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for the latest one?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "selected_purchase_type": "digital",
                "selected_purchase_ids": [
                    PURCHASE_ID,
                    "40000000-0000-4000-8000-000000000002",
                ],
                "selected_policy_scope": "product_type",
            },
        )

    assert result.content == "Digital products can be refunded within 15 days."
    assert result.conversation_state["selected_product"] == "Icon Set"
    assert result.conversation_state["selected_purchase_id"] == (
        "40000000-0000-4000-8000-000000000002"
    )
    assert result.conversation_state["selected_purchase_type"] == "digital"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_refund_policy",
        "reason": "policy_lookup_intent",
        "scope": "product_type",
        "purchase_type": "digital",
    }

def test_chat_graph_ranking_follow_up_after_purchase_type_aggregate_is_account_fact(
    caplog,
) -> None:
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-policy",
            name="get_refund_policy",
            arguments={"scope": "product_type", "purchase_type": "subscription"},
        ),
        "The latest purchase from your subscriptions is Developer Toolkit.",
    )
    chat_service = AIChatService(
        application_service=DeveloperToolkitApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What's the last one?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "selected_purchase_type": "subscription",
                "selected_purchase_ids": [
                    "40000000-0000-4000-8000-000000000005",
                    "40000000-0000-4000-8000-000000000004",
                ],
                "selected_policy_scope": None,
            },
        )

    assert result.content == "The latest purchase from your subscriptions is Developer Toolkit."
    assert result.conversation_state["selected_product"] == "Developer Toolkit"
    assert result.conversation_state["selected_purchase_id"] == (
        "40000000-0000-4000-8000-000000000005"
    )
    assert result.conversation_state["selected_purchase_type"] == "subscription"
    assert result.conversation_state["selected_purchase_ids"] == [
        "40000000-0000-4000-8000-000000000005",
        "40000000-0000-4000-8000-000000000004",
    ]
    assert result.conversation_state["selected_scope_label"] == "your subscriptions"
    assert not any(
        record.event["type"] == "tool_call.completed"
        and record.event["data"]["tool_name"] == "get_refund_policy"
        for record in caplog.records
        if hasattr(record, "event")
    )
    overridden_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.overridden"
    )
    assert overridden_event["data"]["reason"] == "account_domain_intent"
    assert overridden_event["data"]["requested_tool_name"] == "get_refund_policy"
    assert overridden_event["data"]["tool_name"] == "get_customer_purchase_history"

def test_chat_graph_sanitizes_backend_terms_from_final_response() -> None:
    model_client = LeakyFinalResponseModelClient()
    chat_service = AIChatService(
        application_service=DeveloperToolkitApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    result = chat_service.create_response(
        message="What's the last one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state={
            "selected_purchase_type": "subscription",
            "selected_purchase_ids": [
                "40000000-0000-4000-8000-000000000005",
                "40000000-0000-4000-8000-000000000004",
            ],
            "selected_scope_label": "your subscriptions",
        },
    )

    assert result.content == (
        "The latest purchase from your subscriptions is Developer Toolkit for $39.99."
    )
    assert_customer_safe_response(result.content)

def test_chat_graph_resolves_oldest_follow_up_inside_selected_set(caplog) -> None:
    model_client = NoToolModelClient("Pro Subscription is your oldest subscription.")
    chat_service = AIChatService(
        application_service=DeveloperToolkitApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What's my oldest?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "selected_purchase_type": "subscription",
                "selected_purchase_ids": [
                    "40000000-0000-4000-8000-000000000005",
                    "40000000-0000-4000-8000-000000000004",
                ],
            },
        )

    assert result.content == "Pro Subscription is your oldest subscription."
    assert result.conversation_state["selected_product"] == "Pro Subscription"
    assert result.conversation_state["selected_purchase_id"] == (
        "40000000-0000-4000-8000-000000000004"
    )
    assert result.conversation_state["selected_purchase_type"] == "subscription"
    final_messages = model_client.calls[1]["messages"]
    resolved_context_message = next(
        message
        for message in final_messages
        if message["content"].startswith("Backend-resolved purchase context:")
    )
    assert "Pro Subscription" in resolved_context_message["content"]
    assert "Developer Toolkit" not in resolved_context_message["content"]

def test_chat_graph_ranking_follow_up_after_date_range_aggregate_is_scoped() -> None:
    application_service = FakeApplicationService()
    first_model_client = NoToolModelClient("You made 3 purchases in that date range.")
    first_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=first_model_client,
    )
    first_result = first_chat_service.create_response(
        message="How many purchases did I make between June 20 and June 22?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert first_result.conversation_state["selected_purchase_ids"] == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
        "40000000-0000-4000-8000-000000000003",
    ]
    assert first_result.conversation_state["selected_scope_label"] == (
        "purchases from June 20, 2026 through June 22, 2026"
    )

    second_model_client = NoToolModelClient(
        "The most expensive purchase from that date range was Keyboard for $125.00."
    )
    second_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=second_model_client,
    )
    second_result = second_chat_service.create_response(
        message="What was the most expensive one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert second_result.content == (
        "The most expensive purchase from that date range was Keyboard for $125.00."
    )
    assert second_result.conversation_state["selected_product"] == "Keyboard"
    assert second_result.conversation_state["selected_purchase_id"] == (
        "40000000-0000-4000-8000-000000000003"
    )
    assert second_result.conversation_state["selected_scope_label"] == (
        "purchases from June 20, 2026 through June 22, 2026"
    )
    resolved_context_message = next(
        message
        for message in second_model_client.calls[1]["messages"]
        if message["content"].startswith("Backend-resolved purchase context:")
    )
    assert "Keyboard" in resolved_context_message["content"]
    assert "$125.00" in resolved_context_message["content"]

def test_chat_graph_date_range_ranking_then_vague_policy_uses_ranked_purchase(
    caplog,
) -> None:
    application_service = FakeApplicationService()
    first_model_client = NoToolModelClient("You made 3 purchases in that date range.")
    first_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=first_model_client,
    )
    first_result = first_chat_service.create_response(
        message="How many purchases did I make between June 20 and June 22?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    second_model_client = NoToolModelClient("Keyboard was the most expensive one.")
    second_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=second_model_client,
    )
    second_result = second_chat_service.create_response(
        message="What was the most expensive one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    third_model_client = NoToolModelClient("Keyboard uses physical return policy.")
    third_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=third_model_client,
    )
    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        third_result = third_chat_service.create_response(
            message="What is its refund policy?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=second_result.conversation_state,
        )

    assert third_result.content == "Keyboard uses physical return policy."
    assert third_result.conversation_state["selected_product"] == "Keyboard"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"]["purchase_type"] == "physical"

def test_chat_graph_ranking_follow_up_after_threshold_aggregate_is_scoped() -> None:
    application_service = FakeApplicationService()
    first_model_client = NoToolModelClient("You had 2 purchases over $40.")
    first_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=first_model_client,
    )
    first_result = first_chat_service.create_response(
        message="How many purchases were over $40?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert first_result.conversation_state["selected_purchase_ids"] == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000003",
    ]
    assert first_result.conversation_state["selected_scope_label"] == (
        "purchases over $40.00"
    )

    second_model_client = NoToolModelClient(
        "The cheapest purchase from those purchases was Design Template Pack for $45.00."
    )
    second_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=second_model_client,
    )
    second_result = second_chat_service.create_response(
        message="What was the cheapest one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert second_result.content == (
        "The cheapest purchase from those purchases was Design Template Pack for $45.00."
    )
    assert second_result.conversation_state["selected_product"] == "Design Template Pack"
    assert second_result.conversation_state["selected_purchase_id"] == PURCHASE_ID
    assert second_result.conversation_state["selected_purchase_ids"] == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000003",
    ]
    assert second_result.conversation_state["selected_scope_label"] == (
        "purchases over $40.00"
    )

    third_model_client = NoToolModelClient("It was $45.00.")
    third_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=third_model_client,
    )
    third_result = third_chat_service.create_response(
        message="How much was it?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=second_result.conversation_state,
    )

    assert third_result.content == "It was $45.00."
    assert third_result.conversation_state["selected_product"] == "Design Template Pack"
    resolved_context_message = next(
        message
        for message in third_model_client.calls[1]["messages"]
        if message["content"].startswith("Backend-resolved purchase context:")
    )
    assert "$45.00" in resolved_context_message["content"]

def test_chat_graph_policy_follow_up_after_ranking_uses_ranked_purchase(caplog) -> None:
    application_service = DeveloperToolkitApplicationService()
    first_model_client = NoToolModelClient(
        "The latest purchase from your subscriptions is Developer Toolkit."
    )
    first_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=first_model_client,
    )
    first_result = first_chat_service.create_response(
        message="What's the last one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state={
            "selected_purchase_type": "subscription",
            "selected_purchase_ids": [
                "40000000-0000-4000-8000-000000000005",
                "40000000-0000-4000-8000-000000000004",
            ],
        },
    )

    assert first_result.conversation_state["selected_product"] == "Developer Toolkit"

    second_model_client = NoToolModelClient("Developer Toolkit uses subscription policy.")
    second_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=second_model_client,
    )
    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        second_result = second_chat_service.create_response(
            message="What is its refund policy?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=first_result.conversation_state,
        )

    assert second_result.content == "Developer Toolkit uses subscription policy."
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"]["purchase_type"] == "subscription"

def test_chat_graph_aggregate_ranking_then_vague_eligibility_uses_ranked_purchase(
    caplog,
) -> None:
    application_service = DeveloperToolkitApplicationService()
    first_model_client = NoToolModelClient(
        "The latest purchase from your subscriptions is Developer Toolkit."
    )
    first_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=first_model_client,
    )
    first_result = first_chat_service.create_response(
        message="What's the latest one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state={
            "selected_purchase_type": "subscription",
            "selected_purchase_ids": [
                "40000000-0000-4000-8000-000000000005",
                "40000000-0000-4000-8000-000000000004",
            ],
        },
    )

    second_model_client = NoToolModelClient("Developer Toolkit is eligible.")
    second_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=second_model_client,
    )
    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        second_result = second_chat_service.create_response(
            message="Can I refund it?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=first_result.conversation_state,
        )

    assert_refund_command_response(
        second_result.content,
        "Developer Toolkit is eligible.",
        "Confirm cancel and issue refund",
    )
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005"
    ]
    assert second_result.conversation_state["selected_product"] == "Developer Toolkit"
    assert second_result.conversation_state["active_refund_context"]["purchase_id"] == (
        "40000000-0000-4000-8000-000000000005"
    )
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"]["context"] == "selected_purchase"

def test_chat_graph_sends_compact_context_without_full_payloads() -> None:
    model_client = NoToolModelClient("Context was available.")
    chat_service = AIChatService(
        application_service=DeveloperToolkitApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    chat_service.create_response(
        message="What about the latest one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        page_context={
            "surface": "purchase_detail",
            "purchase_id": "40000000-0000-4000-8000-000000000005",
            "rendered_page_text": "This full page text must not be sent to the model.",
        },
        conversation_state={
            "selected_purchase_type": "subscription",
            "selected_product": "Developer Toolkit",
            "selected_purchase_id": "40000000-0000-4000-8000-000000000005",
            "selected_purchase_ids": [
                "40000000-0000-4000-8000-000000000005",
                "40000000-0000-4000-8000-000000000004",
            ],
            "selected_policy_scope": "product_type",
        },
    )

    tool_selection_context = next(
        message
        for message in model_client.calls[0]["messages"]
        if message["content"].startswith("Compact conversation context")
    )
    assert "selected_purchase_ids" in tool_selection_context["content"]
    assert '"count": 2' in tool_selection_context["content"]
    assert "Developer Toolkit" in tool_selection_context["content"]
    assert "This full page text must not be sent" not in tool_selection_context["content"]
    assert "Read-only account tool result" not in tool_selection_context["content"]

def test_chat_graph_resolves_earliest_and_first_aliases_inside_selected_set() -> None:
    for message in ("What about the earliest?", "What about the first?"):
        model_client = NoToolModelClient("Pro Subscription is the selected subscription.")
        chat_service = AIChatService(
            application_service=DeveloperToolkitApplicationService(),
            model="gpt-5.4-mini",
            model_client=model_client,
        )

        result = chat_service.create_response(
            message=message,
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={
                "selected_purchase_type": "subscription",
                "selected_purchase_ids": [
                    "40000000-0000-4000-8000-000000000005",
                    "40000000-0000-4000-8000-000000000004",
                ],
                "selected_policy_scope": "product_type",
            },
        )

        assert result.conversation_state["selected_product"] == "Pro Subscription"
        assert result.conversation_state["selected_purchase_id"] == (
            "40000000-0000-4000-8000-000000000004"
        )

def test_chat_graph_uses_global_latest_only_without_selected_set(caplog) -> None:
    model_client = NoToolModelClient("Subscription policy applies to the latest purchase.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for the latest one?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={"selected_policy_scope": "product_type"},
        )

    assert result.content == "Subscription policy applies to the latest purchase."
    assert result.conversation_state["selected_product"] == "Pro Subscription"
    assert result.conversation_state["selected_purchase_id"] == (
        "40000000-0000-4000-8000-000000000004"
    )
    assert result.conversation_state["selected_purchase_type"] == "subscription"

def test_chat_graph_uses_global_oldest_only_without_selected_set(caplog) -> None:
    model_client = NoToolModelClient("Design Template Pack is the oldest purchase.")
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="What is the refund policy for the oldest one?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state={"selected_policy_scope": "product_type"},
        )

    assert result.content == "Design Template Pack is the oldest purchase."
    assert result.conversation_state["selected_product"] == "Design Template Pack"
    assert result.conversation_state["selected_purchase_id"] == PURCHASE_ID
    assert result.conversation_state["selected_purchase_type"] == "digital"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"]["purchase_type"] == "digital"

def test_chat_graph_subscription_temporal_chain_updates_concrete_purchase_state() -> None:
    application_service = DeveloperToolkitApplicationService()
    first_model_client = NoToolModelClient("You have 2 subscription purchases.")
    first_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=first_model_client,
    )

    first_result = first_chat_service.create_response(
        message="How many purchases are subscriptions?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert first_result.conversation_state["selected_purchase_type"] == "subscription"
    assert first_result.conversation_state["selected_purchase_ids"] == [
        "40000000-0000-4000-8000-000000000005",
        "40000000-0000-4000-8000-000000000004",
    ]

    second_model_client = NoToolModelClient("Pro Subscription is your oldest subscription.")
    second_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=second_model_client,
    )
    second_result = second_chat_service.create_response(
        message="What's my oldest?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert second_result.conversation_state["selected_product"] == "Pro Subscription"
    assert second_result.conversation_state["selected_purchase_type"] == "subscription"

    third_model_client = NoToolModelClient("Subscription purchases follow subscription policy.")
    third_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=third_model_client,
    )
    third_result = third_chat_service.create_response(
        message="What's its refund policy?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=second_result.conversation_state,
    )

    assert third_result.content == "Subscription purchases follow subscription policy."
    policy_message = next(
        message
        for message in third_model_client.calls[1]["messages"]
        if message["content"].startswith("Read-only account tool result:")
    )
    assert "subscription refunds" in policy_message["content"]
    compact_context_message = next(
        message
        for message in third_model_client.calls[1]["messages"]
        if message["content"].startswith("Compact conversation context")
    )
    assert '"selected_purchase_type": "subscription"' in compact_context_message["content"]

def test_chat_graph_subscription_fact_to_last_one_to_eligibility_workflow_chain() -> None:
    application_service = DeveloperToolkitApplicationService()
    first_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("You have paid for 2 subscriptions."),
    )

    first_result = first_chat_service.create_response(
        message="How many subscriptions have I paid for?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert first_result.conversation_state["active_workflow"]["kind"] == "account_fact"
    assert first_result.conversation_state["active_result_set"] == {
        "type": "subscriptions",
        "purchase_ids": [
            "40000000-0000-4000-8000-000000000005",
            "40000000-0000-4000-8000-000000000004",
        ],
        "sort": "purchase_date_desc",
        "label": "your subscriptions",
    }

    second_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("The latest paid subscription was Developer Toolkit."),
    )
    second_result = second_chat_service.create_response(
        message="What was the last one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert second_result.conversation_state["active_workflow"]["kind"] == "account_fact"
    assert second_result.conversation_state["active_purchase"] == {
        "purchase_id": "40000000-0000-4000-8000-000000000005",
        "product_name": "Developer Toolkit",
        "purchase_type": "subscription",
    }

    third_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Developer Toolkit is eligible."),
    )
    third_result = third_chat_service.create_response(
        message="Is it refundable?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=second_result.conversation_state,
    )

    assert_refund_command_response(
        third_result.content,
        "Developer Toolkit is eligible.",
        "Confirm cancel and issue refund",
    )
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005"
    ]
    assert third_result.conversation_state["active_workflow"]["kind"] == (
        "refund_eligibility"
    )
    assert third_result.conversation_state["active_refund_context"]["purchase_id"] == (
        "40000000-0000-4000-8000-000000000005"
    )

def test_chat_graph_date_range_first_policy_eligibility_workflow_chain() -> None:
    application_service = FakeApplicationService()
    first_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Here are your purchases from that range."),
    )

    first_result = first_chat_service.create_response(
        message="Show me purchases between June 20 and June 22.",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert first_result.conversation_state["active_workflow"]["kind"] == "account_fact"
    assert first_result.conversation_state["active_result_set"]["type"] == "date_range"
    assert first_result.conversation_state["selected_purchase_ids"] == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
        "40000000-0000-4000-8000-000000000003",
    ]

    second_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("The first purchase was Design Template Pack."),
    )
    second_result = second_chat_service.create_response(
        message="What was the first one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert second_result.conversation_state["active_purchase"] == {
        "purchase_id": PURCHASE_ID,
        "product_name": "Design Template Pack",
        "purchase_type": "digital",
    }

    third_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Design Template Pack follows digital policy."),
    )
    third_result = third_chat_service.create_response(
        message="What is the refund policy for it?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=second_result.conversation_state,
    )

    assert third_result.conversation_state["active_workflow"]["kind"] == "refund_policy"
    assert third_result.conversation_state["selected_purchase_id"] == PURCHASE_ID

    fourth_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Design Template Pack is eligible."),
    )
    fourth_result = fourth_chat_service.create_response(
        message="Is it eligible?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=third_result.conversation_state,
    )

    assert_refund_command_response(
        fourth_result.content,
        "Design Template Pack is eligible.",
        "Confirm invalidate code and issue refund",
    )
    assert application_service.refund_workflow_requests == [PURCHASE_ID]
    assert fourth_result.conversation_state["active_workflow"]["kind"] == (
        "refund_eligibility"
    )
    assert fourth_result.conversation_state["active_refund_context"]["purchase_id"] == (
        PURCHASE_ID
    )

def test_chat_graph_list_follow_up_answers_from_active_digital_result_set(caplog) -> None:
    application_service = FakeApplicationService()
    first_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("You have 2 digital purchases."),
    )
    first_result = first_chat_service.create_response(
        message="How many digital purchases have I made?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    second_model_client = ActiveResultSetAnswerModelClient()
    second_chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=second_model_client,
    )
    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        second_result = second_chat_service.create_response(
            message="Can you list them please.",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=first_result.conversation_state,
        )

    assert second_result.content == (
        "your digital purchases: Design Template Pack, Icon Set."
    )
    assert "Keyboard" not in second_result.content
    assert "Pro Subscription" not in second_result.content
    response_context = second_model_client.final_response_context
    assert response_context["primary_answer_source"] == "active_result_set"
    assert response_context["answer_scope"] == "your digital purchases"
    assert response_context["active_result_set"]["count"] == 2
    assert {
        item["purchase_type"] for item in response_context["active_result_set"]["items"]
    } == {"digital"}
    final_request_event = [
        record.event
        for record in caplog.records
        if record.event["type"] == "model.requested"
        and record.event["data"]["phase"] == "final_response"
    ][-1]
    assert (
        final_request_event["data"]["model_context"]["tool_results"]
        == "active_result_set:2 purchases, label=your digital purchases; "
        "raw=get_customer_purchase_history:4 purchases, $209.99"
    )

def test_chat_graph_first_follow_up_selects_from_active_digital_result_set() -> None:
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

    second_model_client = ActiveResultSetAnswerModelClient(mode="first")
    second_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=second_model_client,
    ).create_response(
        message="What's the first one?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert second_result.content == "The first one was Design Template Pack."
    assert second_result.conversation_state["selected_purchase_id"] == PURCHASE_ID
    assert second_model_client.final_response_context["active_result_set"]["items"][0][
        "product_name"
    ] == "Design Template Pack"

def test_chat_graph_list_follow_up_answers_from_active_date_range_result_set() -> None:
    application_service = LastWeekApplicationService()
    first_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Here are your purchases from last week."),
    ).create_response(
        message="Show purchases from last week.",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    second_model_client = ActiveResultSetAnswerModelClient()
    second_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=second_model_client,
    ).create_response(
        message="List them.",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert second_result.content == (
        "last week's purchases: Design Template Pack, Keyboard."
    )
    assert "Pro Subscription" not in second_result.content
    assert second_model_client.final_response_context["active_result_set"]["type"] == (
        "date_range"
    )
    assert {
        item["product_name"]
        for item in second_model_client.final_response_context["active_result_set"][
            "items"
        ]
    } == {"Design Template Pack", "Keyboard"}

def test_chat_graph_list_follow_up_answers_from_active_subscription_result_set() -> None:
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

    second_model_client = ActiveResultSetAnswerModelClient()
    second_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=second_model_client,
    ).create_response(
        message="List them.",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    assert second_result.content == (
        "your subscriptions: Developer Toolkit, Pro Subscription."
    )
    assert "Design Template Pack" not in second_result.content
    assert "Keyboard" not in second_result.content
    assert {
        item["purchase_type"]
        for item in second_model_client.final_response_context["active_result_set"][
            "items"
        ]
    } == {"subscription"}

def test_chat_graph_subscription_result_set_follow_up_routes_to_eligibility(
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
    second_result = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("your subscriptions: Developer Toolkit, Pro Subscription."),
    ).create_response(
        message="Can you list them please?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
        conversation_state=first_result.conversation_state,
    )

    third_model_client = NoToolModelClient("Both subscriptions are eligible.")
    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        third_result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=third_model_client,
        ).create_response(
            message="Am I able to refund them?",
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
    assert third_result.conversation_state["active_workflow"]["object_label"] == (
        "your subscriptions"
    )
    assert third_result.conversation_state["active_workflow"]["operation"] == (
        "eligibility"
    )
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005",
        "40000000-0000-4000-8000-000000000004",
    ]
    compact_context_message = next(
        message
        for message in third_model_client.calls[-1]["messages"]
        if message["content"].startswith("Compact conversation context")
    )
    response_context = json.loads(compact_context_message["content"].split(": ", 1)[1])[
        "response_context"
    ]
    assert response_context["primary_answer_source"] == "refund_eligibility_result"
    assert response_context["active_result_set"]["label"] == "your subscriptions"
    classified_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "workflow.classified"
    )
    assert classified_event["data"] | {
        "kind": "refund_eligibility",
        "object": "active_result_set",
        "object_label": "your subscriptions",
        "operation": "eligibility",
        "reason": "active_result_set_refund_query",
    } == classified_event["data"]
    completed_event = next(
        record.event
        for record in caplog.records
        if record.event["type"] == "tool_call.completed"
    )
    assert completed_event["data"]["tool_name"] == "get_refund_eligibility"
    assert not any(
        record.event["type"] == "tool_call.overridden"
        and record.event["data"]["tool_name"] == "get_customer_purchase_history"
        for record in caplog.records
    )
