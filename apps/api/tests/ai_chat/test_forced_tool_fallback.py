from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.forced_tool_fallback import (
    apply_deterministic_forced_tool_fallback,
)
from refunds_ai_api.services.ai_chat.workflows.context import EligibilityResolution

from .fakes import (
    CUSTOMER_ID,
    PURCHASE_ID,
    FakeApplicationService,
    WorkflowRuntime,
)


def test_apply_deterministic_forced_tool_fallback_eligibility() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "message": "can I refund this?",
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "threshold_query": None,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": EligibilityResolution(
            purchase_ids=[PURCHASE_ID],
            context="digital",
        ),
        "resolved_context_purchase": None,
    }
    tool_results: list[dict[str, Any]] = []

    new_state, results, intent = apply_deterministic_forced_tool_fallback(
        runtime, state, context, tool_results
    )
    assert len(results) == 1
    assert results[0]["name"] == "get_refund_eligibility"
    assert intent is True


def test_apply_deterministic_forced_tool_fallback_policy() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "message": "policy please",
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "threshold_query": None,
        "date_range_query": None,
        "policy_lookup_query": {
            "scope": "product_type",
            "purchase_type": "digital",
        },
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    tool_results: list[dict[str, Any]] = []

    new_state, results, intent = apply_deterministic_forced_tool_fallback(
        runtime, state, context, tool_results
    )
    assert len(results) == 1
    assert results[0]["name"] == "get_refund_policy"
    assert intent is False


def test_apply_deterministic_forced_tool_fallback_threshold() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "message": "purchases over $100",
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "threshold_query": {
            "threshold_cents": 10000,
            "comparison": "gt",
        },
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    tool_results: list[dict[str, Any]] = []

    new_state, results, intent = apply_deterministic_forced_tool_fallback(
        runtime, state, context, tool_results
    )
    assert len(results) == 1
    assert results[0]["name"] == "get_purchase_count_by_amount_threshold"
    assert intent is True


def test_apply_deterministic_forced_tool_fallback_date_range() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "message": "purchases between dates",
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "threshold_query": None,
        "date_range_query": {
            "start_date": "2026-06-20",
            "end_date": "2026-06-22",
            "timezone": "America/Chicago",
            "label": "June 20 through 22",
        },
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    tool_results: list[dict[str, Any]] = []

    new_state, results, intent = apply_deterministic_forced_tool_fallback(
        runtime, state, context, tool_results
    )
    assert len(results) == 1
    assert results[0]["name"] == "get_purchase_history_by_date_range"
    assert intent is True


def test_apply_deterministic_forced_tool_fallback_account_fact() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "message": "show my orders",
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "threshold_query": None,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    tool_results: list[dict[str, Any]] = []

    new_state, results, intent = apply_deterministic_forced_tool_fallback(
        runtime, state, context, tool_results
    )
    assert len(results) == 1
    assert results[0]["name"] == "get_customer_purchase_history"
    assert intent is True


def test_apply_deterministic_forced_tool_fallback_resolved_context_purchase() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "message": "hello",
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "threshold_query": None,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": {
            "id": PURCHASE_ID,
            "purchase_type": "digital",
        },
    }
    tool_results: list[dict[str, Any]] = []

    new_state, results, intent = apply_deterministic_forced_tool_fallback(
        runtime, state, context, tool_results
    )
    assert len(results) == 1
    assert results[0]["name"] == "get_customer_purchase_history"
    assert intent is True


def test_apply_deterministic_forced_tool_fallback_off_domain() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "message": "what is the weather today?",
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "threshold_query": None,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    tool_results: list[dict[str, Any]] = []

    new_state, results, intent = apply_deterministic_forced_tool_fallback(
        runtime, state, context, tool_results
    )
    assert len(results) == 0
    assert intent is False
