from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from refunds_ai_api.services.ai_chat import (
    AIChatService,
    get_customer_purchase_history,
    get_purchase_count_by_amount_threshold,
    get_purchase_history_by_date_range,
    get_refund_eligibility,
    get_refund_eligibility_tool_schema,
    parse_amount_threshold_query,
    parse_date_range_query,
    parse_model_refund_eligibility_arguments,
    parse_refund_policy_query,
    parse_tool_arguments,
    should_force_purchase_history_tool,
    validate_customer_account,
    validate_customer_account_tool_schema,
)
from refunds_ai_api.services.dates import (
    build_inclusive_date_range,
    format_date,
    get_timezone,
    is_datetime_in_inclusive_date_range,
)
from refunds_ai_api.services.money import cents_to_dollars, dollars_to_cents
from refunds_ai_api.services.refund_policy_catalog import get_refund_policy

from .fakes import (
    CUSTOMER_ID,
    PURCHASE_ID,
    FakeApplicationService,
    MalformedPseudoToolModelClient,
    NoToolModelClient,
)


def test_threshold_tool_returns_count_ids_total_and_threshold_context() -> None:
    result = get_purchase_count_by_amount_threshold(
        FakeApplicationService(),
        CUSTOMER_ID,
        threshold_cents=10000,
        comparison="gt",
    )

    assert result == {
        "count": 1,
        "matching_purchase_ids": ["40000000-0000-4000-8000-000000000003"],
        "total_amount_cents": 12500,
        "total_amount_dollars": "125.00",
        "threshold_cents": 10000,
        "threshold_dollars": "100.00",
        "comparison": "gt",
    }

def test_refund_eligibility_tool_returns_backend_workflow_results() -> None:
    application_service = FakeApplicationService()

    result = get_refund_eligibility(
        application_service,
        CUSTOMER_ID,
        purchase_ids=[
            PURCHASE_ID,
            PURCHASE_ID,
            "not-an-active-purchase",
            "40000000-0000-4000-8000-000000000002",
        ],
        context="digital",
    )

    assert result["context"] == "digital"
    assert result["requested_purchase_ids"] == [
        PURCHASE_ID,
        PURCHASE_ID,
        "not-an-active-purchase",
        "40000000-0000-4000-8000-000000000002",
    ]
    assert result["resolved_purchase_ids"] == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
    ]
    assert result["purchase_count"] == 2
    assert result["eligible_count"] == 1
    assert result["blocked_count"] == 1
    assert result["prepared_count"] == 0
    assert result["issued_count"] == 0
    assert result["purchases"][0]["product_name"] == "Design Template Pack"
    assert result["purchases"][0]["required_action"] == "invalidate_digital_entitlement"
    assert result["purchases"][1]["reasons"] == ["digital_entitlement_redeemed"]
    assert application_service.refund_workflow_requests == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
    ]

def test_refund_eligibility_tool_schema_and_argument_validation() -> None:
    schema = get_refund_eligibility_tool_schema()

    assert schema["name"] == "get_refund_eligibility"
    assert schema["parameters"]["required"] == ["purchase_ids"]
    assert parse_model_refund_eligibility_arguments(
        {"purchase_ids": [PURCHASE_ID], "context": "product"}
    ) == {"purchase_ids": [PURCHASE_ID], "context": "product"}
    assert parse_model_refund_eligibility_arguments(
        {"purchase_ids": [PURCHASE_ID], "context": ""}
    ) == {"purchase_ids": [PURCHASE_ID], "context": "model_requested"}
    assert parse_model_refund_eligibility_arguments({"purchase_ids": []}) is None
    assert parse_model_refund_eligibility_arguments({"purchase_ids": [1]}) is None

def test_validate_customer_account_tool_uses_active_customer_context() -> None:
    schema = validate_customer_account_tool_schema()

    assert schema["name"] == "validate_customer_account"
    assert schema["parameters"] == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    result = validate_customer_account(FakeApplicationService(), CUSTOMER_ID)

    assert result == {
        "customer_id": CUSTOMER_ID,
        "valid": True,
        "display_name": "Avery Customer",
        "first_name": "Avery",
        "last_name": "Customer",
        "roles": [{"key": "customer", "name": "Customer"}],
    }

def test_validate_customer_account_tool_returns_invalid_for_unknown_customer() -> None:
    class UnknownCustomerApplicationService(FakeApplicationService):
        def get_user(self, user_id: str) -> dict[str, object]:
            raise LookupError(user_id)

    result = validate_customer_account(
        UnknownCustomerApplicationService(),
        "20000000-0000-4000-8000-000000009999",
    )

    assert result == {
        "customer_id": "20000000-0000-4000-8000-000000009999",
        "valid": False,
        "display_name": None,
        "first_name": None,
        "last_name": None,
        "roles": [],
    }

def test_chat_graph_forces_threshold_tool_after_malformed_pseudo_tool_output(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = MalformedPseudoToolModelClient("You have 1 purchase over $100.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="How many purchases have I made over $100?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "You have 1 purchase over $100."
    assert application_service.purchase_requests == [CUSTOMER_ID]
    events = [record.event for record in caplog.records]
    assert "model.invalid_tool_output" in [event["type"] for event in events]
    forced_event = next(event for event in events if event["type"] == "tool_call.forced")
    assert forced_event["data"] == {
        "tool_name": "get_purchase_count_by_amount_threshold",
        "reason": "amount_threshold_intent",
        "threshold_cents": 10000,
        "comparison": "gt",
    }
    response_event = next(event for event in events if event["type"] == "response.generated")
    assert response_event["data"]["tool_result_count"] == 1
    final_messages = model_client.calls[1]["messages"]
    assert any(
        "get_purchase_count_by_amount_threshold" in message["content"]
        for message in final_messages
    )

def test_purchase_threshold_parser_handles_typo_purchase_intent() -> None:
    assert parse_amount_threshold_query("How many puchases have I made over $100?") == {
        "threshold_cents": 10000,
        "comparison": "gt",
    }

def test_date_range_parser_handles_first_week_of_month() -> None:
    assert parse_date_range_query(
        "How many purchases did I make during the first week of May?",
        today=date(2026, 7, 5),
    ) == {
        "start_date": "2026-05-01",
        "end_date": "2026-05-07",
        "timezone": "America/Chicago",
        "label": "first week of May 2026",
    }

def test_date_range_parser_handles_previous_completed_week() -> None:
    assert parse_date_range_query(
        "How many orders did I make last week?",
        today=date(2026, 7, 5),
    ) == {
        "start_date": "2026-06-28",
        "end_date": "2026-07-04",
        "timezone": "America/Chicago",
        "label": "last week",
    }

def test_date_range_parser_handles_current_sunday_started_week() -> None:
    assert parse_date_range_query(
        "How many purchases have I made this week?",
        today=date(2026, 7, 5),
    ) == {
        "start_date": "2026-07-05",
        "end_date": "2026-07-05",
        "timezone": "America/Chicago",
        "label": "this week",
    }

def test_date_format_helper_is_cross_platform() -> None:
    assert format_date(
        datetime(2026, 6, 25, 14, 36, tzinfo=UTC),
        get_timezone("America/Chicago"),
    ) == "June 25, 2026"

def test_inclusive_local_date_range_uses_half_open_utc_bounds() -> None:
    timezone = get_timezone("America/Chicago")
    date_range = build_inclusive_date_range(
        start_date=date(2026, 6, 28),
        end_date=date(2026, 7, 4),
        timezone=timezone,
        label="last week",
    )

    assert date_range.start_at_utc == datetime(2026, 6, 28, 5, 0, tzinfo=UTC)
    assert date_range.end_before_utc == datetime(2026, 7, 5, 5, 0, tzinfo=UTC)
    assert is_datetime_in_inclusive_date_range(
        datetime(2026, 7, 5, 4, 59, 59, 999999, tzinfo=UTC),
        date_range,
    )
    assert not is_datetime_in_inclusive_date_range(
        datetime(2026, 7, 5, 5, 0, tzinfo=UTC),
        date_range,
    )

def test_money_conversion_helpers_keep_database_values_in_cents() -> None:
    assert dollars_to_cents(Decimal("100")) == 10000
    assert dollars_to_cents(Decimal("100.99")) == 10099
    assert dollars_to_cents(100) == 10000
    assert cents_to_dollars(10099) == Decimal("100.99")

def test_date_range_tool_returns_rows_aggregates_and_display_context() -> None:
    result = get_purchase_history_by_date_range(
        FakeApplicationService(),
        CUSTOMER_ID,
        start_date="2026-06-20",
        end_date="2026-06-22",
        timezone_name="America/Chicago",
        label="June 20, 2026 through June 22, 2026",
    )

    assert result["date_range"] == {
        "start_date": "2026-06-20",
        "end_date": "2026-06-22",
        "label": "June 20, 2026 through June 22, 2026",
        "timezone": "America/Chicago",
    }
    assert result["aggregates"]["total_purchase_count"] == 3
    assert result["aggregates"]["total_amount_cents"] == 20000
    assert result["aggregates"]["total_amount_dollars"] == "200.00"
    assert [purchase["id"] for purchase in result["purchases"]] == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
        "40000000-0000-4000-8000-000000000003",
    ]
    assert result["purchases"][2]["amount_display"] == "$125.00"
    assert result["purchases"][2]["purchased_date_display"] == "June 22, 2026"

def test_chat_graph_forces_date_range_tool_for_date_range_intent(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("You made 3 purchases from June 20 through June 22.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="How many purchases did I make between June 20 and June 22?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "You made 3 purchases from June 20 through June 22."
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"] == {
        "tool_name": "get_purchase_history_by_date_range",
        "reason": "date_range_intent",
        "start_date": "2026-06-20",
        "end_date": "2026-06-22",
        "timezone": "America/Chicago",
    }
    assert any(
        "get_purchase_history_by_date_range" in message["content"]
        for message in model_client.calls[1]["messages"]
    )

def test_policy_catalog_general_lookup_returns_all_sections() -> None:
    result = get_refund_policy(scope="general")

    section_keys = [section["key"] for section in result["sections"]]
    assert result["effective_date"] == "July 3, 2026"
    assert result["source"] == "docs/REFUND_POLICY.md"
    assert section_keys == [
        "physical",
        "digital",
        "subscription",
        "refund_processing",
        "administrative_review",
        "policy_updates",
    ]

def test_policy_catalog_digital_lookup_is_narrow() -> None:
    result = get_refund_policy(scope="product_type", purchase_type="digital")

    assert [section["key"] for section in result["sections"]] == ["digital"]
    facts = " ".join(result["sections"][0]["facts"])
    assert "15 calendar days" in facts
    assert "must not have been redeemed" in facts
    assert "30 calendar days" not in facts
    assert "prorated" not in facts

def test_policy_catalog_physical_lookup_is_narrow() -> None:
    result = get_refund_policy(scope="product_type", purchase_type="physical")

    assert [section["key"] for section in result["sections"]] == ["physical"]
    facts = " ".join(result["sections"][0]["facts"])
    assert "30 calendar days" in facts
    assert "accepted by the carrier" in facts
    assert "15 calendar days" not in facts
    assert "prorated" not in facts

def test_policy_catalog_subscription_lookup_is_narrow() -> None:
    result = get_refund_policy(scope="product_type", purchase_type="subscription")

    assert [section["key"] for section in result["sections"]] == ["subscription"]
    facts = " ".join(result["sections"][0]["facts"])
    assert "48 hours" in facts
    assert "prorated" in facts
    assert "current active billing period" in facts
    assert "auto-renewal" in facts

def test_policy_catalog_funds_release_lookup_returns_processing_context() -> None:
    result = get_refund_policy(scope="funds_release")

    assert [section["key"] for section in result["sections"]] == ["refund_processing"]
    facts = " ".join(result["sections"][0]["facts"])
    assert "3-10 business days" in facts

def test_refund_policy_parser_detects_policy_scope_and_product_type() -> None:
    assert parse_refund_policy_query("What is the refund policy for my digital products?") == {
        "scope": "product_type",
        "purchase_type": "digital",
    }
    assert parse_refund_policy_query("How long until funds are released?") == {
        "scope": "funds_release",
        "purchase_type": None,
    }
    assert parse_refund_policy_query("When do funds get released for a physical return?") == {
        "scope": "funds_release",
        "purchase_type": "physical",
    }
    assert parse_refund_policy_query(
        "What is the refund policy for those purchases?",
        conversation_state={"selected_purchase_type": "digital"},
    ) == {
        "scope": "product_type",
        "purchase_type": "digital",
    }

def test_purchase_history_fallback_intent_classifier_handles_account_domain_terms() -> None:
    assert should_force_purchase_history_tool("Can you summarize my orders?") is True
    assert should_force_purchase_history_tool("What's my account activity?") is True
    assert should_force_purchase_history_tool("How many puchases have I made?") is True
    assert should_force_purchase_history_tool("When are the Dallas Cowboys playing?") is False
    assert should_force_purchase_history_tool("How do I reverse a linked list?") is False

def test_purchase_history_tool_returns_rows_and_aggregates() -> None:
    application_service = FakeApplicationService()

    result = get_customer_purchase_history(application_service, CUSTOMER_ID)

    assert len(result["purchases"]) == 4
    assert result["purchases"][0] == {
        "id": PURCHASE_ID,
        "order_number": "RAI-10001",
        "purchase_type": "digital",
        "product_name": "Design Template Pack",
        "amount_cents": 4500,
        "amount_dollars": "45.00",
        "amount_display": "$45.00",
        "purchased_at": datetime(2026, 6, 20, 14, 30, tzinfo=UTC),
        "purchased_date_display": "June 20, 2026",
        "status": "completed",
    }
    assert result["aggregates"] == {
        "total_purchase_count": 4,
        "total_amount_cents": 20999,
        "total_amount_dollars": "209.99",
        "by_purchase_type": {
            "digital": {
                "count": 2,
                "total_amount_cents": 7500,
                "total_amount_dollars": "75.00",
            },
            "physical": {
                "count": 1,
                "total_amount_cents": 12500,
                "total_amount_dollars": "125.00",
            },
            "subscription": {
                "count": 1,
                "total_amount_cents": 999,
                "total_amount_dollars": "9.99",
            },
        },
        "by_status": {
            "completed": {
                "count": 2,
                "total_amount_cents": 17000,
                "total_amount_dollars": "170.00",
            },
            "redeemed": {
                "count": 1,
                "total_amount_cents": 3000,
                "total_amount_dollars": "30.00",
            },
            "subscribed": {
                "count": 1,
                "total_amount_cents": 999,
                "total_amount_dollars": "9.99",
            },
        },
    }

def test_parse_tool_arguments_handles_missing_invalid_and_non_object_values() -> None:
    assert parse_tool_arguments(None) == {}
    assert parse_tool_arguments("{") == {}
    assert parse_tool_arguments("[1, 2]") == {}
    assert parse_tool_arguments('{"customer_id": "customer-1"}') == {
        "customer_id": "customer-1"
    }
