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
from refunds_ai_api.services.ai_chat.nodes.tool_selection import (
    select_tool_schemas_for_request,
)
from refunds_ai_api.services.audit import ModelAuditEventKey, ModelAuditSession, TokenUsage
from refunds_ai_api.services.model_audit import enrich_session_summary

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


class FailedStaticChatService(StaticChatService):
    def create_response(self, **kwargs) -> AIChatResult:  # type: ignore[no-untyped-def]
        result = super().create_response(**kwargs)
        return AIChatResult(
            content=result.content,
            graph_ready=result.graph_ready,
            conversation_state=result.conversation_state,
            next_trace_step=result.next_trace_step,
            token_usage=TokenUsage(total_tokens=17),
            audit_failed=True,
        )


class TokenReportingModelClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        if not tools and self.calls == 0:
            self.calls = 2
            return ModelTurn(
                content="You made 2 digital purchases.",
                tool_calls=[],
                token_usage=TokenUsage(
                    prompt_tokens=10,
                    completion_tokens=13,
                    total_tokens=23,
                ),
            )
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


def tool_schema_names(tools: list[dict[str, Any]]) -> list[str]:
    return [str(tool["name"]) for tool in tools]


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


def test_tool_selection_exposes_only_relevant_tool_schemas() -> None:
    base_state = {
        "customer_id": CUSTOMER_ID,
        "purchase_id": None,
        "page_context": {"surface": "purchase_history"},
        "conversation_state": {},
    }

    assert tool_schema_names(
        select_tool_schemas_for_request(
            {**base_state, "message": "How many digital purchases have I made?"}
        )
    ) == ["get_customer_purchase_history"]
    assert tool_schema_names(
        select_tool_schemas_for_request(
            {**base_state, "message": "What is the refund policy for subscriptions?"}
        )
    ) == ["get_refund_policy"]
    assert tool_schema_names(
        select_tool_schemas_for_request(
            {**base_state, "message": "Am I able to refund the Icon Set?"}
        )
    ) == ["get_refund_eligibility"]
    assert select_tool_schemas_for_request(
        {**base_state, "message": "When are the Dallas Cowboys playing?"}
    ) == []

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
    response_content = response.json()["data"]["message"]["content"]
    generated_event = next(
        event
        for event in audit_writer.events
        if event["event_key"] == ModelAuditEventKey.RESPONSE_GENERATED
    )
    returned_event = next(
        event
        for event in audit_writer.events
        if event["event_key"] == ModelAuditEventKey.RESPONSE_RETURNED
    )
    assert generated_event["output_json"]["assistant_response"] == response_content
    assert returned_event["output_json"]["response"]["message"]["content"] == (
        response_content
    )
    assert [event["sequence_number"] for event in audit_writer.events] == list(
        range(1, len(audit_writer.events) + 1)
    )
    assert audit_writer.completed[0]["status"] == "succeeded"
    assert audit_writer.completed[0]["token_usage"] == TokenUsage(
        prompt_tokens=10,
        completion_tokens=13,
        total_tokens=23,
    )
    tool_started = next(
        event
        for event in audit_writer.events
        if event["event_key"] == ModelAuditEventKey.TOOL_STARTED
    )
    tool_completed = next(
        event
        for event in audit_writer.events
        if event["event_key"] == ModelAuditEventKey.TOOL_COMPLETED
    )
    started_lifecycle = tool_started["metadata_json"]["lifecycle"]
    completed_lifecycle = tool_completed["metadata_json"]["lifecycle"]
    assert started_lifecycle["tool_call_id"] == completed_lifecycle["tool_call_id"]
    assert started_lifecycle["tool_name"] == "get_customer_purchase_history"
    assert started_lifecycle["status"] == "started"
    assert completed_lifecycle["status"] == "completed"
    assert completed_lifecycle["source"] == "deterministic_forced"
    assert completed_lifecycle["workflow"] == "account_fact"
    assert completed_lifecycle["operation"] == "list"
    assert completed_lifecycle["input_summary"] == "customer purchase history"
    assert completed_lifecycle["output_summary"] == "4 purchases, $209.99"
    assert completed_lifecycle["backend_category"] == "backend_read"
    assert isinstance(completed_lifecycle["input_tokens_estimated"], int)
    assert isinstance(completed_lifecycle["output_tokens_estimated"], int)
    assert completed_lifecycle["output_tokens_estimated"] > 0
    assert completed_lifecycle["tokenizer"].startswith("tiktoken:")

    model_completed = next(
        event
        for event in audit_writer.events
        if event["event_key"] == ModelAuditEventKey.MODEL_COMPLETED
    )
    model_lifecycle = model_completed["metadata_json"]["lifecycle"]
    assert isinstance(model_lifecycle["input_tokens_estimated"], int)
    assert isinstance(model_lifecycle["output_tokens_estimated"], int)
    assert model_lifecycle["input_tokens_estimated"] > 0
    assert model_lifecycle["output_tokens_estimated"] > 0
    assert "token_budget" in model_lifecycle

    summary = enrich_session_summary(
        {"latency_ms": 100},
        [
            {
                "id": str(index),
                "event_key": event["event_key"],
                "metadata_json": event["metadata_json"],
            }
            for index, event in enumerate(audit_writer.events)
        ],
    )
    assert summary["total_model_calls"] == 1
    assert summary["total_tool_calls"] == 1
    assert summary["total_prompt_tokens"] == 10
    assert summary["total_completion_tokens"] == 13
    assert summary["total_reasoning_tokens"] == 0
    assert summary["total_tokens"] == 23
    assert summary["total_model_input_tokens_estimated"] > 0
    assert summary["total_model_output_tokens_estimated"] > 0
    assert summary["total_tool_input_tokens_estimated"] == 0
    assert summary["total_tool_output_tokens_estimated"] > 0


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


def test_chat_endpoint_marks_failed_audit_session_terminal() -> None:
    chat_service = FailedStaticChatService()
    chat_service.audit_writer = FakeAuditWriter()
    client = build_client(chat_service)

    response = client.post(
        "/api/chat",
        json={
            "message": "Issue my refund",
            "customer_id": CUSTOMER_ID,
            "purchase_id": PURCHASE_ID,
        },
    )

    assert response.status_code == 200
    assert len(chat_service.audit_writer.completed) == 1
    assert chat_service.audit_writer.completed[0]["status"] == "failed"
    assert chat_service.audit_writer.completed[0]["token_usage"] == TokenUsage(
        total_tokens=17
    )


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

def test_chat_graph_routes_transposed_purchase_typo_to_purchase_history() -> None:
    application_service = FakeApplicationService()
    model_client = ToolCallingModelClient(
        ModelToolCall(
            id="tool-call-validate-customer",
            name="validate_customer_account",
            arguments={},
        ),
        (
            "You have made 4 purchases in total. Of those, 0 have been "
            "refunded and 4 have not been refunded."
        ),
    )
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=model_client,
    )

    result = chat_service.create_response(
        message="How many purhcases have i made?",
        customer_id=CUSTOMER_ID,
        purchase_id=None,
    )

    assert result.content == (
        "You have made 4 purchases in total. Of those, 0 have been "
        "refunded and 4 have not been refunded."
    )
    assert application_service.purchase_requests == [CUSTOMER_ID]
    assert result.conversation_state["active_workflow"]["kind"] == "account_fact"
    tool_message = next(
        message
        for message in model_client.calls[1]["messages"]
        if message["content"].startswith("Read-only account tool result:")
    )
    assert "get_customer_purchase_history" in tool_message["content"]
    assert "history_summary" in tool_message["content"]
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

    assert result.content == CHAT_UNAVAILABLE_RESPONSE
    assert result.graph_ready is True
    assert caplog.records[0].event["type"] == "model.failure"
    failure_data = caplog.records[0].event["data"]
    assert failure_data["reason"] == "RuntimeError"
    assert failure_data["detail"] == "model offline"
    assert failure_data["model"] == "gpt-5.4-mini"
    assert failure_data["status"] == "failed"
    assert failure_data["phase"] == "final_response"
    assert failure_data["model_call_id"]
    assert failure_data["latency_ms"] >= 0

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
        "workflow.classified",
        "workflow.context_resolved",
        "workflow.executing",
        "tool_call.skipped",
        "workflow.state_updated",
        "model.requested",
        "model.completed",
        "response.generated",
    ]
    assert caplog.records[4].event["data"] == {"reason": "off_domain_intent"}

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


def test_chat_audit_token_usage_preserved_on_deterministic_refund_confirmation() -> None:
    """Regression: audit_token_usage must be correctly propagated when the
    refund confirmation path bypasses request_tool_call_node entirely.

    When a customer sends the exact canonical confirmation command, the graph
    routes validate_context -> execute_tools -> generate_final_response,
    skipping the model call in request_tool_call_node. The final-response node
    takes the _return_deterministic_response branch because assistant_response
    is pre-set by execute_tools. This test confirms that audit_token_usage
    (None for this no-model path) is explicitly returned from the graph state
    and handed to complete_session, rather than being silently dropped.
    """
    from .fakes import MutableRefundApplicationService, NoToolModelClient

    DIGITAL_CONFIRMATION_COMMAND = "Confirm invalidate code and issue refund"

    application_service = MutableRefundApplicationService()
    # Seed a persisted confirmation so the mutation is authorized
    application_service.refund_confirmations[PURCHASE_ID] = {
        "refund_confirmation_granted": True,
        "refund_confirmation_message": f"{DIGITAL_CONFIRMATION_COMMAND}.",
        "refund_confirmation_granted_at": None,
        "refund_confirmation_expected_command": DIGITAL_CONFIRMATION_COMMAND,
        "refund_confirmation_matched": True,
        "refund_confirmation_source": "chat_confirmation_validator",
        "refund_confirmation_customer_id": CUSTOMER_ID,
        "refund_confirmation_purchase_id": PURCHASE_ID,
        "refund_confirmation_consumed_at": None,
        "refund_confirmation_consumed_by_action": None,
    }

    pending_action = {
        "action": "request_refund",
        "purchase_id": PURCHASE_ID,
        "product_name": "Design Template Pack",
        "purchase_type": "digital",
        "confirmation_expected_command": DIGITAL_CONFIRMATION_COMMAND,
    }

    audit_writer = FakeAuditWriter()
    chat_service = AIChatService(
        application_service=application_service,
        model="gpt-5.4-mini",
        model_client=NoToolModelClient("Unused model response."),
        audit_writer=audit_writer,  # type: ignore[arg-type]
    )
    client = build_client(chat_service)

    response = client.post(
        "/api/chat",
        json={
            "message": DIGITAL_CONFIRMATION_COMMAND,
            "customer_id": CUSTOMER_ID,
            "purchase_id": PURCHASE_ID,
            "conversation_state": {
                "pending_refund_action": pending_action,
            },
        },
    )

    assert response.status_code == 200
    # The graph took the deterministic confirmation path — no model call was made.
    # complete_session must be called exactly once with token_usage=None (not dropped).
    assert len(audit_writer.completed) == 1
    completed = audit_writer.completed[0]
    assert completed["status"] == "succeeded"
    # For a purely deterministic refund turn, no model tokens were consumed.
    # token_usage should be None (not a stale value or an exception).
    assert completed["token_usage"] is None
