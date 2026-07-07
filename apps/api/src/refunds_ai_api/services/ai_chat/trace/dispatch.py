"""Trace event to console-block dispatch."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .blocks import format_debug_block
from .summaries import (
    summarize_api_response,
    summarize_assistant_response,
    summarize_blocked_workflow,
    summarize_incoming_message,
    summarize_model_request,
    summarize_refund_mutation_lifecycle,
    summarize_state_update,
    summarize_tool_execution,
    summarize_tool_result_event,
    summarize_tool_selection,
    summarize_workflow_classification,
    summarize_workflow_confirmation,
    summarize_workflow_confirmation_command,
    summarize_workflow_context,
    summarize_workflow_execution,
    summarize_workflow_mutation,
)


def format_trace_detail_block(event_type: str, data: Mapping[str, Any]) -> str | None:
    """Return the structured console detail block for a trace event."""
    if event_type == "message.received":
        return format_debug_block("Incoming Message", summarize_incoming_message(data))
    if event_type == "model.requested":
        return format_debug_block("Model Request", summarize_model_request(data))
    if event_type == "tool_call.requested":
        return format_debug_block("Model Tool Selection", summarize_tool_selection(data))
    if event_type == "workflow.classified":
        return format_debug_block(
            "Workflow Classification",
            summarize_workflow_classification(data),
        )
    if event_type == "workflow.confirmation_requested":
        return format_debug_block(
            "Workflow Confirmation",
            summarize_workflow_confirmation(data),
        )
    if event_type in {
        "workflow.confirmation_command_generated",
        "workflow.confirmation_command_received",
        "workflow.confirmation_command_invalid",
        "workflow.confirmation_command_verified",
        "workflow.confirmation_context_incomplete",
        "workflow.confirmation_pending_action_missing",
        "workflow.confirmation_target_resolution_failed",
        "workflow.confirmation_validation_failed",
        "workflow.confirmation_validated",
    }:
        return format_debug_block(
            "Workflow Confirmation Command",
            summarize_workflow_confirmation_command(data),
        )
    if event_type == "workflow.context_resolved":
        return format_debug_block("Workflow Context", summarize_workflow_context(data))
    if event_type in {
        "workflow.mutation_executing",
        "workflow.mutation_completed",
        "workflow.mutation_conflict",
        "workflow.refund_mutation_started",
        "workflow.refund_mutation_completed",
    }:
        return format_debug_block(
            "Workflow Mutation",
            summarize_workflow_mutation(data),
        )
    if event_type == "workflow.refund_mutation_lifecycle":
        return format_debug_block(
            "Refund Mutation Lifecycle",
            summarize_refund_mutation_lifecycle(data),
        )
    if event_type == "workflow.executing":
        return format_debug_block("Workflow Execution", summarize_workflow_execution(data))
    if event_type == "tool_call.executing":
        return format_debug_block("Tool Execution", summarize_tool_execution(data))
    if event_type == "tool_call.completed":
        return format_debug_block("Tool Result", summarize_tool_result_event(data))
    if event_type == "workflow.state_updated":
        return format_debug_block("Workflow State Update", summarize_state_update(data))
    if event_type == "response.generated":
        return format_debug_block("Assistant Response", summarize_assistant_response(data))
    if event_type == "route.response_returned":
        return format_debug_block("API Response", summarize_api_response(data))
    if event_type in {"response.blocked", "workflow.blocked"}:
        return format_debug_block("Workflow Blocked", summarize_blocked_workflow(data))
    return None
