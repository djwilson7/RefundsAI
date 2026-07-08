from __future__ import annotations

import json
from dataclasses import dataclass

from refunds_ai_api.services.ai_chat import AIChatService
from refunds_ai_api.services.ai_chat.model_context_projection import (
    build_model_context_projection,
)
from refunds_ai_api.services.ai_chat.token_budget import (
    ApproximateTokenCounter,
    build_token_budget_breakdown,
    count_serialized,
    get_token_counter,
)
from refunds_ai_api.services.ai_chat.tools import get_customer_purchase_history

from .fakes import CUSTOMER_ID, FakeApplicationService, NoToolModelClient


@dataclass(frozen=True)
class CharacterTokenCounter:
    name: str = "test_characters"

    def count_text(self, value: str) -> int:
        return len(value)


@dataclass(frozen=True)
class FailingTokenCounter:
    name: str = "failing_tokenizer"

    def count_text(self, value: str) -> int:
        raise RuntimeError("tokenizer unavailable")


def test_plain_string_counting_uses_selected_counter() -> None:
    counter = CharacterTokenCounter()

    assert counter.count_text("four") == 4


def test_serialized_object_counting_uses_stable_json() -> None:
    counter = CharacterTokenCounter()
    value = {"b": 2, "a": [1]}

    assert count_serialized(value, counter) == len(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def test_fallback_approximation_is_explicit_and_safe() -> None:
    counter = get_token_counter("gpt-5.4-mini", force_fallback=True)

    assert counter.name == "approx_chars_div_4"
    assert isinstance(counter, ApproximateTokenCounter)
    assert counter.count_text("") == 0
    assert counter.count_text("12345") == 2


def test_openai_tokenizer_is_used_when_available() -> None:
    counter = get_token_counter("gpt-5.4-mini")

    assert counter.name.startswith("tiktoken:")
    assert counter.count_text("hello") > 0


def test_runtime_tokenizer_failure_uses_approximation() -> None:
    breakdown = build_token_budget_breakdown(
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": "12345"}],
        tools=[],
        current_user_message="12345",
        request_id="request-1",
        customer_id=None,
        page=None,
        counter=FailingTokenCounter(),
    )

    assert breakdown["tokenizer"] == "approx_chars_div_4"
    assert breakdown["components"]["current_user_message"] == 2


def test_unknown_messages_are_counted_as_other_with_safe_label() -> None:
    breakdown = build_token_budget_breakdown(
        model="gpt-5.4-mini",
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
            {"role": "user", "content": "uncategorized instruction"},
        ],
        tools=[],
        current_user_message="hello",
        request_id="request-1",
        customer_id="customer-1",
        page="purchase_history",
        counter=CharacterTokenCounter(),
    )

    assert breakdown["components"]["system_prompt"] == len("system")
    assert breakdown["components"]["current_user_message"] == len("hello")
    assert breakdown["components"]["other_messages"] == len(
        "uncategorized instruction"
    )
    assert breakdown["uncategorized_labels"] == ["user_message_2"]


def test_output_tokens_are_counted_after_model_response() -> None:
    breakdown = build_token_budget_breakdown(
        model="gpt-5.4-mini",
        messages=[{"role": "user", "content": "hello"}],
        tools=[],
        current_user_message="hello",
        request_id="request-1",
        customer_id=None,
        page=None,
        output_text="model output",
        counter=CharacterTokenCounter(),
    )

    assert breakdown["output_tokens_estimated"] == len("model output")


def test_chat_model_call_logs_breakdown_without_changing_response(caplog) -> None:
    expected_response = "You have 2 digital purchases."
    service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=NoToolModelClient(expected_response),
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.token_budget"):
        result = service.create_response(
            message="Can you list all of my digital purchases please",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == expected_response
    budget_events = [
        record.event
        for record in caplog.records
        if hasattr(record, "event") and record.event["type"] == "model.token_budget"
    ]
    assert len(budget_events) == 1
    breakdown = budget_events[0]["data"]
    assert breakdown["components"]["system_prompt"] > 0
    assert breakdown["components"]["current_user_message"] > 0
    assert breakdown["components"]["tool_results"] > 0
    assert breakdown["output_tokens_estimated"] > 0
    assert breakdown["input_tokens_total_estimated"] == sum(
        breakdown["components"].values()
    )
    assert breakdown["request_category"] == "purchase_list"
    assert breakdown["raw_context_tokens"] > breakdown["projected_context_tokens"]
    assert breakdown["token_savings_estimated"] > 0


def test_model_context_projection_keeps_raw_purchase_rows_out_of_model_context() -> None:
    raw_result = {
        "tool_call_id": "tool-call-1",
        "name": "get_customer_purchase_history",
        "result": get_customer_purchase_history(FakeApplicationService(), CUSTOMER_ID),
    }
    state = {
        "message": "How many digital purchases have I made?",
        "workflow_kind": "account_fact",
        "conversation_state": {
            "selected_purchase_type": "digital",
            "selected_purchase_ids": [
                "40000000-0000-4000-8000-000000000001",
                "40000000-0000-4000-8000-000000000002",
            ],
        },
    }

    projection = build_model_context_projection(
        state=state,
        tool_results=[raw_result],
        counter=get_token_counter("gpt-5.4-mini"),
    )

    projected = projection.projected_tool_results[0]["result"]["purchases"]
    assert projection.request_category == "purchase_count_by_group"
    assert projection.raw_context_tokens > projection.projected_context_tokens
    assert projection.token_savings_estimated > 0
    assert projected == [
        {
            "product_name": "Design Template Pack",
            "purchase_type": "digital",
            "amount_display": "$45.00",
            "purchased_date_display": "June 20, 2026",
            "status": "completed",
        },
        {
            "product_name": "Icon Set",
            "purchase_type": "digital",
            "amount_display": "$30.00",
            "purchased_date_display": "June 21, 2026",
            "status": "redeemed",
        },
    ]
    assert "id" not in projected[0]
    assert "order_number" not in projected[0]
