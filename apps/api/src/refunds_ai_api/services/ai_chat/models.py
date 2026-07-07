"""Data models and model-client adapters for AI chat orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict

from .parsing import parse_tool_arguments
from .state import EMPTY_CONVERSATION_STATE


@dataclass(frozen=True)
class ModelToolCall:
    """Normalized model tool-call request."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    """Normalized model response."""

    content: str | None
    tool_calls: list[ModelToolCall]


@dataclass(frozen=True)
class EligibilityResolution:
    """Resolved purchase ids and context for a read-only eligibility lookup."""

    purchase_ids: list[str]
    context: str
    resolved_purchase: dict[str, Any] | None = None
    unresolved_product_reference: str | None = None


class ChatModelClient(Protocol):
    """Model-client boundary used by the LangGraph nodes."""

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        """Return a model turn for the given messages and tool schemas."""
        ...


@dataclass(frozen=True)
class OpenAIChatCompletionsModelClient:
    """OpenAI SDK adapter for chat completion tool calls."""

    api_key: str
    model: str

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        """Call OpenAI and normalize the response for the graph."""
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        request: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            request["tools"] = [{"type": "function", "function": tool} for tool in tools]
            request["tool_choice"] = "auto"

        response = client.chat.completions.create(**request)
        message = response.choices[0].message
        tool_calls = [
            ModelToolCall(
                id=tool_call.id,
                name=tool_call.function.name,
                arguments=parse_tool_arguments(tool_call.function.arguments),
            )
            for tool_call in message.tool_calls or []
        ]

        return ModelTurn(content=message.content, tool_calls=tool_calls)


@dataclass(frozen=True)
class AIChatResult:
    """Assistant response returned by the AI chat service."""

    content: str
    graph_ready: bool
    conversation_state: dict[str, Any] = field(
        default_factory=lambda: dict(EMPTY_CONVERSATION_STATE)
    )
    side_effects: list[dict[str, Any]] = field(default_factory=list)
    next_trace_step: int = field(default=1, compare=False)


class ChatGraphState(TypedDict, total=False):
    """State carried through the purchase/refund chat graph."""

    message: str
    customer_id: str | None
    purchase_id: str | None
    page_context: dict[str, Any]
    conversation_state: dict[str, Any]
    model: str
    tool_calls: list[ModelToolCall]
    tool_results: list[dict[str, Any]]
    account_fact_intent: bool
    policy_lookup_intent: bool
    eligibility_lookup_intent: bool
    blocked_intent: str
    page_reference: dict[str, Any]
    resolved_context_purchase: dict[str, Any]
    invalid_model_output: bool
    assistant_response: str
    side_effects: list[dict[str, Any]]
    error: str
    trace_step: int
