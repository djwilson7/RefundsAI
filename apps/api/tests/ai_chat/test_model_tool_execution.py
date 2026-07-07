from __future__ import annotations

from typing import Any
import pytest

from refunds_ai_api.services.ai_chat import ModelToolCall
from refunds_ai_api.services.ai_chat.model_tool_execution import execute_model_requested_tool_calls
from refunds_ai_api.services.ai_chat.workflows.context import (
    EligibilityResolution,
)
from .fakes import (
    CUSTOMER_ID,
    PURCHASE_ID,
    FakeApplicationService,
    WorkflowRuntime,
)

def test_execute_validate_customer_account_with_arguments_ignored() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="validate_customer_account",
                arguments={"invalid": "args"},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 0

def test_execute_validate_customer_account_success() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="validate_customer_account",
                arguments={},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "validate_customer_account"
    assert results[0]["result"]["valid"] is True

def test_get_customer_purchase_history_override_eligibility() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_customer_purchase_history",
                arguments={},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": EligibilityResolution(
            purchase_ids=[PURCHASE_ID],
            context="digital",
        ),
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "get_refund_eligibility"

def test_get_customer_purchase_history_override_policy() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_customer_purchase_history",
                arguments={},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": {
            "scope": "product_type",
            "purchase_type": "digital",
        },
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "get_refund_policy"

def test_get_customer_purchase_history_override_date_range() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_customer_purchase_history",
                arguments={},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
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
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "get_purchase_history_by_date_range"

def test_get_customer_purchase_history_fallback() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_customer_purchase_history",
                arguments={},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "get_customer_purchase_history"

def test_get_purchase_count_by_amount_threshold_invalid_args() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_purchase_count_by_amount_threshold",
                arguments={"invalid": "args"},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 0

def test_get_purchase_count_by_amount_threshold_success() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_purchase_count_by_amount_threshold",
                arguments={"threshold_cents": 10000, "comparison": "gt"},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "get_purchase_count_by_amount_threshold"

def test_get_refund_policy_invalid_args() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_refund_policy",
                arguments={"invalid": "args"},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 0

def test_get_refund_policy_ignored_no_intent() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_refund_policy",
                arguments={"scope": "general"},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 0

def test_get_refund_policy_override_args() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_refund_policy",
                arguments={"scope": "general"},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": {
            "scope": "product_type",
            "purchase_type": "digital",
        },
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "get_refund_policy"
    assert results[0]["result"]["sections"][0]["key"] == "digital"

def test_get_refund_policy_success() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_refund_policy",
                arguments={"scope": "general"},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": {"scope": "general"},
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "get_refund_policy"

def test_get_refund_eligibility_invalid_args() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_refund_eligibility",
                arguments={"invalid": "args"},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 0

def test_get_refund_eligibility_ignored_account_fact() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_refund_eligibility",
                arguments={"purchase_ids": [PURCHASE_ID]},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": {
            "id": PURCHASE_ID,
            "purchase_type": "digital",
        },
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 0

def test_get_refund_eligibility_override_args() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_refund_eligibility",
                arguments={"purchase_ids": ["different-id"]},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": EligibilityResolution(
            purchase_ids=[PURCHASE_ID],
            context="digital",
        ),
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "get_refund_eligibility"
    assert results[0]["result"]["resolved_purchase_ids"] == [PURCHASE_ID]

def test_get_refund_eligibility_success_no_override() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_refund_eligibility",
                arguments={"purchase_ids": [PURCHASE_ID], "context": "digital"},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "get_refund_eligibility"
    assert results[0]["result"]["resolved_purchase_ids"] == [PURCHASE_ID]

def test_get_purchase_history_by_date_range_invalid_args() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_purchase_history_by_date_range",
                arguments={"invalid": "args"},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 0

def test_get_purchase_history_by_date_range_success() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="get_purchase_history_by_date_range",
                arguments={
                    "start_date": "2026-06-20",
                    "end_date": "2026-06-22",
                    "timezone": "America/Chicago",
                },
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 1
    assert results[0]["name"] == "get_purchase_history_by_date_range"
    assert results[0]["result"]["aggregates"]["total_purchase_count"] == 3

def test_unsupported_model_tool_ignored() -> None:
    runtime = WorkflowRuntime(FakeApplicationService())
    state = {
        "tool_calls": [
            ModelToolCall(
                id="call_1",
                name="some_unsupported_tool",
                arguments={},
            )
        ]
    }
    context = {
        "customer_id": CUSTOMER_ID,
        "date_range_query": None,
        "policy_lookup_query": None,
        "eligibility_resolution": None,
        "resolved_context_purchase": None,
    }
    
    new_state, results = execute_model_requested_tool_calls(runtime, state, context)
    assert len(results) == 0
