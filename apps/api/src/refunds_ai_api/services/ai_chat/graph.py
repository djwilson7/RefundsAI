"""LangGraph construction for the AI chat workflow."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .models import ChatGraphState
from .routing import should_continue


def build_chat_graph(service):
    """Build the chat graph around AIChatService node methods."""
    # The graph shape stays intentionally small; deterministic context resolution
    # happens inside execute_tools before any model-requested tool is honored.
    # Routing precedence:
    # 1. Page purchase references such as "this product" or "this order".
    # 2. Active refund workflow context for continuation commands.
    # 3. Explicit product, SKU, order number, or purchase id references.
    # 4. Selected single purchase for vague follow-ups like "it" or "that item".
    # 5. Scoped selected purchase set for ranking terms.
    # 6. Aggregate/list scope capture for future follow-ups.
    # 7. Explicit policy intent.
    # 8. Explicit eligibility intent.
    # 9. Supported mutation intent, currently blocked in Phase 3.
    # 10. Clarification when unresolved or ambiguous.
    graph_builder = StateGraph(ChatGraphState)
    graph_builder.add_node("validate_context", service._validate_context)
    graph_builder.add_node("request_tool_call", service._request_tool_call)
    graph_builder.add_node("execute_tools", service._execute_tools)
    graph_builder.add_node("generate_final_response", service._generate_final_response)

    graph_builder.set_entry_point("validate_context")
    graph_builder.add_conditional_edges(
        "validate_context",
        should_continue,
        {"continue": "request_tool_call", "stop": END},
    )
    graph_builder.add_conditional_edges(
        "request_tool_call",
        should_continue,
        {"continue": "execute_tools", "stop": END},
    )
    graph_builder.add_edge("execute_tools", "generate_final_response")
    graph_builder.add_edge("generate_final_response", END)

    return graph_builder.compile()
