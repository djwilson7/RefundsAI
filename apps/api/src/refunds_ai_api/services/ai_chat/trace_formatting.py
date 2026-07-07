"""Compatibility facade for readable AI chat trace formatting."""

from __future__ import annotations

# ruff: noqa: F401
from .trace.blocks import format_debug_block, format_sequence_block
from .trace.dispatch import format_trace_detail_block
from .trace.helpers import (
    MAX_ACTIVE_RESULT_SET_PREVIEW_ITEMS,
    MAX_MESSAGE_PREVIEW_CHARS,
    MAX_RESPONSE_PREVIEW_CHARS,
    MAX_TRACE_ITEMS,
    preview_text,
)
from .trace.state_summaries import (
    summarize_active_purchase,
    summarize_active_result_set,
    summarize_active_workflow,
    summarize_conversation_state,
    summarize_pending_refund_action,
)
from .trace.summaries import (
    summarize_api_response,
    summarize_assistant_response,
    summarize_blocked_workflow,
    summarize_incoming_message,
    summarize_model_request,
    summarize_refund_mutation_lifecycle,
    summarize_state_update,
    summarize_tool_execution,
    summarize_tool_result,
    summarize_tool_result_event,
    summarize_tool_selection,
    summarize_workflow_classification,
    summarize_workflow_confirmation,
    summarize_workflow_confirmation_command,
    summarize_workflow_context,
    summarize_workflow_execution,
    summarize_workflow_mutation,
)
