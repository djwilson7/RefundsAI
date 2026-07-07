from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from refunds_ai_api.services.ai_chat import (
    CHAT_UNAVAILABLE_RESPONSE,
    CUSTOMER_CONTEXT_REQUIRED_RESPONSE,
    EMPTY_CONVERSATION_STATE,
    AIChatResult,
    AIChatService,
    ModelToolCall,
    ModelTurn,
)
from refunds_ai_api.services.audit import ModelAuditEventKey, ModelAuditSession, TokenUsage

from .fakes import (
    CUSTOMER_ID,
    PURCHASE_ID,
    FakeApplicationService,
    FakeModelClient,
    NoToolModelClient,
    StaticChatService,
    ToolCallingModelClient,
    UnknownToolModelClient,
    build_client,
)


class FakeAuditWriter:
    def __init__(self) -> None:
        self.started: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []
        self.completed: list[dict[str, object]] = []

    def start_session(self, **kwargs) -> ModelAuditSession:  # type: ignore[no-untyped-def]
        self.started.append(kwargs)
        return ModelAuditSession(
            id=uuid4(),
            trace_id=uuid4(),
            started_at=datetime.now(UTC),
        )

    def record_event(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.events.append(kwargs)

    def complete_session(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.completed.append({"status": "succeeded", **kwargs})

    def fail_session(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.completed.append({"status": "failed", **kwargs})


class FailingStartAuditWriter(FakeAuditWriter):
    def start_session(self, **kwargs) -> ModelAuditSession:  # type: ignore[no-untyped-def]
        raise RuntimeError("audit session timeout")


class FailingEventAuditWriter(FakeAuditWriter):
    def record_event(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("audit event timeout")


class TokenReportingModelClient:
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
                tool_calls=[],
                token_usage=TokenUsage(
                    prompt_tokens=3,
                    completion_tokens=2,
                    total_tokens=5,
                ),
            )
        return ModelTurn(
            content="You made 2 digital purchases.",
            tool_calls=[],
            token_usage=TokenUsage(
                prompt_tokens=7,
                completion_tokens=11,
                total_tokens=18,
            ),
        )


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
        "side_effects": [],
    }
    assert body["error"] is None
    assert "timestamp" in body["meta"]

def test_chat_endpoint_records_audit_session_events_and_metrics() -> None:
    audit_writer = FakeAuditWriter()
    chat_service = AIChatService(
        application_service=FakeApplicationService(),
        model="gpt-5.4-mini",
        model_client=TokenReportingModelClient(),
        audit_writer=audit_writer,  # type: ignore[arg-type]
    )
    client = build_client(chat_service)

    response = client.post(
        "/api/chat",
        json={
            "message": "How many digital purchases have I made?",
            "customer_id": CUSTOMER_ID,
            "purchase_id": PURCHASE_ID,
        },
    )

    assert response.status_code == 200
    assert audit_writer.started[0]["model_name"] == "gpt-5.4-mini"
    assert str(audit_writer.started[0]["customer_id"]) == CUSTOMER_ID
    event_keys = [event["event_key"] for event in audit_writer.events]
    assert event_keys[0:2] == [
        ModelAuditEventKey.REQUEST_RECEIVED,
        ModelAuditEventKey.GRAPH_STARTED,
    ]
    assert ModelAuditEventKey.TOOL_REQUESTED in event_keys
    assert ModelAuditEventKey.RESPONSE_GENERATED in event_keys
    assert event_keys[-1] == ModelAuditEventKey.RESPONSE_RETURNED
    assert [event["sequence_number"] for event in audit_writer.events] == list(
        range(1, len(audit_writer.events) + 1)
    )
    assert audit_writer.completed[0]["status"] == "succeeded"
    assert audit_writer.completed[0]["token_usage"] == TokenUsage(
        prompt_tokens=10,
        completion_tokens=13,
        total_tokens=23,
    )


def test_chat_endpoint_audit_write_failure_does_not_fail_response(caplog) -> None:
    chat_service = StaticChatService()
    chat_service.audit_writer = FailingEventAuditWriter()
    client = build_client(chat_service)

    with caplog.at_level("WARNING", logger="refunds_ai_api.chat"):
        response = client.post(
            "/api/chat",
            json={
                "message": "Show my purchases",
                "customer_id": CUSTOMER_ID,
                "purchase_id": PURCHASE_ID,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["message"]["content"] == "Received Show my purchases"
    assert body["data"]["message"]["content"] != CHAT_UNAVAILABLE_RESPONSE
    assert {record.event["type"] for record in caplog.records} == {"audit.write_failed"}


def test_chat_endpoint_audit_session_creation_failure_does_not_fail_response(caplog) -> None:
    chat_service = StaticChatService()
    chat_service.audit_writer = FailingStartAuditWriter()
    client = build_client(chat_service)

    with caplog.at_level("WARNING", logger="refunds_ai_api.audit"):
        response = client.post(
            "/api/chat",
            json={
                "message": "Show my purchases",
                "customer_id": CUSTOMER_ID,
                "purchase_id": PURCHASE_ID,
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["message"]["content"] == "Received Show my purchases"
    assert caplog.records[0].event["type"] == "audit.session_create_failed"


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
        "validate_customer_account",
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
    assert tool_schemas[1]["parameters"] == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    assert tool_schemas[2]["parameters"]["required"] == ["threshold_cents", "comparison"]
    assert tool_schemas[3]["parameters"]["required"] == [
        "start_date",
        "end_date",
        "timezone",
    ]
    assert tool_schemas[4]["parameters"]["required"] == ["scope"]
    assert tool_schemas[5]["parameters"]["required"] == ["purchase_ids"]

def test_chat_graph_executes_validate_customer_account_tool() -> None:
    application_service = FakeApplicationService()
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-validate-customer",
            name="validate_customer_account",
            arguments={},
        ),
        "You are signed in as Avery Customer.",
    )
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    result = chat_service.create_response(
        message="Who am I signed in as?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert result.content == "You are signed in as Avery Customer."
    assert model_client.calls[1]["tools"] == []
    tool_message = next(
        message
        for message in model_client.calls[1]["messages"]
        if message["content"].startswith("Read-only account tool result:")
    )
    assert "validate_customer_account" in tool_message["content"]
    assert "Avery Customer" in tool_message["content"]

def test_chat_graph_overrides_customer_validation_for_purchase_history_count() -> None:
    application_service = FakeApplicationService()
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-validate-customer",
            name="validate_customer_account",
            arguments={},
        ),
        "You have 2 digital purchases.",
    )
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    result = chat_service.create_response(
        message="How many digital products have i purchsed?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert result.content == "You have 2 digital purchases."
    assert application_service.purchase_requests == [CUSTOMER_ID]
    assert result.conversation_state["selected_purchase_type"] == "digital"
    assert result.conversation_state["selected_purchase_ids"] == [
        PURCHASE_ID,
        "40000000-0000-4000-8000-000000000002",
    ]
    tool_message = next(
        message
        for message in model_client.calls[1]["messages"]
        if message["content"].startswith("Read-only account tool result:")
    )
    assert "get_customer_purchase_history" in tool_message["content"]
    assert "validate_customer_account" not in tool_message["content"]

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
    assert caplog.records[0].event["type"] == "model.failure"
    assert caplog.records[0].event["data"] == {
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
        "workflow.classified",
        "workflow.context_resolved",
        "workflow.executing",
        "tool_call.skipped",
        "workflow.state_updated",
        "model.requested",
        "response.generated",
    ]
    assert caplog.records[6].event["data"] == {"reason": "off_domain_intent"}

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

def test_openapi_documents_chat_endpoint() -> None:
    client = build_client(StaticChatService())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/chat" in response.json()["paths"]
