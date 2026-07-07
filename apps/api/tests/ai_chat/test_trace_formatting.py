from __future__ import annotations

import json

from refunds_ai_api.services.ai_chat import (
    AIChatService,
    format_trace_console_message,
    get_customer_purchase_history,
    get_refund_eligibility,
)
from refunds_ai_api.services.ai_chat.models import EligibilityResolution
from refunds_ai_api.services.ai_chat.trace_formatting import (
    MAX_MESSAGE_PREVIEW_CHARS,
    MAX_RESPONSE_PREVIEW_CHARS,
    format_debug_block,
    format_trace_detail_block,
    preview_text,
    summarize_tool_result,
    summarize_workflow_classification,
    summarize_workflow_context,
)
from refunds_ai_api.services.ai_chat.workflows.classification import classify_workflow
from refunds_ai_api.services.ai_chat.workflows.context import resolve_workflow_context

from .fakes import (
    CUSTOMER_ID,
    PURCHASE_ID,
    DeveloperToolkitApplicationService,
    FakeApplicationService,
    FakeModelClient,
    NoToolModelClient,
    WorkflowRuntime,
)


def test_trace_formatting_formats_nested_dictionary_blocks() -> None:
    block = format_debug_block(
        "Example",
        {
            "workflow": {"kind": "refund_eligibility", "reason": "selected_set"},
            "items": ["one", "two"],
        },
    )

    assert block.startswith("--- Example ---")
    assert "workflow:\n  kind: refund_eligibility" in block
    assert "items:\n  - one\n  - two" in block
    assert block.endswith("--- end Example ---")

def test_trace_formatting_truncates_long_lists_and_previews() -> None:
    block = format_debug_block("Items", {"items": list(range(12))})
    message_preview = preview_text(
        "x" * (MAX_MESSAGE_PREVIEW_CHARS + 20),
        max_chars=MAX_MESSAGE_PREVIEW_CHARS,
    )
    response_preview = preview_text(
        "y" * (MAX_RESPONSE_PREVIEW_CHARS + 20),
        max_chars=MAX_RESPONSE_PREVIEW_CHARS,
    )

    assert "... 2 more items not shown" in block
    assert len(message_preview) == MAX_MESSAGE_PREVIEW_CHARS
    assert message_preview.endswith("...")
    assert len(response_preview) == MAX_RESPONSE_PREVIEW_CHARS
    assert response_preview.endswith("...")

def test_trace_formatting_includes_final_response_active_result_set_items_preview() -> None:
    response_context = {
        "primary_answer_source": "active_result_set",
        "answer_scope": "your digital purchases",
        "active_result_set": {
            "type": "purchase_history",
            "label": "your digital purchases",
            "count": 6,
            "items": [
                {
                    "id": f"purchase-{index}",
                    "order_number": f"RAI-{index}",
                    "product_name": f"Digital Product {index}",
                    "purchase_type": "digital",
                    "amount_display": "$10.00",
                    "status": "completed",
                    "purchased_at": "2026-06-20T14:30:00+00:00",
                }
                for index in range(6)
            ],
        },
    }
    block = format_trace_detail_block(
        "model.requested",
        {
            "phase": "final_response",
            "model": "gpt-5.4-mini",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Compact conversation context for resolving follow-up "
                        f"references: {json.dumps({'response_context': response_context})}"
                    ),
                }
            ],
            "tools": [],
            "model_context": {
                "tool_results": (
                    "active_result_set:6 purchases, label=your digital purchases; "
                    "raw=get_customer_purchase_history:12 purchases, $1169.88"
                )
            },
        },
    )

    assert "primary_answer_source: active_result_set" in block
    assert "items_preview:" in block
    assert "product_name: Digital Product 0" in block
    assert "purchase_type: digital" in block
    assert "amount_display: $10.00" in block
    assert "status: completed" in block
    assert "purchased_at: 2026-06-20T14:30:00+00:00" in block
    assert "... 1 more items not shown" in block
    assert "id: purchase-0" not in block
    assert "order_number: RAI-0" not in block

def test_trace_formatting_summarizes_workflow_classification() -> None:
    classification = classify_workflow(
        "Am I able to refund them?",
        conversation_state={
            "active_result_set": {
                "type": "subscriptions",
                "purchase_ids": ["purchase-1", "purchase-2"],
                "sort": "purchase_date_desc",
                "label": "your subscriptions",
            }
        },
        page_context={},
    )

    summary = summarize_workflow_classification(classification)

    assert summary["workflow"]["kind"] == "refund_eligibility"
    assert summary["conversation_object"]["kind"] == "active_result_set"
    assert summary["conversation_object"]["label"] == "your subscriptions"
    assert summary["operation"]["kind"] == "eligibility"
    assert summary["lookup"]["key"] == "active_result_set + eligibility"

def test_trace_formatting_summarizes_workflow_context_with_eligibility_ids() -> None:
    context = WorkflowRuntime(FakeApplicationService())
    classification = classify_workflow(
        "Can I refund them?",
        conversation_state={
            "active_result_set": {
                "type": "subscriptions",
                "purchase_ids": ["purchase-1", "purchase-2"],
                "sort": "purchase_date_desc",
                "label": "your subscriptions",
            }
        },
        page_context={},
    )
    workflow_context = resolve_workflow_context(
        context,
        {
            "message": "Can I refund them?",
            "customer_id": CUSTOMER_ID,
            "page_context": {"surface": "purchase_history"},
            "conversation_state": {
                "active_result_set": {
                    "type": "subscriptions",
                    "purchase_ids": ["purchase-1", "purchase-2"],
                    "sort": "purchase_date_desc",
                    "label": "your subscriptions",
                }
            },
        },
        classification,
    )
    workflow_context = workflow_context.__class__(
        **{
            **workflow_context.__dict__,
            "eligibility_resolution": EligibilityResolution(
                ["purchase-1", "purchase-2"],
                "selected_set",
            ),
        }
    )

    summary = summarize_workflow_context(workflow_context)

    assert summary["eligibility_resolution"] == {
        "purchase_ids": ["purchase-1", "purchase-2"],
        "context": "selected_set",
    }

def test_trace_formatting_summarizes_purchase_history_tool_result() -> None:
    result = get_customer_purchase_history(FakeApplicationService(), CUSTOMER_ID)

    summary = summarize_tool_result("get_customer_purchase_history", result)

    assert summary["summary"] == "4 purchases, $209.99"
    assert summary["aggregates"]["total_purchase_count"] == 4
    assert summary["items_preview"][0].startswith(PURCHASE_ID)

def test_trace_formatting_summarizes_refund_eligibility_tool_result() -> None:
    result = get_refund_eligibility(
        FakeApplicationService(),
        CUSTOMER_ID,
        purchase_ids=[PURCHASE_ID, "40000000-0000-4000-8000-000000000002"],
        context="selected_set",
    )

    summary = summarize_tool_result("get_refund_eligibility", result)

    assert summary["summary"] == "2 purchases, 1 eligible, 1 blocked"
    assert summary["result"]["purchase_count"] == 2
    assert "eligible" in summary["result"]["items"][0]
    assert "blocked" in summary["result"]["items"][1]

def test_trace_formatting_formats_blocked_workflow_with_non_null_reason() -> None:
    block = format_trace_detail_block(
        "workflow.blocked",
        {
            "kind": "refund_mutation",
            "reason": None,
            "object": "active_result_set",
            "object_label": "your subscriptions",
            "operation": "start_refund",
        },
    )

    assert "--- Workflow Blocked ---" in block
    assert "reason: refund_mutation_not_ready" in block
    assert "operation: start_refund" in block

def test_chat_graph_console_logs_include_structured_workflow_sections(caplog) -> None:
    application_service = DeveloperToolkitApplicationService()

    with caplog.at_level("INFO", logger="uvicorn.error"):
        first_result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("You have paid for 2 subscriptions."),
        ).create_response(
            message="How many subscriptions do I currently have?",
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
        third_result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("Subscriptions follow the subscription policy."),
        ).create_response(
            message="What is the refund policy for these types of products?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=second_result.conversation_state,
        )
        fourth_result = AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("Both subscriptions are eligible."),
        ).create_response(
            message="Am I able to refund them?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=third_result.conversation_state,
        )
        AIChatService(
            application_service=application_service,
            model="gpt-5.4-mini",
            model_client=NoToolModelClient("This response should not be used."),
        ).create_response(
            message="Let's do that.",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
            conversation_state=fourth_result.conversation_state,
        )

    console_output = "\n".join(record.getMessage() for record in caplog.records)
    assert "--- Workflow Classification ---" in console_output
    assert "--- Workflow Context ---" in console_output
    assert "--- Tool Result ---" in console_output
    assert "--- Workflow State Update ---" in console_output
    assert "--- Workflow Blocked ---" in console_output
    assert "reason: refund_mutation_target_required" in console_output

def test_trace_console_message_summarizes_model_request_without_nested_payloads() -> None:
    event = {
        "type": "model.requested",
        "step": 2,
        "message": "Sending tool-selection package to the model.",
        "data": {
            "phase": "tool_selection",
            "model": "gpt-5.4-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are RefundsAI's customer support assistant.",
                },
                {"role": "user", "content": "Which purchases can be refunded?"},
            ],
            "tools": [
                {"name": "get_customer_purchase_history"},
                {"name": "get_refund_eligibility"},
            ],
        },
    }

    message = format_trace_console_message(event)

    assert message.startswith(
        "AI graph step 2: Model requested - Sending tool-selection package to the "
        "model. (phase=tool_selection, model=gpt-5.4-mini, messages=2, "
        "tools=get_customer_purchase_history, get_refund_eligibility)"
    )
    assert "--- Model Request ---" in message
    assert "available_tools:\n  - get_customer_purchase_history" in message
    assert "You are RefundsAI" not in message
    assert "Which purchases can be refunded" not in message

def test_trace_console_message_summarizes_tool_result_without_nested_payloads() -> None:
    event = {
        "type": "tool_call.completed",
        "step": 5,
        "message": "Backend refund-eligibility tool completed.",
        "data": {
            "tool_name": "get_refund_eligibility",
            "result": {
                "purchase_count": 3,
                "eligible_count": 2,
                "blocked_count": 1,
                "purchases": [
                    {
                        "product_name": "Developer Toolkit",
                        "policy_facts": {"subscription_active": True},
                    }
                ],
            },
        },
    }

    message = format_trace_console_message(event)

    assert message.startswith(
        "AI graph step 5: Tool completed - Backend refund-eligibility tool "
        "completed. (tool=get_refund_eligibility, result=3 purchases, "
        "2 eligible, 1 blocked)"
    )
    assert "--- Tool Result ---" in message
    assert "summary: 3 purchases, 2 eligible, 1 blocked" in message
    assert "subscription_active" not in message

def test_trace_console_message_includes_model_context_state_and_provided_data() -> None:
    event = {
        "type": "model.requested",
        "step": 6,
        "message": "Sending final-response package to the model.",
        "data": {
            "phase": "final_response",
            "model": "gpt-5.4-mini",
            "messages": [{}, {}, {}, {}],
            "tools": [],
            "model_context": {
                "conversation_state": (
                    "type=subscription, product=Developer Toolkit, "
                    "purchase=40000000, selected=1, refund_selected=1, "
                    "refund_context=product"
                ),
                "page_context": "purchase_detail:40000000",
                "page_reference": (
                    "surface=purchase_detail, product=Developer Toolkit, "
                    "type=subscription, id=40000000"
                ),
                "tool_results": (
                    "get_refund_eligibility:1 purchases, 1 eligible, 0 blocked"
                ),
                "intents": "account,eligibility",
            },
        },
    }

    message = format_trace_console_message(event)

    assert "phase=final_response" in message
    assert "tools=none" in message
    assert "state=type=subscription, product=Developer Toolkit" in message
    assert "page=purchase_detail:40000000" in message
    assert "page_ref=surface=purchase_detail, product=Developer Toolkit" in message
    assert "provided=get_refund_eligibility:1 purchases, 1 eligible, 0 blocked" in message
    assert "intents=account,eligibility" in message

def test_trace_console_message_includes_blocked_action_context() -> None:
    event = {
        "type": "response.blocked",
        "step": 4,
        "message": "Blocked refund request outside the current AI phase.",
        "data": {
            "reason": "workflow_not_ready",
            "model_context": {
                "conversation_state": (
                    "type=subscription, product=Developer Toolkit, purchase=40000000"
                ),
                "page_context": "purchase_history",
                "tool_results": None,
                "blocked_intent": "workflow",
            },
        },
    }

    message = format_trace_console_message(event)

    assert "reason=workflow_not_ready" in message
    assert "state=type=subscription, product=Developer Toolkit" in message
    assert "page=purchase_history" in message
    assert "blocked=workflow" in message

def test_chat_graph_emits_structured_graph_tool_and_response_log_events(caplog) -> None:
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=FakeModelClient(),
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Show my purchases",
            customer_id=CUSTOMER_ID,
            purchase_id=PURCHASE_ID,
        )

    assert result.content == "You made 2 digital purchases totaling $75.00."
    events = [record.event for record in caplog.records]
    assert [event["type"] for event in events] == [
        "graph.started",
        "model.requested",
        "tool_call.requested",
        "workflow.classified",
        "workflow.context_resolved",
        "workflow.executing",
        "workflow.tool_overridden",
        "tool_call.overridden",
        "tool_call.executing",
        "tool_call.completed",
        "workflow.completed",
        "workflow.state_updated",
        "model.requested",
        "response.generated",
    ]
    assert [event["step"] for event in events] == list(range(1, 15))
    assert events[1]["data"]["messages"][0]["content"].startswith(
        "You are RefundsAI's customer support assistant."
    )
    assert "Do not use Markdown" in events[1]["data"]["messages"][0]["content"]
    assert "unrelated topics" in events[1]["data"]["messages"][0]["content"]
    assert events[9]["data"]["result"]["aggregates"]["total_purchase_count"] == 4
    assert events[13]["data"]["assistant_response"] == (
        "You made 2 digital purchases totaling $75.00."
    )
    assert events[13]["file"].endswith(("services\\ai_chat.py", "services/ai_chat.py"))
    assert events[13]["line"] > 0
