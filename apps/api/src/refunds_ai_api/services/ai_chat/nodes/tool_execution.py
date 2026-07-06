"""Tool-execution graph node for AI chat."""

from __future__ import annotations

from typing import Any

from refunds_ai_api.services.ai_chat.execution_blocking import (
    block_workflow_or_reference_response,
)
from refunds_ai_api.services.ai_chat.execution_context import resolve_execution_context
from refunds_ai_api.services.ai_chat.execution_state import finalize_execution_state
from refunds_ai_api.services.ai_chat.forced_tool_fallback import (
    apply_deterministic_forced_tool_fallback,
)
from refunds_ai_api.services.ai_chat.model_tool_execution import (
    execute_model_requested_tool_calls,
)
from refunds_ai_api.services.ai_chat.models import ChatGraphState


def execute_tools_node(runtime: Any, state: ChatGraphState) -> ChatGraphState:
    """Execute model-requested or deterministic backend tools."""
    context = resolve_execution_context(runtime, state)

    blocked_state = block_workflow_or_reference_response(runtime, state, context)
    if blocked_state is not None:
        return blocked_state

    state, tool_results = execute_model_requested_tool_calls(runtime, state, context)

    state, tool_results, account_fact_intent = apply_deterministic_forced_tool_fallback(
        runtime,
        state,
        context,
        tool_results,
    )

    return finalize_execution_state(
        state,
        context,
        tool_results,
        account_fact_intent,
    )
