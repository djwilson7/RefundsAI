from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from refunds_ai_api.services.ai_chat import execution_blocking, execution_context
from refunds_ai_api.services.ai_chat.execution_state import finalize_execution_state
from refunds_ai_api.services.ai_chat.workflows.context import EligibilityResolution

from .fakes import CUSTOMER_ID, PURCHASE_ID, FakeApplicationService, WorkflowRuntime


def test_resolve_execution_context_assembles_queries_and_references(monkeypatch) -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "customer_id": CUSTOMER_ID,
        "message": "show purchases over $100 and generate the return label",
        "conversation_state": {},
        "page_context": {"surface": "purchase_history"},
    }
    policy_query = {"scope": "product_type", "purchase_type": "digital"}
    resolved_purchase = {"id": PURCHASE_ID}
    page_reference = {"surface": "purchase_history"}

    monkeypatch.setattr(
        execution_context,
        "resolve_refund_policy_query_with_purchase",
        lambda *args, **kwargs: (policy_query, resolved_purchase, None),
    )
    monkeypatch.setattr(
        execution_context,
        "resolve_page_reference",
        lambda *args, **kwargs: page_reference,
    )

    context = execution_context.resolve_execution_context(runtime, state)

    assert context["customer_id"] == CUSTOMER_ID
    assert context["threshold_query"] == {"threshold_cents": 10000, "comparison": "gt"}
    assert context["policy_lookup_query"] == policy_query
    assert context["resolved_purchase"] == resolved_purchase
    assert context["unresolved_product_reference"] is None
    assert context["page_reference"] == page_reference
    assert context["workflow_continuation_intent"] == "workflow_continuation"


def test_finalize_execution_state_sets_intents_and_conversation_state(monkeypatch) -> None:
    state = {
        "message": "can this be refunded?",
        "conversation_state": {"selected_purchase_id": PURCHASE_ID},
    }
    tool_results = [{"name": "get_refund_eligibility", "result": {"purchase_count": 1}}]
    eligibility_resolution = EligibilityResolution(
        purchase_ids=[PURCHASE_ID],
        context="product",
    )
    context = {
        "policy_lookup_query": {"scope": "product_type"},
        "eligibility_resolution": eligibility_resolution,
        "resolved_context_purchase": {"id": PURCHASE_ID},
        "resolved_purchase": None,
        "page_reference": {"surface": "purchase_history"},
    }
    calls: list[dict[str, Any]] = []

    def fake_update_conversation_state(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return {"selected_refund_purchase_ids": [PURCHASE_ID]}

    monkeypatch.setattr(
        "refunds_ai_api.services.ai_chat.execution_state.update_conversation_state",
        fake_update_conversation_state,
    )

    result = finalize_execution_state(
        state,
        context,
        tool_results,
        account_fact_intent=True,
    )

    assert result["tool_results"] == tool_results
    assert result["account_fact_intent"] is True
    assert result["policy_lookup_intent"] is True
    assert result["eligibility_lookup_intent"] is True
    assert result["resolved_context_purchase"] == {"id": PURCHASE_ID}
    assert result["conversation_state"] == {"selected_refund_purchase_ids": [PURCHASE_ID]}
    assert result["page_reference"] == {"surface": "purchase_history"}
    assert calls[0]["kwargs"]["resolved_purchase"] == {"id": PURCHASE_ID}


def test_blocking_continuation_uses_active_refund_context(monkeypatch) -> None:
    monkeypatch.setattr(execution_blocking, "build_model_context_summary", lambda *_, **__: {})
    monkeypatch.setattr(execution_blocking, "log_trace_step", lambda state, **kwargs: state)
    state = {
        "message": "continue",
        "conversation_state": {
            "active_refund_context": {
                "purchase_id": PURCHASE_ID,
                "product_name": "Design Template Pack",
                "purchase_type": "physical",
                "eligible": True,
                "stage": "eligibility_confirmed",
                "next_action": "generate_return_label",
                "reason_codes": [],
            }
        },
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "page_reference": {"surface": "purchase_history"},
        "unresolved_product_reference": None,
        "workflow_continuation_intent": "workflow_continuation",
    }

    result = execution_blocking.block_workflow_or_reference_response(
        SimpleNamespace(application_service=FakeApplicationService()),
        state,
        context,
    )

    assert result is not None
    assert result["tool_results"] == []
    assert result["blocked_intent"] == "workflow_continuation"
    assert "cannot start the return process yet" in result["assistant_response"]
    assert result["page_reference"] == {"surface": "purchase_history"}


def test_blocking_continuation_without_active_context_requests_confirmation(
    monkeypatch,
) -> None:
    monkeypatch.setattr(execution_blocking, "build_model_context_summary", lambda *_, **__: {})
    monkeypatch.setattr(execution_blocking, "log_trace_step", lambda state, **kwargs: state)
    state = {"message": "continue", "conversation_state": {}}
    context = {
        "customer_id": CUSTOMER_ID,
        "page_reference": None,
        "unresolved_product_reference": None,
        "workflow_continuation_intent": "workflow_continuation",
    }

    result = execution_blocking.block_workflow_or_reference_response(
        SimpleNamespace(application_service=FakeApplicationService()),
        state,
        context,
    )

    assert result is not None
    assert result["tool_results"] == []
    assert result["blocked_intent"] == "workflow_continuation"
    assert "confirm the product name" in result["assistant_response"].lower()


def test_blocking_refund_intent_stops_before_tool_execution(monkeypatch) -> None:
    monkeypatch.setattr(execution_blocking, "build_model_context_summary", lambda *_, **__: {})
    monkeypatch.setattr(execution_blocking, "log_trace_step", lambda state, **kwargs: state)
    monkeypatch.setattr(
        execution_blocking,
        "resolve_refund_eligibility_query",
        lambda *_, **__: None,
    )
    monkeypatch.setattr(execution_blocking, "resolve_purchase_fact_context", lambda *_, **__: None)
    state = {"message": "start a refund", "conversation_state": {}, "page_context": None}
    context = {
        "customer_id": CUSTOMER_ID,
        "page_reference": None,
        "unresolved_product_reference": None,
        "workflow_continuation_intent": None,
    }

    result = execution_blocking.block_workflow_or_reference_response(
        SimpleNamespace(application_service=FakeApplicationService()),
        state,
        context,
    )

    assert result is not None
    assert result["tool_results"] == []
    assert result["blocked_intent"] == "workflow"
    assert "cannot start or change" in result["assistant_response"].lower()
    assert context["blocked_refund_intent"] == "workflow"


def test_blocking_unresolved_reference_returns_clarification(monkeypatch) -> None:
    monkeypatch.setattr(execution_blocking, "build_model_context_summary", lambda *_, **__: {})
    monkeypatch.setattr(execution_blocking, "log_trace_step", lambda state, **kwargs: state)
    monkeypatch.setattr(
        execution_blocking,
        "parse_refund_workflow_mutation_intent",
        lambda message: None,
    )
    monkeypatch.setattr(
        execution_blocking,
        "resolve_refund_eligibility_query",
        lambda *_, **__: SimpleNamespace(unresolved_product_reference="unknown product"),
    )
    monkeypatch.setattr(execution_blocking, "resolve_purchase_fact_context", lambda *_, **__: None)
    state = {"message": "can I refund unknown product?", "conversation_state": {}}
    context = {
        "customer_id": CUSTOMER_ID,
        "page_reference": {"surface": "purchase_history"},
        "unresolved_product_reference": None,
        "workflow_continuation_intent": None,
    }

    result = execution_blocking.block_workflow_or_reference_response(
        SimpleNamespace(application_service=FakeApplicationService()),
        state,
        context,
    )

    assert result is not None
    assert result["tool_results"] == []
    assert result["blocked_intent"] == "product_reference_unresolved"
    assert "unknown product" in result["assistant_response"]
    assert result["page_reference"] == {"surface": "purchase_history"}
