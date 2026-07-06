from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from refunds_ai_api.main import create_app
from refunds_ai_api.routes.chat import get_ai_chat_service
from refunds_ai_api.services.ai_chat import (
    ACCOUNT_DATA_REQUIRED_RESPONSE,
    CHAT_UNAVAILABLE_RESPONSE,
    CUSTOMER_CONTEXT_REQUIRED_RESPONSE,
    EMPTY_CONVERSATION_STATE,
    AIChatResult,
    AIChatService,
    ModelToolCall,
    ModelTurn,
    format_trace_console_message,
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
)
from refunds_ai_api.services.dates import (
    build_inclusive_date_range,
    format_date,
    get_timezone,
    is_datetime_in_inclusive_date_range,
)
from refunds_ai_api.services.money import cents_to_dollars, dollars_to_cents
from refunds_ai_api.services.refund_policy_catalog import get_refund_policy

CUSTOMER_ID = "20000000-0000-4000-8000-000000000001"
PURCHASE_ID = "40000000-0000-4000-8000-000000000001"


class FakeModelClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        if self.fail:
            raise RuntimeError("model offline")

        self.calls.append({"messages": messages, "tools": tools})

        if len(self.calls) == 1:
            return ModelTurn(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="tool-call-1",
                        name="get_customer_purchase_history",
                        arguments={"customer_id": "not-the-active-customer"},
                    )
                ],
            )

        return ModelTurn(
            content="You made 2 digital purchases totaling $75.00.",
            tool_calls=[],
        )


class FakeApplicationService:
    def __init__(self) -> None:
        self.purchase_requests: list[str] = []
        self.refund_workflow_called = False
        self.refund_workflow_requests: list[str] = []

    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        self.purchase_requests.append(user_id)
        return [
            {
                "id": PURCHASE_ID,
                "order_number": "RAI-10001",
                "purchase_type": "digital",
                "product_name": "Design Template Pack",
                "sku": "DIG-TEMPLATE-001",
                "amount_cents": 4500,
                "purchased_at": datetime(2026, 6, 20, 14, 30, tzinfo=UTC),
                "status": "completed",
                "details_url": f"/api/purchases/{PURCHASE_ID}/details",
            },
            {
                "id": "40000000-0000-4000-8000-000000000002",
                "order_number": "RAI-10002",
                "purchase_type": "digital",
                "product_name": "Icon Set",
                "sku": "DIG-ICONS-001",
                "amount_cents": 3000,
                "purchased_at": datetime(2026, 6, 21, 14, 30, tzinfo=UTC),
                "status": "redeemed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000002/details",
            },
            {
                "id": "40000000-0000-4000-8000-000000000003",
                "order_number": "RAI-10003",
                "purchase_type": "physical",
                "product_name": "Keyboard",
                "sku": "PHY-KEYBOARD-001",
                "amount_cents": 12500,
                "purchased_at": datetime(2026, 6, 22, 14, 30, tzinfo=UTC),
                "status": "completed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000003/details",
            },
            {
                "id": "40000000-0000-4000-8000-000000000004",
                "order_number": "RAI-10004",
                "purchase_type": "subscription",
                "product_name": "Pro Subscription",
                "sku": "SUB-PRO-001",
                "amount_cents": 999,
                "purchased_at": datetime(2026, 6, 23, 14, 30, tzinfo=UTC),
                "status": "subscribed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000004/details",
            },
        ]

    def get_refund_workflow(self, purchase_id: str) -> dict[str, Any]:
        self.refund_workflow_called = True
        self.refund_workflow_requests.append(purchase_id)
        workflows = {
            PURCHASE_ID: {
                "purchase_id": PURCHASE_ID,
                "purchase_type": "digital",
                "can_enter_refund_workflow": True,
                "can_prepare_refund": True,
                "can_issue_funds": False,
                "refund_stage": "eligible",
                "required_action": "invalidate_digital_entitlement",
                "refundable_amount_cents": 4500,
                "refund_outcome": "full",
                "reasons": [],
                "policy_facts": {
                    "purchase_status": "completed",
                    "code_redeemed": False,
                },
            },
            "40000000-0000-4000-8000-000000000002": {
                "purchase_id": "40000000-0000-4000-8000-000000000002",
                "purchase_type": "digital",
                "can_enter_refund_workflow": False,
                "can_prepare_refund": False,
                "can_issue_funds": False,
                "refund_stage": "blocked",
                "required_action": "none",
                "refundable_amount_cents": 0,
                "refund_outcome": "none",
                "reasons": ["digital_entitlement_redeemed"],
                "policy_facts": {
                    "purchase_status": "redeemed",
                    "code_redeemed": True,
                },
            },
            "40000000-0000-4000-8000-000000000003": {
                "purchase_id": "40000000-0000-4000-8000-000000000003",
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
            },
            "40000000-0000-4000-8000-000000000004": {
                "purchase_id": "40000000-0000-4000-8000-000000000004",
                "purchase_type": "subscription",
                "can_enter_refund_workflow": True,
                "can_prepare_refund": True,
                "can_issue_funds": False,
                "refund_stage": "eligible",
                "required_action": "cancel_subscription",
                "refundable_amount_cents": 999,
                "refund_outcome": "full",
                "reasons": [],
                "policy_facts": {
                    "purchase_status": "subscribed",
                    "subscription_active": True,
                },
            },
            "40000000-0000-4000-8000-000000000005": {
                "purchase_id": "40000000-0000-4000-8000-000000000005",
                "purchase_type": "subscription",
                "can_enter_refund_workflow": True,
                "can_prepare_refund": True,
                "can_issue_funds": False,
                "refund_stage": "eligible",
                "required_action": "cancel_subscription",
                "refundable_amount_cents": 3999,
                "refund_outcome": "full",
                "reasons": [],
                "policy_facts": {
                    "purchase_status": "subscribed",
                    "subscription_active": True,
                },
            },
        }
        return workflows[purchase_id]

    def request_refund(self, purchase_id: str) -> dict[str, Any]:
        raise AssertionError("Refund mutations must not be called by chat graph.")

    def issue_refund(self, purchase_id: str) -> dict[str, Any]:
        raise AssertionError("Refund mutations must not be called by chat graph.")


class DeveloperToolkitApplicationService(FakeApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        purchases = super().list_user_purchases(user_id)
        return [
            {
                "id": "40000000-0000-4000-8000-000000000005",
                "order_number": "RAI-10005",
                "purchase_type": "subscription",
                "product_name": "Developer Toolkit",
                "sku": "SUB-DEVELOPER-TOOLKIT",
                "amount_cents": 3999,
                "purchased_at": datetime(2026, 6, 24, 14, 30, tzinfo=UTC),
                "status": "subscribed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000005/details",
            },
            *purchases,
        ]


class AmbiguousProductApplicationService(DeveloperToolkitApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        purchases = super().list_user_purchases(user_id)
        return [
            {
                "id": "40000000-0000-4000-8000-000000000006",
                "order_number": "RAI-10006",
                "purchase_type": "subscription",
                "product_name": "Developer Toolkit Plus",
                "sku": "SUB-DEVELOPER-TOOLKIT-PLUS",
                "amount_cents": 5999,
                "purchased_at": datetime(2026, 6, 25, 14, 30, tzinfo=UTC),
                "status": "subscribed",
                "details_url": "/api/purchases/40000000-0000-4000-8000-000000000006/details",
            },
            *purchases,
        ]


class UnknownToolModelClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        self.calls += 1

        if self.calls == 1:
            return ModelTurn(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="tool-call-unknown",
                        name="unsupported_tool",
                        arguments={},
                    )
                ],
            )

        return ModelTurn(content="You made 4 purchases.", tool_calls=[])


class NoToolModelClient:
    def __init__(self, response: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        self.calls.append({"messages": messages, "tools": tools})

        if len(self.calls) == 1:
            return ModelTurn(content=None, tool_calls=[])

        return ModelTurn(content=self.response, tool_calls=[])


class BroadHistoryForDateRangeModelClient:
    def __init__(self, response: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        self.calls.append({"messages": messages, "tools": tools})

        if len(self.calls) == 1:
            return ModelTurn(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="tool-call-broad-history",
                        name="get_customer_purchase_history",
                        arguments={},
                    )
                ],
            )

        return ModelTurn(content=self.response, tool_calls=[])


class ToolCallingModelClient:
    def __init__(self, tool_call: ModelToolCall, response: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self.tool_call = tool_call
        self.response = response

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        self.calls.append({"messages": messages, "tools": tools})

        if len(self.calls) == 1:
            return ModelTurn(content=None, tool_calls=[self.tool_call])

        return ModelTurn(content=self.response, tool_calls=[])


class LeakyFinalResponseModelClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        self.calls.append({"messages": messages, "tools": tools})

        if len(self.calls) == 1:
            return ModelTurn(content=None, tool_calls=[])

        return ModelTurn(
            content="The selected context resolver picked this purchase_ids state.",
            tool_calls=[],
        )


class MalformedPseudoToolModelClient:
    def __init__(self, response: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        self.calls.append({"messages": messages, "tools": tools})

        if len(self.calls) == 1:
            return ModelTurn(
                content='to=get_customer_purchase_history  {}',
                tool_calls=[],
            )

        return ModelTurn(content=self.response, tool_calls=[])


class GuardedNoToolChatService(AIChatService):
    def _execute_tools(self, state):  # type: ignore[no-untyped-def]
        return {**state, "tool_results": [], "account_fact_intent": True}


class FinalFailureModelClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        self.calls += 1

        if self.calls == 1:
            return ModelTurn(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="tool-call-1",
                        name="get_customer_purchase_history",
                        arguments={"customer_id": "not-the-active-customer"},
                    )
                ],
            )

        raise RuntimeError("final model offline")


class FailingPurchaseApplicationService(FakeApplicationService):
    def list_user_purchases(self, user_id: str) -> list[dict[str, Any]]:
        raise RuntimeError("database offline")


class StaticChatService:
    def create_response(
        self,
        *,
        message: str,
        customer_id: str | None,
        purchase_id: str | None,
        page_context: dict[str, Any] | None = None,
        conversation_state: dict[str, Any] | None = None,
        trace_step_start: int = 1,
    ) -> AIChatResult:
        return AIChatResult(
            content=f"Received {message}",
            graph_ready=True,
            conversation_state=conversation_state or dict(EMPTY_CONVERSATION_STATE),
            next_trace_step=trace_step_start,
        )


def build_client(chat_service: Any) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_ai_chat_service] = lambda: chat_service
    return TestClient(app)


def test_chat_endpoint_returns_graph_response() -> None:
    client = build_client(StaticChatService())

    response = client.post(
        "/api/chat",
        json={
            "message": "How many digital purchases have I made?",
            "customer_id": CUSTOMER_ID,
            "purchase_id": PURCHASE_ID,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "message": {
            "role": "assistant",
            "content": "Received How many digital purchases have I made?",
        },
        "model": "gpt-5.4-mini",
        "graph_ready": True,
        "conversation_state": EMPTY_CONVERSATION_STATE,
    }
    assert body["error"] is None
    assert "timestamp" in body["meta"]


def test_chat_endpoint_rejects_empty_messages() -> None:
    client = build_client(StaticChatService())

    response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"] == {
        "code": "INVALID_CHAT_MESSAGE",
        "message": "Chat message must not be empty.",
    }
    assert "timestamp" in body["meta"]


def test_chat_endpoint_rejects_missing_messages() -> None:
    client = build_client(StaticChatService())

    response = client.post("/api/chat", json={})

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "INVALID_CHAT_MESSAGE",
        "message": "Chat message must not be empty.",
    }


def test_chat_graph_calls_purchase_history_tool_and_returns_model_response() -> None:
    application_service = FakeApplicationService()
    model_client = FakeModelClient()
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    result = chat_service.create_response(
        message="How many digital purchases have I made?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert result.content == "You made 2 digital purchases totaling $75.00."
    assert result.graph_ready is True
    assert result.conversation_state["selected_purchase_ids"] == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
    ]
    assert application_service.purchase_requests == [CUSTOMER_ID]
    assert application_service.refund_workflow_called is False
    assert len(model_client.calls) == 2
    system_prompt = model_client.calls[0]["messages"][0]["content"]
    assert "Return plain standard text only." in system_prompt
    assert "Do not use Markdown" in system_prompt
    assert "Keep the conversation grounded" in system_prompt
    assert "gracefully redirect" in system_prompt
    assert "unrelated topics" in system_prompt
    assert model_client.calls[1]["tools"] == []
    tool_schemas = model_client.calls[0]["tools"]
    assert [tool_schema["name"] for tool_schema in tool_schemas] == [
        "get_customer_purchase_history",
        "get_purchase_count_by_amount_threshold",
        "get_purchase_history_by_date_range",
        "get_refund_policy",
        "get_refund_eligibility",
    ]
    assert tool_schemas[0]["parameters"] == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    assert tool_schemas[1]["parameters"]["required"] == ["threshold_cents", "comparison"]
    assert tool_schemas[2]["parameters"]["required"] == [
        "start_date",
        "end_date",
        "timezone",
    ]
    assert tool_schemas[3]["parameters"]["required"] == ["scope"]
    assert tool_schemas[4]["parameters"]["required"] == ["purchase_ids"]


def test_chat_graph_asks_for_customer_context_without_customer_id() -> None:
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=FakeModelClient(),
    )

    result = chat_service.create_response(
        message="How many digital purchases have I made?",
        customer_id=None,
        purchase_id=None,
    )

    assert result == AIChatResult(
        content=CUSTOMER_CONTEXT_REQUIRED_RESPONSE,
        graph_ready=True,
    )


def test_chat_graph_returns_graceful_response_without_openai_api_key(caplog) -> None:
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=None,
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Show my purchases",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result == AIChatResult(content=CHAT_UNAVAILABLE_RESPONSE, graph_ready=False)
    assert caplog.records[0].event["type"] == "model.failure"
    assert caplog.records[0].event["step"] == 2
    assert caplog.records[0].event["data"] == {
        "reason": "missing_openai_api_key",
        "model": "gpt-5.4-mini",
    }


def test_chat_graph_returns_graceful_response_when_model_fails(caplog) -> None:
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=FakeModelClient(fail=True),
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Show my purchases",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result == AIChatResult(content=CHAT_UNAVAILABLE_RESPONSE, graph_ready=True)
    assert caplog.records[0].event == {
        "type": "model.failure",
        "reason": "RuntimeError",
        "detail": "model offline",
        "model": "gpt-5.4-mini",
    }


def test_chat_graph_forces_purchase_history_tool_when_model_requests_unknown_tool() -> None:
    application_service = FakeApplicationService()
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=UnknownToolModelClient(),
    )

    result = chat_service.create_response(
        message="Summarize my purchases",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert result.content == "You made 4 purchases."
    assert result.graph_ready is True
    assert result.conversation_state["current_page"] == {
        "surface": "purchase_history",
        "purchase": None,
    }
    assert application_service.purchase_requests == [CUSTOMER_ID]


def test_chat_graph_skips_purchase_history_tool_for_off_domain_message(caplog) -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient(
        "I can help with account and purchase history, but I can't provide sports schedules."
    )
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="When are the Dallas Cowboys playing?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == (
        "I can help with account and purchase history, but I can't provide sports schedules."
    )
    assert application_service.purchase_requests == []
    assert len(model_client.calls) == 2
    assert model_client.calls[1]["tools"] == []
    assert [message["role"] for message in model_client.calls[1]["messages"]] == [
        "system",
        "user",
        "user",
        "user",
    ]
    assert model_client.calls[1]["messages"][2]["content"] == (
        'Current page reference: {"surface": "purchase_history", "purchase": null}'
    )
    assert not any(
        message["content"].startswith("Read-only account tool result:")
        for message in model_client.calls[1]["messages"]
    )
    assert [record.event["type"] for record in caplog.records] == [
        "graph.started",
        "model.requested",
        "tool_call.requested",
        "tool_call.skipped",
        "model.requested",
        "response.generated",
    ]
    assert caplog.records[3].event["data"] == {"reason": "off_domain_intent"}


def test_chat_graph_forces_purchase_history_tool_for_account_domain_message() -> None:
    application_service = FakeApplicationService()
    model_client = NoToolModelClient("You made 4 purchases.")
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    result = chat_service.create_response(
        message="Can you summarize my orders?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert result.content == "You made 4 purchases."
    assert application_service.purchase_requests == [CUSTOMER_ID]
    assert any(
        message["content"].startswith("Read-only account tool result:")
        for message in model_client.calls[1]["messages"]
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
    ignored_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.ignored"
    )
    assert ignored_event["data"]["reason"] == "policy_intent_not_detected"


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
    forbidden_terms = (
        "selected context",
        "resolver",
        "purchase_ids",
        "state",
        "node",
        "graph",
    )
    assert not any(term in result.content.casefold() for term in forbidden_terms)


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

    assert second_result.content == "Developer Toolkit is eligible."
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
    model_client = BroadHistoryForDateRangeModelClient("Only backend eligibility was used.")
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

    assert result.content == "Only backend eligibility was used."
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

    assert result.content == "Three purchases are eligible and one is blocked."
    assert application_service.refund_workflow_requests == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
        "40000000-0000-4000-8000-000000000003",
        "40000000-0000-4000-8000-000000000004",
    ]
    assert result.conversation_state["selected_refund_context"] == "all_purchases"
    forced_event = next(
        record.event for record in caplog.records if record.event["type"] == "tool_call.forced"
    )
    assert forced_event["data"]["context"] == "all_purchases"


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

    assert result.content == "Developer Toolkit is eligible under subscription rules."
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
    assert result.conversation_state["selected_refund_context"] == "product"
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

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Please check refund handling.",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "The purchase is eligible."
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

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        result = chat_service.create_response(
            message="Can I refund the Developer Toolkit?",
            customer_id=CUSTOMER_ID,
            purchase_id=None,
        )

    assert result.content == "Developer Toolkit is eligible."
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

    assert result.content == "Developer Toolkit is eligible."
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
    assert len(model_client.calls) == 1
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

    assert result.content == "This item is eligible to begin refund handling."
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

    assert result.content == "Keyboard is eligible for a return label."
    assert result.conversation_state["active_refund_context"] == {
        "purchase_id": "40000000-0000-4000-8000-000000000003",
        "product_name": "Keyboard",
        "purchase_type": "physical",
        "eligible": True,
        "stage": "awaiting_return_label",
        "next_action": "generate_return_label",
        "reason_codes": [],
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
        "Keyboard is eligible, and the next required step is generating a return "
        "label. That workflow action is not wired yet."
    )
    assert application_service.purchase_requests == []
    assert application_service.refund_workflow_requests == []
    assert len(model_client.calls) == 1
    blocked_event = next(
        record.event for record in caplog.records if record.event["type"] == "response.blocked"
    )
    assert blocked_event["data"]["purchase_id"] == (
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
        "Please confirm the product name or order number before continuing the refund workflow."
    )
    assert application_service.purchase_requests == []
    assert application_service.refund_workflow_requests == []
    assert len(model_client.calls) == 1


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

    assert result.content == "Design Template Pack is eligible."
    assert result.conversation_state["active_refund_context"] == {
        "purchase_id": PURCHASE_ID,
        "product_name": "Design Template Pack",
        "purchase_type": "digital",
        "eligible": True,
        "stage": "eligibility_confirmed",
        "next_action": "invalidate_digital_entitlement",
        "reason_codes": [],
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

    assert result.content == "Developer Toolkit is eligible as a subscription."
    assert application_service.refund_workflow_requests == [
        "40000000-0000-4000-8000-000000000005"
    ]
    assert result.conversation_state["selected_product"] == "Developer Toolkit"
    assert result.conversation_state["selected_purchase_type"] == "subscription"
    assert result.conversation_state["selected_purchase_ids"] == [
        "40000000-0000-4000-8000-000000000005"
    ]
    assert result.conversation_state["selected_scope_label"] is None


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
        "I can explain refund policy, but I cannot start or change a refund workflow yet."
    )
    assert application_service.refund_workflow_requests == []
    assert len(model_client.calls) == 1


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
    assert "tool_call.executing" not in event_types
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
        "June 20 through June 22, 2026"
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


def test_purchase_history_fallback_intent_classifier_handles_account_domain_terms() -> None:
    assert should_force_purchase_history_tool("Can you summarize my orders?") is True
    assert should_force_purchase_history_tool("What's my account activity?") is True
    assert should_force_purchase_history_tool("How many puchases have I made?") is True
    assert should_force_purchase_history_tool("When are the Dallas Cowboys playing?") is False
    assert should_force_purchase_history_tool("How do I reverse a linked list?") is False


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
    assert caplog.records[0].event == {
        "type": "model.failure",
        "reason": "RuntimeError",
        "detail": "final model offline",
        "model": "gpt-5.4-mini",
    }


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

    assert message == (
        "AI graph step 2: Model requested - Sending tool-selection package to the "
        "model. (phase=tool_selection, model=gpt-5.4-mini, messages=2, "
        "tools=get_customer_purchase_history, get_refund_eligibility)"
    )
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

    assert message == (
        "AI graph step 5: Tool completed - Backend refund-eligibility tool "
        "completed. (tool=get_refund_eligibility, result=3 purchases, "
        "2 eligible, 1 blocked)"
    )
    assert "Developer Toolkit" not in message
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


def test_chat_endpoint_emits_structured_route_log_events(caplog) -> None:
    client = build_client(StaticChatService())

    with caplog.at_level("INFO", logger="refunds_ai_api.chat"):
        response = client.post(
            "/api/chat",
            json={
                "message": "Show my purchases",
                "customer_id": CUSTOMER_ID,
                "purchase_id": PURCHASE_ID,
            },
        )

    assert response.status_code == 200
    events = [record.event for record in caplog.records]
    assert [event["type"] for event in events] == [
        "message.received",
        "route.response_returned",
    ]
    assert [event["step"] for event in events] == [1, 2]
    assert events[0]["data"] == {
        "message": "Show my purchases",
        "message_length": len("Show my purchases"),
        "customer_id": CUSTOMER_ID,
        "purchase_id": PURCHASE_ID,
        "page_context": None,
        "conversation_state": None,
    }
    assert events[0]["file"].endswith(("routes\\chat.py", "routes/chat.py"))
    assert events[0]["line"] > 0
    assert events[1]["data"]["response"]["message"]["content"] == "Received Show my purchases"
    assert events[1]["data"]["response"]["conversation_state"] == EMPTY_CONVERSATION_STATE


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
        "tool_call.executing",
        "tool_call.completed",
        "model.requested",
        "response.generated",
    ]
    assert [event["step"] for event in events] == [1, 2, 3, 4, 5, 6, 7]
    assert events[1]["data"]["messages"][0]["content"].startswith(
        "You are RefundsAI's customer support assistant."
    )
    assert "Do not use Markdown" in events[1]["data"]["messages"][0]["content"]
    assert "unrelated topics" in events[1]["data"]["messages"][0]["content"]
    assert events[4]["data"]["result"]["aggregates"]["total_purchase_count"] == 4
    assert events[6]["data"]["assistant_response"] == (
        "You made 2 digital purchases totaling $75.00."
    )
    assert events[6]["file"].endswith(("services\\ai_chat.py", "services/ai_chat.py"))
    assert events[6]["line"] > 0


def test_openapi_documents_chat_endpoint() -> None:
    client = build_client(StaticChatService())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/chat" in response.json()["paths"]
