"""LangGraph-backed AI chat orchestration for read-only purchase intelligence."""

from __future__ import annotations

import inspect
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, TypedDict
from zoneinfo import ZoneInfo

from langgraph.graph import END, StateGraph
from openai import OpenAI

from refunds_ai_api.services.application import ApplicationService
from refunds_ai_api.services.dates import (
    DEFAULT_CUSTOMER_TIMEZONE,
    InclusiveDateRange,
    build_inclusive_date_range,
    format_date,
    get_timezone,
    is_datetime_in_inclusive_date_range,
    parse_iso_date,
)
from refunds_ai_api.services.money import (
    cents_to_dollar_string,
    dollars_to_cents,
    format_cents,
)

logger = logging.getLogger("refunds_ai_api.chat")
console_logger = logging.getLogger("uvicorn.error")

CHAT_UNAVAILABLE_RESPONSE = (
    "AI chat is temporarily unavailable. Please try again in a moment."
)
ACCOUNT_DATA_REQUIRED_RESPONSE = (
    "I need account data before I can answer that. Please ask about your purchases, "
    "orders, account activity, or refund flow."
)
CUSTOMER_CONTEXT_REQUIRED_RESPONSE = (
    "I need an active customer session before I can inspect purchase history. "
    "Please load a mock customer, then ask again."
)
SYSTEM_PROMPT = (
    "You are RefundsAI's customer support assistant. For purchase-history "
    "questions, call the relevant read-only purchase tool before answering. Use "
    "only tool-provided purchase data for counts, totals, purchase types, "
    "statuses, and dates. Do not assess refund eligibility, explain refund policy, or "
    "initiate refund workflow actions. Keep the conversation grounded in the "
    "customer's account, account history, purchases, orders, account activity, "
    "and refund flows. If the customer asks about unrelated topics, briefly and "
    "gracefully redirect them to account, purchase, order, activity, or refund "
    "topics you can help with. Return plain standard text only. Do not use "
    "Markdown, bullets, numbered lists, headings, tables, code blocks, links, or "
    "other markup."
)


class ChatGraphState(TypedDict, total=False):
    """State carried through the phase-one purchase-history graph."""

    message: str
    customer_id: str | None
    purchase_id: str | None
    model: str
    tool_calls: list[ModelToolCall]
    tool_results: list[dict[str, Any]]
    account_fact_intent: bool
    invalid_model_output: bool
    assistant_response: str
    error: str
    trace_step: int


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
    next_trace_step: int = field(default=1, compare=False)


@dataclass(frozen=True)
class AIChatService:
    """Run read-only purchase-history chat through a LangGraph workflow."""

    application_service: ApplicationService
    model: str
    model_client: ChatModelClient | None

    def create_response(
        self,
        *,
        message: str,
        customer_id: str | None,
        purchase_id: str | None,
        trace_step_start: int = 1,
    ) -> AIChatResult:
        """Invoke the purchase-history graph and return the assistant response."""
        graph = self._build_graph()
        try:
            state = graph.invoke(
                {
                    "message": message,
                    "customer_id": customer_id,
                    "purchase_id": purchase_id,
                    "model": self.model,
                    "trace_step": trace_step_start,
                }
            )
        except Exception as exc:
            logger.warning(
                "ai.chat.graph_failed: %s",
                exc,
                extra={
                    "event": {
                        "type": "model.failure",
                        "reason": exc.__class__.__name__,
                        "detail": str(exc),
                        "model": self.model,
                    }
                },
            )
            return AIChatResult(
                content=CHAT_UNAVAILABLE_RESPONSE,
                graph_ready=self.model_client is not None,
                next_trace_step=trace_step_start,
            )

        return AIChatResult(
            content=state.get("assistant_response") or CHAT_UNAVAILABLE_RESPONSE,
            graph_ready=self.model_client is not None,
            next_trace_step=int(state.get("trace_step", trace_step_start)),
        )

    def _build_graph(self):
        graph_builder = StateGraph(ChatGraphState)
        graph_builder.add_node("validate_context", self._validate_context)
        graph_builder.add_node("request_tool_call", self._request_tool_call)
        graph_builder.add_node("execute_tools", self._execute_tools)
        graph_builder.add_node("generate_final_response", self._generate_final_response)

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

    def _validate_context(self, state: ChatGraphState) -> ChatGraphState:
        state = log_trace_step(
            state,
            message="LangGraph chat workflow started.",
            event_type="graph.started",
            data={
                "customer_id": state.get("customer_id"),
                "purchase_id": state.get("purchase_id"),
                "model": self.model,
            },
        )

        if not state.get("customer_id"):
            state = log_trace_step(
                state,
                message="Stopped before model call because no customer context was supplied.",
                event_type="graph.stopped",
                data={"reason": "customer_context_required"},
            )
            return {
                **state,
                "assistant_response": CUSTOMER_CONTEXT_REQUIRED_RESPONSE,
                "error": "customer_context_required",
            }

        if self.model_client is None:
            state = log_trace_step(
                state,
                message="Stopped before model call because OPENAI_API_KEY is not configured.",
                event_type="model.failure",
                level=logging.WARNING,
                data={"reason": "missing_openai_api_key", "model": self.model},
            )
            return {
                **state,
                "assistant_response": CHAT_UNAVAILABLE_RESPONSE,
                "error": "missing_openai_api_key",
            }

        return state

    def _request_tool_call(self, state: ChatGraphState) -> ChatGraphState:
        account_fact_intent = has_account_fact_intent(state["message"])
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state["message"]},
        ]
        tools = [
            get_customer_purchase_history_tool_schema(),
            get_purchase_count_by_amount_threshold_tool_schema(),
            get_purchase_history_by_date_range_tool_schema(),
        ]
        state = log_trace_step(
            {**state, "account_fact_intent": account_fact_intent},
            message="Sending tool-selection package to the model.",
            event_type="model.requested",
            data={
                "phase": "tool_selection",
                "model": self.model,
                "messages": messages,
                "tools": tools,
            },
        )

        try:
            turn = self.model_client.generate(messages=messages, tools=tools)
        except Exception as exc:
            logger.warning(
                "ai.chat.model_failed: %s",
                exc,
                extra={
                    "event": {
                        "type": "model.failure",
                        "reason": exc.__class__.__name__,
                        "detail": str(exc),
                        "model": self.model,
                    }
                },
            )
            return {
                **state,
                "assistant_response": CHAT_UNAVAILABLE_RESPONSE,
                "error": "model_request_failed",
            }

        state = log_trace_step(
            state,
            message="Model returned tool-call selection.",
            event_type="tool_call.requested",
            data={
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    }
                    for tool_call in turn.tool_calls
                ],
                "model_content": turn.content,
            },
        )
        invalid_model_output = has_invalid_pseudo_tool_output(turn.content)
        if invalid_model_output:
            state = log_trace_step(
                state,
                message="Model returned malformed pseudo-tool text instead of a tool call.",
                event_type="model.invalid_tool_output",
                data={"model_content": turn.content},
            )

        return {
            **state,
            "tool_calls": turn.tool_calls,
            "account_fact_intent": account_fact_intent,
            "invalid_model_output": invalid_model_output,
        }

    def _execute_tools(self, state: ChatGraphState) -> ChatGraphState:
        tool_results: list[dict[str, Any]] = []
        customer_id = state["customer_id"]
        threshold_query = parse_amount_threshold_query(state["message"])
        date_range_query = parse_date_range_query(state["message"])

        for tool_call in state.get("tool_calls", []):
            if tool_call.name == "get_customer_purchase_history":
                if date_range_query is not None:
                    state = log_trace_step(
                        state,
                        message=(
                            "Overriding broad purchase-history tool selection with "
                            "the narrower deterministic purchase-date-range tool."
                        ),
                        event_type="tool_call.overridden",
                        data={
                            "requested_tool_name": tool_call.name,
                            "tool_name": "get_purchase_history_by_date_range",
                            "reason": "date_range_intent",
                            "start_date": date_range_query["start_date"],
                            "end_date": date_range_query["end_date"],
                            "timezone": date_range_query["timezone"],
                        },
                    )
                    result = get_purchase_history_by_date_range(
                        self.application_service,
                        customer_id,
                        start_date=date_range_query["start_date"],
                        end_date=date_range_query["end_date"],
                        timezone_name=date_range_query["timezone"],
                        label=date_range_query.get("label"),
                    )
                    tool_results.append(
                        {
                            "tool_call_id": tool_call.id,
                            "name": "get_purchase_history_by_date_range",
                            "result": result,
                        }
                    )
                    state = log_trace_step(
                        state,
                        message="Backend purchase-date-range tool completed.",
                        event_type="tool_call.completed",
                        data={
                            "tool_name": "get_purchase_history_by_date_range",
                            "customer_id": customer_id,
                            "result": result,
                        },
                    )
                    continue

                state = log_trace_step(
                    state,
                    message="Executing backend purchase-history tool.",
                    event_type="tool_call.executing",
                    data={
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_call.name,
                        "model_arguments": tool_call.arguments,
                        "effective_customer_id": customer_id,
                    },
                )
                result = get_customer_purchase_history(self.application_service, customer_id)
                tool_results.append(
                    {
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "result": result,
                    }
                )

                state = log_trace_step(
                    state,
                    message="Backend purchase-history tool completed.",
                    event_type="tool_call.completed",
                    data={
                        "tool_name": tool_call.name,
                        "customer_id": customer_id,
                        "purchase_count": result["aggregates"]["total_purchase_count"],
                        "result": result,
                    },
                )
                continue

            if tool_call.name == "get_purchase_count_by_amount_threshold":
                threshold_query = parse_model_threshold_arguments(tool_call.arguments)
                if threshold_query is None:
                    state = log_trace_step(
                        state,
                        message="Ignoring invalid purchase-threshold tool arguments.",
                        event_type="tool_call.ignored",
                        data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                    )
                    continue

                state = log_trace_step(
                    state,
                    message="Executing backend purchase-threshold count tool.",
                    event_type="tool_call.executing",
                    data={
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_call.name,
                        "model_arguments": tool_call.arguments,
                        "effective_customer_id": customer_id,
                    },
                )
                result = get_purchase_count_by_amount_threshold(
                    self.application_service,
                    customer_id,
                    threshold_cents=threshold_query["threshold_cents"],
                    comparison=threshold_query["comparison"],
                )
                tool_results.append(
                    {
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "result": result,
                    }
                )
                state = log_trace_step(
                    state,
                    message="Backend purchase-threshold count tool completed.",
                    event_type="tool_call.completed",
                    data={
                        "tool_name": tool_call.name,
                        "customer_id": customer_id,
                        "result": result,
                    },
                )
                continue

            if tool_call.name == "get_purchase_history_by_date_range":
                date_range_query = parse_model_date_range_arguments(tool_call.arguments)
                if date_range_query is None:
                    state = log_trace_step(
                        state,
                        message="Ignoring invalid purchase-date-range tool arguments.",
                        event_type="tool_call.ignored",
                        data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                    )
                    continue

                state = log_trace_step(
                    state,
                    message="Executing backend purchase-date-range tool.",
                    event_type="tool_call.executing",
                    data={
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_call.name,
                        "model_arguments": tool_call.arguments,
                        "effective_customer_id": customer_id,
                    },
                )
                result = get_purchase_history_by_date_range(
                    self.application_service,
                    customer_id,
                    start_date=date_range_query["start_date"],
                    end_date=date_range_query["end_date"],
                    timezone_name=date_range_query["timezone"],
                    label=date_range_query.get("label"),
                )
                tool_results.append(
                    {
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "result": result,
                    }
                )
                state = log_trace_step(
                    state,
                    message="Backend purchase-date-range tool completed.",
                    event_type="tool_call.completed",
                    data={
                        "tool_name": tool_call.name,
                        "customer_id": customer_id,
                        "result": result,
                    },
                )
                continue

            state = log_trace_step(
                state,
                message="Ignoring unsupported model-requested tool.",
                event_type="tool_call.ignored",
                data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
            )

        account_fact_intent = bool(state.get("account_fact_intent")) or has_account_fact_intent(
            state["message"]
        )
        if not tool_results and threshold_query is not None:
            state = log_trace_step(
                state,
                message=(
                    "No supported tool was requested for a threshold purchase query; "
                    "forcing the deterministic purchase-threshold count tool."
                ),
                event_type="tool_call.forced",
                data={
                    "tool_name": "get_purchase_count_by_amount_threshold",
                    "reason": "amount_threshold_intent",
                    "threshold_cents": threshold_query["threshold_cents"],
                    "comparison": threshold_query["comparison"],
                },
            )
            result = get_purchase_count_by_amount_threshold(
                self.application_service,
                customer_id,
                threshold_cents=threshold_query["threshold_cents"],
                comparison=threshold_query["comparison"],
            )
            tool_results.append(
                {
                    "tool_call_id": "forced-get-purchase-count-by-amount-threshold",
                    "name": "get_purchase_count_by_amount_threshold",
                    "result": result,
                }
            )
            state = log_trace_step(
                state,
                message="Forced backend purchase-threshold count tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": "get_purchase_count_by_amount_threshold",
                    "customer_id": customer_id,
                    "result": result,
                },
            )
        elif not tool_results and date_range_query is not None:
            state = log_trace_step(
                state,
                message=(
                    "No supported tool was requested for a date-range purchase query; "
                    "forcing the deterministic purchase-date-range tool."
                ),
                event_type="tool_call.forced",
                data={
                    "tool_name": "get_purchase_history_by_date_range",
                    "reason": "date_range_intent",
                    "start_date": date_range_query["start_date"],
                    "end_date": date_range_query["end_date"],
                    "timezone": date_range_query["timezone"],
                },
            )
            result = get_purchase_history_by_date_range(
                self.application_service,
                customer_id,
                start_date=date_range_query["start_date"],
                end_date=date_range_query["end_date"],
                timezone_name=date_range_query["timezone"],
                label=date_range_query.get("label"),
            )
            tool_results.append(
                {
                    "tool_call_id": "forced-get-purchase-history-by-date-range",
                    "name": "get_purchase_history_by_date_range",
                    "result": result,
                }
            )
            state = log_trace_step(
                state,
                message="Forced backend purchase-date-range tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": "get_purchase_history_by_date_range",
                    "customer_id": customer_id,
                    "result": result,
                },
            )
        elif not tool_results and account_fact_intent:
            state = log_trace_step(
                state,
                message=(
                    "No supported tool was requested for an account-domain message; "
                    "forcing the read-only purchase-history tool."
                ),
                event_type="tool_call.forced",
                data={
                    "tool_name": "get_customer_purchase_history",
                    "reason": "account_domain_intent",
                },
            )
            result = get_customer_purchase_history(self.application_service, customer_id)
            tool_results.append(
                {
                    "tool_call_id": "forced-get-customer-purchase-history",
                    "name": "get_customer_purchase_history",
                    "result": result,
                }
            )
            state = log_trace_step(
                state,
                message="Forced backend purchase-history tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": "get_customer_purchase_history",
                    "customer_id": customer_id,
                    "purchase_count": result["aggregates"]["total_purchase_count"],
                    "result": result,
                },
            )
        elif not tool_results:
            state = log_trace_step(
                state,
                message="No supported account tool was requested for an off-domain message.",
                event_type="tool_call.skipped",
                data={"reason": "off_domain_intent"},
            )

        return {**state, "tool_results": tool_results, "account_fact_intent": account_fact_intent}

    def _generate_final_response(self, state: ChatGraphState) -> ChatGraphState:
        tool_results = state.get("tool_results", [])
        if state.get("account_fact_intent") and not tool_results:
            state = log_trace_step(
                state,
                message=(
                    "Blocked factual account response because no authoritative "
                    "tool result exists."
                ),
                event_type="response.blocked",
                data={"reason": "account_fact_without_tool_result"},
                level=logging.WARNING,
            )
            return {**state, "assistant_response": ACCOUNT_DATA_REQUIRED_RESPONSE}

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state["message"]},
        ]
        if tool_results:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Read-only account tool result: "
                        f"{json.dumps(tool_results, default=str)}"
                    ),
                }
            )

        messages.append(
            {
                "role": "user",
                "content": (
                    "Answer the customer's request if it is about their account, "
                    "account history, purchases, orders, account activity, or "
                    "refund flows. Use the tool result when relevant. If the "
                    "request is unrelated, briefly redirect the customer back to "
                    "supported account topics. Return plain standard text only, "
                    "with no Markdown formatting."
                ),
            },
        )
        tools: list[dict[str, Any]] = []
        state = log_trace_step(
            state,
            message="Sending final-response package to the model.",
            event_type="model.requested",
            data={
                "phase": "final_response",
                "model": self.model,
                "messages": messages,
                "tools": tools,
            },
        )

        try:
            turn = self.model_client.generate(messages=messages, tools=tools)
        except Exception as exc:
            logger.warning(
                "ai.chat.model_failed: %s",
                exc,
                extra={
                    "event": {
                        "type": "model.failure",
                        "reason": exc.__class__.__name__,
                        "detail": str(exc),
                        "model": self.model,
                    }
                },
            )
            return {
                **state,
                "assistant_response": CHAT_UNAVAILABLE_RESPONSE,
                "error": "final_model_request_failed",
            }

        assistant_response = turn.content or CHAT_UNAVAILABLE_RESPONSE
        state = log_trace_step(
            state,
            message="Model generated final assistant response.",
            event_type="response.generated",
            data={
                "model": self.model,
                "graph_ready": True,
                "tool_result_count": len(state.get("tool_results", [])),
                "assistant_response": assistant_response,
                "follow_up_tool_calls": [
                    {
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    }
                    for tool_call in turn.tool_calls
                ],
            },
        )

        return {**state, "assistant_response": assistant_response}


def should_continue(state: ChatGraphState) -> str:
    """Stop graph execution when a previous node already produced an answer."""
    return "stop" if state.get("assistant_response") else "continue"


def should_force_purchase_history_tool(message: str) -> bool:
    """Return whether account-domain text should receive purchase-history context."""
    return has_account_fact_intent(message)


def has_account_fact_intent(message: str) -> bool:
    """Return whether text asks for account-backed purchase/order facts."""
    normalized_message = message.casefold()
    account_domain_terms = (
        "account",
        "activity",
        "billing",
        "customer",
        "delivery",
        "digital",
        "history",
        "license",
        "order",
        "orders",
        "purchase",
        "purchases",
        "puchase",
        "puchases",
        "refund",
        "return",
        "shipment",
        "shipping",
        "subscription",
        "tracking",
    )
    fact_terms = (
        "amount",
        "count",
        "date",
        "dates",
        "between",
        "first",
        "how many",
        "last",
        "made",
        "month",
        "months",
        "on",
        "over",
        "status",
        "statuses",
        "summarize",
        "summary",
        "this",
        "total",
        "type",
        "under",
        "week",
        "weeks",
    )
    return any(term in normalized_message for term in account_domain_terms) and (
        any(term in normalized_message for term in fact_terms)
        or "?" in normalized_message
    )


def has_invalid_pseudo_tool_output(content: str | None) -> bool:
    """Detect malformed textual tool-call attempts returned as model content."""
    if not content:
        return False

    normalized_content = content.casefold()
    return bool(
        re.search(r"\bto\s*=\s*get_[a-z0-9_]+", normalized_content)
        or re.search(r"\bget_[a-z0-9_]+\s*\{", normalized_content)
    )


def parse_amount_threshold_query(message: str) -> dict[str, Any] | None:
    """Parse narrow amount-threshold purchase questions into deterministic tool args."""
    normalized_message = message.casefold()
    if not has_account_fact_intent(normalized_message):
        return None

    amount_match = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", normalized_message)
    if amount_match is None:
        amount_match = re.search(
            r"\b(\d+(?:\.\d{1,2})?)\s*(?:dollar|dollars|usd)\b",
            normalized_message,
        )

    if amount_match is None:
        return None

    comparison = parse_threshold_comparison(normalized_message)
    if comparison is None:
        return None

    amount = Decimal(amount_match.group(1))
    return {
        "threshold_cents": dollars_to_cents(amount),
        "comparison": comparison,
    }


def parse_threshold_comparison(message: str) -> str | None:
    """Return the comparison operator implied by narrow threshold phrasing."""
    comparison_patterns = (
        ("gte", ("at least", "greater than or equal", "more than or equal")),
        ("lte", ("at most", "less than or equal", "under or equal", "up to")),
        ("gt", ("over", "more than", "greater than", "above")),
        ("lt", ("under", "less than", "below")),
    )
    for comparison, patterns in comparison_patterns:
        if any(pattern in message for pattern in patterns):
            return comparison
    return None


def parse_model_threshold_arguments(arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Validate model-provided threshold arguments before tool execution."""
    comparison = arguments.get("comparison")
    threshold_cents = arguments.get("threshold_cents")
    if comparison not in {"gt", "gte", "lt", "lte"}:
        return None
    if not isinstance(threshold_cents, int) or threshold_cents < 0:
        return None
    return {"comparison": comparison, "threshold_cents": threshold_cents}


def parse_date_range_query(
    message: str,
    *,
    today: date | None = None,
    timezone_name: str = DEFAULT_CUSTOMER_TIMEZONE,
) -> dict[str, str] | None:
    """Parse narrow purchase date-range questions into deterministic tool args."""
    normalized_message = message.casefold()
    if not has_account_fact_intent(normalized_message):
        return None

    timezone = get_timezone(timezone_name)
    reference_date = today or datetime.now(timezone).date()

    try:
        last_week_range = parse_relative_week_range(normalized_message, reference_date)
        if last_week_range is not None:
            start_date, end_date, label = last_week_range
            return date_range_query(start_date, end_date, timezone_name, label)

        month_day_range = parse_month_day_range(normalized_message, reference_date.year)
        if month_day_range is not None:
            start_date, end_date, label = month_day_range
            return date_range_query(start_date, end_date, timezone_name, label)

        first_week_range = parse_first_week_of_month(normalized_message, reference_date.year)
        if first_week_range is not None:
            start_date, end_date, label = first_week_range
            return date_range_query(start_date, end_date, timezone_name, label)

        month_range = parse_month_range(normalized_message, reference_date.year)
        if month_range is not None:
            start_date, end_date, label = month_range
            return date_range_query(start_date, end_date, timezone_name, label)
    except ValueError:
        return None

    return None


def parse_relative_week_range(
    message: str,
    reference_date: date,
) -> tuple[date, date, str] | None:
    """Parse supported relative week phrases."""
    days_since_sunday = (reference_date.weekday() + 1) % 7
    current_week_start = reference_date - timedelta(days=days_since_sunday)
    if "last week" in message:
        start_date = current_week_start - timedelta(days=7)
        end_date = start_date + timedelta(days=6)
        return start_date, end_date, "last week"
    if "this week" in message:
        start_date = current_week_start
        end_date = reference_date
        return start_date, end_date, "this week"
    return None


def parse_first_week_of_month(
    message: str,
    default_year: int,
) -> tuple[date, date, str] | None:
    """Parse 'first week of Month' as Month 1 through Month 7."""
    match = re.search(r"\bfirst week of\s+([a-z]+)(?:\s+(\d{4}))?\b", message)
    if match is None:
        return None

    month_number = parse_month_name(match.group(1))
    if month_number is None:
        return None

    year = int(match.group(2) or default_year)
    start_date = date(year, month_number, 1)
    end_date = date(year, month_number, 7)
    return start_date, end_date, f"first week of {format_month_name(month_number)} {year}"


def parse_month_day_range(
    message: str,
    default_year: int,
) -> tuple[date, date, str] | None:
    """Parse 'May 1 to May 7', 'between June 1 and June 15', and 'on July 4'."""
    range_match = re.search(
        r"\b(?:between\s+)?([a-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?\s+"
        r"(?:to|through|and|-)\s+(?:(?:([a-z]+)\s+)?(\d{1,2})(?:,\s*(\d{4}))?)\b",
        message,
    )
    if range_match is not None:
        start_month = parse_month_name(range_match.group(1))
        if start_month is None:
            return None

        end_month = parse_month_name(range_match.group(4)) if range_match.group(4) else start_month
        if end_month is None:
            return None

        start_year = int(range_match.group(3) or default_year)
        end_year = int(range_match.group(6) or start_year)
        start_date = date(start_year, start_month, int(range_match.group(2)))
        end_date = date(end_year, end_month, int(range_match.group(5)))
        return start_date, end_date, format_date_range_label_for_query(start_date, end_date)

    on_match = re.search(r"\bon\s+([a-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?\b", message)
    if on_match is None:
        return None

    month_number = parse_month_name(on_match.group(1))
    if month_number is None:
        return None

    matched_date = date(
        int(on_match.group(3) or default_year),
        month_number,
        int(on_match.group(2)),
    )
    return matched_date, matched_date, format_date_range_label_for_query(matched_date, matched_date)


def parse_month_range(
    message: str,
    default_year: int,
) -> tuple[date, date, str] | None:
    """Parse 'in May' as the full calendar month."""
    match = re.search(r"\bin\s+([a-z]+)(?:\s+(\d{4}))?\b", message)
    if match is None:
        return None

    month_number = parse_month_name(match.group(1))
    if month_number is None:
        return None

    year = int(match.group(2) or default_year)
    start_date = date(year, month_number, 1)
    if month_number == 12:
        end_date = date(year, 12, 31)
    else:
        end_date = date(year, month_number + 1, 1) - timedelta(days=1)
    return start_date, end_date, f"{format_month_name(month_number)} {year}"


def date_range_query(
    start_date: date,
    end_date: date,
    timezone_name: str,
    label: str,
) -> dict[str, str]:
    """Return date-range tool arguments with ISO dates."""
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": timezone_name,
        "label": label,
    }


def parse_month_name(value: str) -> int | None:
    """Return a month number for supported English month names."""
    months = {
        "january": 1,
        "jan": 1,
        "february": 2,
        "feb": 2,
        "march": 3,
        "mar": 3,
        "april": 4,
        "apr": 4,
        "may": 5,
        "june": 6,
        "jun": 6,
        "july": 7,
        "jul": 7,
        "august": 8,
        "aug": 8,
        "september": 9,
        "sep": 9,
        "sept": 9,
        "october": 10,
        "oct": 10,
        "november": 11,
        "nov": 11,
        "december": 12,
        "dec": 12,
    }
    return months.get(value.casefold())


def format_month_name(month_number: int) -> str:
    """Return an English month name."""
    return date(2000, month_number, 1).strftime("%B")


def format_date_range_label_for_query(start_date: date, end_date: date) -> str:
    """Return a stable date-range label for parsed queries."""
    if start_date == end_date:
        return f"{format_month_name(start_date.month)} {start_date.day}, {start_date.year}"
    return (
        f"{format_month_name(start_date.month)} {start_date.day}, {start_date.year} "
        f"through {format_month_name(end_date.month)} {end_date.day}, {end_date.year}"
    )


def parse_model_date_range_arguments(arguments: dict[str, Any]) -> dict[str, str] | None:
    """Validate model-provided date-range arguments before tool execution."""
    start_date_value = arguments.get("start_date")
    end_date_value = arguments.get("end_date")
    timezone_value = arguments.get("timezone") or DEFAULT_CUSTOMER_TIMEZONE
    if not isinstance(start_date_value, str) or not isinstance(end_date_value, str):
        return None
    if not isinstance(timezone_value, str):
        return None

    try:
        start_date = parse_iso_date(start_date_value)
        end_date = parse_iso_date(end_date_value)
        build_inclusive_date_range(
            start_date=start_date,
            end_date=end_date,
            timezone=get_timezone(timezone_value),
        )
    except ValueError:
        return None

    label = arguments.get("label") or format_date_range_label_for_query(start_date, end_date)
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": timezone_value,
        "label": str(label),
    }


def amount_matches_threshold(amount_cents: int, threshold_cents: int, comparison: str) -> bool:
    """Apply one supported threshold comparison."""
    if comparison == "gt":
        return amount_cents > threshold_cents
    if comparison == "gte":
        return amount_cents >= threshold_cents
    if comparison == "lt":
        return amount_cents < threshold_cents
    if comparison == "lte":
        return amount_cents <= threshold_cents
    raise ValueError(f"Unsupported threshold comparison: {comparison}.")


def get_purchase_count_by_amount_threshold_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for deterministic threshold purchase counts."""
    return {
        "name": "get_purchase_count_by_amount_threshold",
        "description": (
            "Count a customer's purchases that match an amount threshold using "
            "backend purchase data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "threshold_cents": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Purchase amount threshold in cents.",
                },
                "comparison": {
                    "type": "string",
                    "enum": ["gt", "gte", "lt", "lte"],
                    "description": "Comparison to apply against purchase amount.",
                },
            },
            "required": ["threshold_cents", "comparison"],
            "additionalProperties": False,
        },
    }


def get_purchase_history_by_date_range_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for deterministic date-range purchase history."""
    return {
        "name": "get_purchase_history_by_date_range",
        "description": (
            "Retrieve a customer's purchases and aggregate totals for an inclusive "
            "local date range."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Inclusive local start date in YYYY-MM-DD format.",
                },
                "end_date": {
                    "type": "string",
                    "description": "Inclusive local end date in YYYY-MM-DD format.",
                },
                "timezone": {
                    "type": "string",
                    "description": "Customer timezone, such as America/Chicago.",
                },
            },
            "required": ["start_date", "end_date", "timezone"],
            "additionalProperties": False,
        },
    }


def get_customer_purchase_history_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for the purchase-history reader."""
    return {
        "name": "get_customer_purchase_history",
        "description": (
            "Retrieve read-only purchase history and aggregate totals for one customer."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    }


def get_customer_purchase_history(
    application_service: ApplicationService,
    customer_id: str,
) -> dict[str, Any]:
    """Return sanitized purchase rows and deterministic aggregates."""
    purchases = application_service.list_user_purchases(customer_id)
    timezone = get_timezone(DEFAULT_CUSTOMER_TIMEZONE)
    rows = [build_purchase_tool_row(purchase, timezone) for purchase in purchases]

    return {
        "customer_id": customer_id,
        "purchases": rows,
        "aggregates": build_purchase_history_aggregates(rows),
    }


def get_purchase_history_by_date_range(
    application_service: ApplicationService,
    customer_id: str,
    *,
    start_date: str,
    end_date: str,
    timezone_name: str,
    label: str | None = None,
) -> dict[str, Any]:
    """Return deterministic purchase history and totals for one inclusive date range."""
    timezone = get_timezone(timezone_name)
    date_range = build_inclusive_date_range(
        start_date=parse_iso_date(start_date),
        end_date=parse_iso_date(end_date),
        timezone=timezone,
        label=label,
    )
    purchases = application_service.list_user_purchases(customer_id)
    rows = [
        build_purchase_tool_row(purchase, timezone)
        for purchase in purchases
        if is_datetime_in_inclusive_date_range(purchase["purchased_at"], date_range)
    ]

    return {
        "customer_id": customer_id,
        "date_range": build_date_range_output(date_range),
        "aggregates": build_purchase_history_aggregates(rows),
        "purchases": rows,
    }


def get_purchase_count_by_amount_threshold(
    application_service: ApplicationService,
    customer_id: str,
    *,
    threshold_cents: int,
    comparison: str,
) -> dict[str, Any]:
    """Return deterministic purchase count and totals for one amount threshold."""
    purchases = application_service.list_user_purchases(customer_id)
    matching_purchases = [
        purchase
        for purchase in purchases
        if amount_matches_threshold(
            int(purchase["amount_cents"]),
            threshold_cents,
            comparison,
        )
    ]
    total_amount_cents = sum(int(purchase["amount_cents"]) for purchase in matching_purchases)
    return {
        "count": len(matching_purchases),
        "matching_purchase_ids": [str(purchase["id"]) for purchase in matching_purchases],
        "total_amount_cents": total_amount_cents,
        "total_amount_dollars": cents_to_dollar_string(total_amount_cents),
        "threshold_cents": threshold_cents,
        "threshold_dollars": cents_to_dollar_string(threshold_cents),
        "comparison": comparison,
    }


def build_purchase_tool_row(
    purchase: dict[str, Any],
    timezone: ZoneInfo,
) -> dict[str, Any]:
    """Return a sanitized purchase row for model-facing account tool payloads."""
    amount_cents = int(purchase["amount_cents"])
    purchased_at = purchase["purchased_at"]
    return {
        "id": str(purchase["id"]),
        "order_number": purchase["order_number"],
        "purchase_type": purchase["purchase_type"],
        "product_name": purchase["product_name"],
        "amount_cents": amount_cents,
        "amount_dollars": cents_to_dollar_string(amount_cents),
        "amount_display": format_cents(amount_cents),
        "purchased_at": purchased_at,
        "purchased_date_display": format_date(purchased_at, timezone),
        "status": purchase["status"],
    }


def build_date_range_output(date_range: InclusiveDateRange) -> dict[str, str]:
    """Return model-facing metadata for an inclusive date range."""
    return {
        "start_date": date_range.start_date.isoformat(),
        "end_date": date_range.end_date.isoformat(),
        "label": date_range.label,
        "timezone": str(date_range.timezone),
    }


def build_purchase_history_aggregates(purchases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute purchase-history counts and totals for model consumption."""
    by_purchase_type: dict[str, dict[str, Any]] = {}
    by_status: dict[str, dict[str, Any]] = {}
    total_amount_cents = 0

    for purchase in purchases:
        amount_cents = int(purchase["amount_cents"])
        total_amount_cents += amount_cents

        increment_aggregate_bucket(by_purchase_type, purchase["purchase_type"], amount_cents)
        increment_aggregate_bucket(by_status, purchase["status"], amount_cents)

    return {
        "total_purchase_count": len(purchases),
        "total_amount_cents": total_amount_cents,
        "total_amount_dollars": cents_to_dollar_string(total_amount_cents),
        "by_purchase_type": by_purchase_type,
        "by_status": by_status,
    }


def increment_aggregate_bucket(
    buckets: dict[str, dict[str, Any]],
    key: str,
    amount_cents: int,
) -> None:
    """Increment one count/amount aggregate bucket."""
    bucket = buckets.setdefault(key, {"count": 0, "total_amount_cents": 0})
    bucket["count"] += 1
    bucket["total_amount_cents"] += amount_cents
    bucket["total_amount_dollars"] = cents_to_dollar_string(bucket["total_amount_cents"])


def log_trace_step(
    state: ChatGraphState,
    *,
    message: str,
    event_type: str,
    data: dict[str, Any] | None = None,
    level: int = logging.INFO,
) -> ChatGraphState:
    """Emit one console-visible sequential trace event for chat orchestration."""
    frame = inspect.currentframe()
    caller_frame = frame.f_back if frame is not None else None
    file_path = (
        str(Path(caller_frame.f_code.co_filename).resolve())
        if caller_frame is not None
        else str(Path(__file__).resolve())
    )
    line_number = caller_frame.f_lineno if caller_frame is not None else 0
    step = int(state.get("trace_step", 1))
    event = {
        "type": event_type,
        "step": step,
        "file": file_path,
        "line": line_number,
        "message": message,
        "data": data or {},
    }
    logger.log(
        level,
        "ai.chat.trace %s",
        json.dumps(event, default=str, sort_keys=True),
        extra={"event": event},
    )
    console_logger.log(
        level,
        "ai.chat.trace %s",
        json.dumps(event, default=str, sort_keys=True),
    )
    return {**state, "trace_step": step + 1}


def parse_tool_arguments(arguments: str | None) -> dict[str, Any]:
    """Parse model tool-call arguments defensively."""
    if not arguments:
        return {}

    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}
