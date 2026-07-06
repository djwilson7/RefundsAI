"""LangGraph-backed AI chat orchestration for read-only purchase intelligence."""

from __future__ import annotations

import inspect
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
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
from refunds_ai_api.services.refund_policy_catalog import (
    PolicyPurchaseType,
    get_refund_policy,
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
REFUND_WORKFLOW_NOT_READY_RESPONSE = (
    "I can explain refund policy, but I cannot start or change a refund workflow yet."
)
REFUND_WORKFLOW_CONFIRMATION_REQUIRED_RESPONSE = (
    "Please confirm the product name or order number before continuing the refund workflow."
)
CUSTOMER_CONTEXT_REQUIRED_RESPONSE = (
    "I need an active customer session before I can inspect purchase history. "
    "Please load a mock customer, then ask again."
)
REFUND_CONTEXT_STAGES = {
    "eligibility_confirmed",
    "ineligible",
    "awaiting_customer_confirmation",
    "awaiting_return_label",
    "return_label_ready",
}
EMPTY_CONVERSATION_STATE = {
    "selected_purchase_type": None,
    "selected_product": None,
    "selected_purchase_id": None,
    "selected_purchase_ids": [],
    "selected_scope_label": None,
    "selected_policy_scope": None,
    "selected_date_range": None,
    "selected_refund_purchase_ids": [],
    "selected_refund_context": None,
    "active_refund_context": None,
    "current_page": None,
}
ROUTING_PRECEDENCE = (
    "page_purchase_reference",
    "active_refund_workflow_context",
    "explicit_purchase_reference",
    "selected_single_purchase",
    "scoped_selected_purchase_set",
    "aggregate_list_scope_capture",
    "explicit_policy_intent",
    "explicit_eligibility_intent",
    "supported_mutation_intent",
    "clarification",
)
FORBIDDEN_CUSTOMER_RESPONSE_TERMS = (
    "selected context",
    "selected set",
    "resolver",
    "tool",
    "state",
    "purchase_ids",
    "node",
    "graph",
)
SUPPORTED_ACCOUNT_TOPICS = (
    "account, purchases, orders, refund policies, refund-related questions, "
    "and account activity"
)
SYSTEM_PROMPT = (
    "You are RefundsAI's customer support assistant. For purchase-history "
    "questions, call the relevant read-only purchase tool before answering. For "
    "refund policy questions, call get_refund_policy before answering. For refund "
    "eligibility questions, call get_refund_eligibility before answering. Use only "
    "tool-provided purchase data for counts, totals, purchase types, statuses, "
    "and dates. Use only tool-provided refund policy data for policy explanations. "
    "Use only tool-provided refund eligibility data for eligibility explanations. "
    "Do not initiate refund workflow actions. Keep the conversation grounded in the "
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
        page_context: dict[str, Any] | None = None,
        conversation_state: dict[str, Any] | None = None,
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
                    "page_context": normalize_page_context(
                        page_context,
                        fallback_purchase_id=purchase_id,
                    ),
                    "conversation_state": normalize_conversation_state(conversation_state),
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
                conversation_state=normalize_conversation_state(conversation_state),
                next_trace_step=trace_step_start,
            )

        return AIChatResult(
            content=state.get("assistant_response") or CHAT_UNAVAILABLE_RESPONSE,
            graph_ready=self.model_client is not None,
            conversation_state=state.get("conversation_state")
            or normalize_conversation_state(conversation_state),
            next_trace_step=int(state.get("trace_step", trace_step_start)),
        )

    def _build_graph(self):
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
                "page_context": state.get("page_context"),
                "model": self.model,
            },
        )

        policy_lookup_query = resolve_refund_policy_query(
            state["message"],
            conversation_state=state.get("conversation_state"),
            page_context=state.get("page_context"),
        )
        eligibility_intent = has_refund_eligibility_intent(
            state["message"],
            conversation_state=state.get("conversation_state"),
        )
        blocked_intent = parse_refund_workflow_mutation_intent(state["message"])

        if (
            not state.get("customer_id")
            and policy_lookup_query is None
            and blocked_intent is None
            and not eligibility_intent
        ):
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

        if not state.get("customer_id") and eligibility_intent:
            state = log_trace_step(
                state,
                message=(
                    "Stopped before eligibility lookup because no customer "
                    "context was supplied."
                ),
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
        compact_context_message = build_compact_model_context_message(state)
        if compact_context_message is not None:
            messages.append(compact_context_message)
        tools = [
            get_customer_purchase_history_tool_schema(),
            get_purchase_count_by_amount_threshold_tool_schema(),
            get_purchase_history_by_date_range_tool_schema(),
            get_refund_policy_tool_schema(),
            get_refund_eligibility_tool_schema(),
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
                "model_context": build_model_context_summary(state),
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
        (
            policy_lookup_query,
            resolved_purchase,
            unresolved_product_reference,
        ) = resolve_refund_policy_query_with_purchase(
            state["message"],
            conversation_state=state.get("conversation_state"),
            page_context=state.get("page_context"),
            application_service=self.application_service,
            customer_id=customer_id,
        )
        page_reference = resolve_page_reference(
            self.application_service,
            customer_id,
            state.get("page_context"),
        )
        workflow_continuation_intent = parse_refund_workflow_continuation_intent(
            state["message"]
        )
        if workflow_continuation_intent is not None:
            normalized_state = normalize_conversation_state(
                state.get("conversation_state")
            )
            active_refund_context = normalized_state.get("active_refund_context")
            if active_refund_context is not None:
                state = log_trace_step(
                    state,
                    message=(
                        "Resolved refund workflow continuation from active refund "
                        "context."
                    ),
                    event_type="response.blocked",
                    data={
                        "reason": "refund_workflow_action_not_wired",
                        "purchase_id": active_refund_context["purchase_id"],
                        "next_action": active_refund_context.get("next_action"),
                        "model_context": build_model_context_summary(
                            {
                                **state,
                                "conversation_state": normalized_state,
                                "blocked_intent": workflow_continuation_intent,
                            },
                            page_reference=page_reference,
                        ),
                    },
                    level=logging.WARNING,
                )
                return {
                    **state,
                    "tool_results": [],
                    "assistant_response": build_refund_workflow_action_not_wired_response(
                        active_refund_context
                    ),
                    "blocked_intent": workflow_continuation_intent,
                    "conversation_state": update_conversation_state_for_page_reference(
                        normalized_state,
                        page_reference,
                    ),
                    "page_reference": page_reference,
                }

            state = log_trace_step(
                state,
                message=(
                    "Blocked refund workflow continuation because no active refund "
                    "context was available."
                ),
                event_type="response.blocked",
                data={
                    "reason": "active_refund_context_required",
                    "model_context": build_model_context_summary(
                        {
                            **state,
                            "conversation_state": normalized_state,
                            "blocked_intent": workflow_continuation_intent,
                        },
                        page_reference=page_reference,
                    ),
                },
                level=logging.WARNING,
            )
            return {
                **state,
                "tool_results": [],
                "assistant_response": REFUND_WORKFLOW_CONFIRMATION_REQUIRED_RESPONSE,
                "blocked_intent": workflow_continuation_intent,
                "conversation_state": update_conversation_state_for_page_reference(
                    normalized_state,
                    page_reference,
                ),
                "page_reference": page_reference,
            }

        blocked_refund_intent = parse_refund_workflow_mutation_intent(state["message"])
        eligibility_resolution = resolve_refund_eligibility_query(
            state["message"],
            conversation_state=state.get("conversation_state"),
            page_context=state.get("page_context"),
            application_service=self.application_service,
            customer_id=customer_id,
        )
        resolved_context_purchase = resolve_purchase_fact_context(
            self.application_service,
            customer_id,
            state["message"],
            state.get("conversation_state"),
            state.get("page_context"),
        )

        if blocked_refund_intent is not None:
            state = log_trace_step(
                state,
                message="Blocked refund request outside the current AI phase.",
                event_type="response.blocked",
                data={
                    "reason": f"{blocked_refund_intent}_not_ready",
                    "model_context": build_model_context_summary(
                        state,
                        page_reference=page_reference,
                    ),
                },
                level=logging.WARNING,
            )
            return {
                **state,
                "tool_results": [],
                "assistant_response": REFUND_WORKFLOW_NOT_READY_RESPONSE,
                "blocked_intent": blocked_refund_intent,
            }

        unresolved_reference = (
            eligibility_resolution.unresolved_product_reference
            if eligibility_resolution is not None
            and eligibility_resolution.unresolved_product_reference is not None
            else unresolved_product_reference
        )
        if unresolved_reference is not None:
            state = log_trace_step(
                state,
                message=(
                    "Blocked product-specific refund response because entity "
                    "resolution failed."
                ),
                event_type="response.blocked",
                data={
                    "reason": "product_reference_unresolved",
                    "product_reference": unresolved_reference,
                    "model_context": build_model_context_summary(
                        state,
                        page_reference=page_reference,
                    ),
                },
                level=logging.WARNING,
            )
            return {
                **state,
                "tool_results": [],
                "assistant_response": build_unresolved_product_response(
                    unresolved_reference
                ),
                "blocked_intent": "product_reference_unresolved",
                "conversation_state": update_conversation_state_for_page_reference(
                    state.get("conversation_state"),
                    page_reference,
                ),
                "page_reference": page_reference,
            }

        for tool_call in state.get("tool_calls", []):
            if tool_call.name == "get_customer_purchase_history":
                if eligibility_resolution is not None:
                    state = log_trace_step(
                        state,
                        message=(
                            "Overriding broad purchase-history tool selection with "
                            "the deterministic refund-eligibility tool."
                        ),
                        event_type="tool_call.overridden",
                        data={
                            "requested_tool_name": tool_call.name,
                            "tool_name": "get_refund_eligibility",
                            "reason": "eligibility_lookup_intent",
                            "purchase_ids": eligibility_resolution.purchase_ids,
                            "context": eligibility_resolution.context,
                        },
                    )
                    result = get_refund_eligibility(
                        self.application_service,
                        customer_id,
                        purchase_ids=eligibility_resolution.purchase_ids,
                        context=eligibility_resolution.context,
                    )
                    tool_results.append(
                        {
                            "tool_call_id": tool_call.id,
                            "name": "get_refund_eligibility",
                            "result": result,
                        }
                    )
                    state = log_trace_step(
                        state,
                        message="Backend refund-eligibility tool completed.",
                        event_type="tool_call.completed",
                        data={
                            "tool_name": "get_refund_eligibility",
                            "result": result,
                        },
                    )
                    continue

                if policy_lookup_query is not None:
                    state = log_trace_step(
                        state,
                        message=(
                            "Overriding broad purchase-history tool selection with "
                            "the deterministic refund-policy tool."
                        ),
                        event_type="tool_call.overridden",
                        data={
                            "requested_tool_name": tool_call.name,
                            "tool_name": "get_refund_policy",
                            "reason": "policy_lookup_intent",
                            **policy_lookup_query,
                        },
                    )
                    result = get_refund_policy(**policy_lookup_query)
                    tool_results.append(
                        {
                            "tool_call_id": tool_call.id,
                            "name": "get_refund_policy",
                            "result": result,
                        }
                    )
                    state = log_trace_step(
                        state,
                        message="Backend refund-policy tool completed.",
                        event_type="tool_call.completed",
                        data={
                            "tool_name": "get_refund_policy",
                            "result": result,
                        },
                    )
                    continue

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

            if tool_call.name == "get_refund_policy":
                policy_arguments = parse_model_refund_policy_arguments(tool_call.arguments)
                if policy_arguments is None:
                    state = log_trace_step(
                        state,
                        message="Ignoring invalid refund-policy tool arguments.",
                        event_type="tool_call.ignored",
                        data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                    )
                    continue
                if policy_lookup_query is None:
                    state = log_trace_step(
                        state,
                        message=(
                            "Ignoring refund-policy tool request because the "
                            "message was resolved as an account fact."
                        ),
                        event_type="tool_call.ignored",
                        data={
                            "tool_name": tool_call.name,
                            "arguments": tool_call.arguments,
                            "reason": "policy_intent_not_detected",
                        },
                    )
                    continue
                if policy_lookup_query is not None and policy_arguments != policy_lookup_query:
                    state = log_trace_step(
                        state,
                        message=(
                            "Overriding refund-policy tool arguments with resolved "
                            "conversation context."
                        ),
                        event_type="tool_call.overridden",
                        data={
                            "requested_tool_name": tool_call.name,
                            "tool_name": "get_refund_policy",
                            "reason": "resolved_policy_context",
                            "model_arguments": policy_arguments,
                            **policy_lookup_query,
                        },
                    )
                    policy_arguments = policy_lookup_query

                state = log_trace_step(
                    state,
                    message="Executing backend refund-policy tool.",
                    event_type="tool_call.executing",
                    data={
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_call.name,
                        "model_arguments": tool_call.arguments,
                    },
                )
                result = get_refund_policy(**policy_arguments)
                tool_results.append(
                    {
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "result": result,
                    }
                )
                state = log_trace_step(
                    state,
                    message="Backend refund-policy tool completed.",
                    event_type="tool_call.completed",
                    data={
                        "tool_name": tool_call.name,
                        "result": result,
                    },
                )
                continue

            if tool_call.name == "get_refund_eligibility":
                eligibility_arguments = parse_model_refund_eligibility_arguments(
                    tool_call.arguments
                )
                if eligibility_arguments is None:
                    state = log_trace_step(
                        state,
                        message="Ignoring invalid refund-eligibility tool arguments.",
                        event_type="tool_call.ignored",
                        data={"tool_name": tool_call.name, "arguments": tool_call.arguments},
                    )
                    continue
                if eligibility_resolution is None and resolved_context_purchase is not None:
                    state = log_trace_step(
                        state,
                        message=(
                            "Ignoring refund-eligibility tool request because the "
                            "message was resolved as an account fact."
                        ),
                        event_type="tool_call.ignored",
                        data={
                            "tool_name": tool_call.name,
                            "arguments": tool_call.arguments,
                            "reason": "eligibility_intent_not_detected",
                        },
                    )
                    continue
                if eligibility_resolution is not None:
                    effective_purchase_ids = eligibility_resolution.purchase_ids
                    effective_context = eligibility_resolution.context
                    if (
                        eligibility_arguments["purchase_ids"] != effective_purchase_ids
                        or eligibility_arguments["context"] != effective_context
                    ):
                        state = log_trace_step(
                            state,
                            message=(
                                "Overriding refund-eligibility tool arguments with "
                                "resolved conversation context."
                            ),
                            event_type="tool_call.overridden",
                            data={
                                "requested_tool_name": tool_call.name,
                                "tool_name": "get_refund_eligibility",
                                "reason": "resolved_eligibility_context",
                                "model_arguments": eligibility_arguments,
                                "purchase_ids": effective_purchase_ids,
                                "context": effective_context,
                            },
                        )
                else:
                    effective_purchase_ids = eligibility_arguments["purchase_ids"]
                    effective_context = eligibility_arguments["context"]

                state = log_trace_step(
                    state,
                    message="Executing backend refund-eligibility tool.",
                    event_type="tool_call.executing",
                    data={
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_call.name,
                        "model_arguments": tool_call.arguments,
                        "effective_purchase_ids": effective_purchase_ids,
                        "context": effective_context,
                    },
                )
                result = get_refund_eligibility(
                    self.application_service,
                    customer_id,
                    purchase_ids=effective_purchase_ids,
                    context=effective_context,
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
                    message="Backend refund-eligibility tool completed.",
                    event_type="tool_call.completed",
                    data={
                        "tool_name": tool_call.name,
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
        if resolved_context_purchase is not None:
            account_fact_intent = True

        if not tool_results and eligibility_resolution is not None:
            state = log_trace_step(
                state,
                message=(
                    "No supported tool was requested for a refund-eligibility query; "
                    "forcing the deterministic refund-eligibility tool."
                ),
                event_type="tool_call.forced",
                data={
                    "tool_name": "get_refund_eligibility",
                    "reason": "eligibility_lookup_intent",
                    "purchase_ids": eligibility_resolution.purchase_ids,
                    "context": eligibility_resolution.context,
                },
            )
            result = get_refund_eligibility(
                self.application_service,
                customer_id,
                purchase_ids=eligibility_resolution.purchase_ids,
                context=eligibility_resolution.context,
            )
            tool_results.append(
                {
                    "tool_call_id": "forced-get-refund-eligibility",
                    "name": "get_refund_eligibility",
                    "result": result,
                }
            )
            state = log_trace_step(
                state,
                message="Forced backend refund-eligibility tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": "get_refund_eligibility",
                    "result": result,
                },
            )
        elif not tool_results and policy_lookup_query is not None:
            state = log_trace_step(
                state,
                message=(
                    "No supported tool was requested for a refund-policy query; "
                    "forcing the deterministic refund-policy tool."
                ),
                event_type="tool_call.forced",
                data={
                    "tool_name": "get_refund_policy",
                    "reason": "policy_lookup_intent",
                    **policy_lookup_query,
                },
            )
            result = get_refund_policy(**policy_lookup_query)
            tool_results.append(
                {
                    "tool_call_id": "forced-get-refund-policy",
                    "name": "get_refund_policy",
                    "result": result,
                }
            )
            state = log_trace_step(
                state,
                message="Forced backend refund-policy tool completed.",
                event_type="tool_call.completed",
                data={
                    "tool_name": "get_refund_policy",
                    "result": result,
                },
            )
        elif not tool_results and threshold_query is not None:
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

        return {
            **state,
            "tool_results": tool_results,
            "account_fact_intent": account_fact_intent,
            "policy_lookup_intent": policy_lookup_query is not None,
            "eligibility_lookup_intent": eligibility_resolution is not None,
            "resolved_context_purchase": resolved_context_purchase,
            "conversation_state": update_conversation_state(
                state["message"],
                current_state=state.get("conversation_state"),
                tool_results=tool_results,
                policy_lookup_query=policy_lookup_query,
                eligibility_resolution=eligibility_resolution,
                resolved_purchase=resolved_purchase or resolved_context_purchase,
                page_reference=page_reference,
            ),
            "page_reference": page_reference,
        }

    def _generate_final_response(self, state: ChatGraphState) -> ChatGraphState:
        if state.get("assistant_response"):
            return state

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
        compact_context_message = build_compact_model_context_message(
            state,
            tool_results=tool_results,
            page_reference=state.get("page_reference"),
        )
        if compact_context_message is not None:
            messages.append(compact_context_message)
        resolved_context_purchase = state.get("resolved_context_purchase")
        if resolved_context_purchase is not None:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Backend-resolved purchase context: "
                        f"{json.dumps(resolved_context_purchase, default=str)}"
                    ),
                }
            )
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
        page_reference = state.get("page_reference")
        if page_reference:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Current page reference: "
                        f"{json.dumps(page_reference, default=str)}"
                    ),
                }
            )

        messages.append(
            {
                "role": "user",
                "content": (
                    "Answer the customer's request if it is about their account, "
                    "account history, purchases, orders, account activity, or "
                    "refund flows. Use the tool result when relevant. When the "
                    "backend provides resolved purchase context, use that concrete "
                    "purchase before ranking or selecting from broader purchase "
                    "history. If the customer asks a ranking follow-up without "
                    "refund, return, policy, eligibility, approval, or process "
                    "wording, answer only the purchase fact requested and do not "
                    "discuss refund policy. Do not expose backend terms such as "
                    "selected context, selected set, state, tool, resolver, or "
                    "purchase ids. For refund "
                    "policy questions, answer only from the refund-policy tool "
                    "result and keep the answer scoped to the customer's request. "
                    "For refund eligibility questions, answer only from the "
                    "refund-eligibility tool result and do not offer to start, "
                    "prepare, issue, submit, or process a refund. "
                    "If the request is unrelated, briefly redirect the customer "
                    "back to supported account topics. Return plain standard text "
                    "only, with no Markdown formatting."
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
                "model_context": build_model_context_summary(
                    state,
                    tool_results=tool_results,
                    page_reference=page_reference,
                ),
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

        assistant_response = sanitize_customer_response(
            turn.content or CHAT_UNAVAILABLE_RESPONSE,
            state,
        )
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


def sanitize_customer_response(response: str, state: ChatGraphState) -> str:
    """Replace customer-facing responses that expose backend routing terms."""
    if not contains_forbidden_customer_response_term(response):
        return response

    safe_response = build_customer_safe_resolved_purchase_response(state)
    return safe_response or (
        "I can help with account history, purchases, orders, refund policy, and "
        "refund eligibility."
    )


def contains_forbidden_customer_response_term(response: str) -> bool:
    """Return whether the assistant text exposes backend implementation terms."""
    normalized_response = response.casefold()
    for term in FORBIDDEN_CUSTOMER_RESPONSE_TERMS:
        pattern = r"(?<![a-z0-9_])" + re.escape(term.casefold()) + r"(?![a-z0-9_])"
        if re.search(pattern, normalized_response):
            return True
    return False


def build_customer_safe_resolved_purchase_response(
    state: ChatGraphState,
) -> str | None:
    """Return deterministic prose for resolved purchase facts when sanitizing."""
    resolved_purchase = state.get("resolved_context_purchase")
    if not isinstance(resolved_purchase, dict):
        return None

    product_name = resolved_purchase.get("product_name")
    if not isinstance(product_name, str) or not product_name:
        return None

    ranking_reference = parse_purchase_ranking_reference(state.get("message", ""))
    conversation_state = normalize_conversation_state(state.get("conversation_state"))
    scope_label = conversation_state.get("selected_scope_label") or "your purchases"
    if ranking_reference is not None:
        ranking_label = {
            "newest": "latest",
            "oldest": "oldest",
            "cheapest": "cheapest",
            "most_expensive": "most expensive",
        }[ranking_reference]
        amount_display = resolved_purchase.get("amount_display")
        amount_suffix = (
            f" for {amount_display}" if isinstance(amount_display, str) else ""
        )
        return (
            f"The {ranking_label} purchase from {scope_label} is "
            f"{product_name}{amount_suffix}."
        )

    return f"The purchase I found is {product_name}."


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


def normalize_conversation_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Return the compact, model-facing conversation state shape."""
    state = state or {}
    selected_purchase_type = state.get("selected_purchase_type")
    if selected_purchase_type not in {"digital", "physical", "subscription"}:
        selected_purchase_type = None

    selected_policy_scope = state.get("selected_policy_scope")
    if selected_policy_scope not in {
        "general",
        "product_type",
        "funds_release",
        "administrative_review",
    }:
        selected_policy_scope = None

    selected_date_range = state.get("selected_date_range")
    if not isinstance(selected_date_range, dict):
        selected_date_range = None

    selected_purchase_ids = state.get("selected_purchase_ids")
    if not isinstance(selected_purchase_ids, list):
        selected_purchase_ids = []

    selected_scope_label = state.get("selected_scope_label")
    if not isinstance(selected_scope_label, str) or not selected_scope_label.strip():
        selected_scope_label = None
    if (
        selected_scope_label is None
        and selected_purchase_ids
        and selected_purchase_type in {"digital", "physical", "subscription"}
    ):
        selected_scope_label = build_purchase_type_scope_label(selected_purchase_type)

    selected_refund_purchase_ids = state.get("selected_refund_purchase_ids")
    if not isinstance(selected_refund_purchase_ids, list):
        selected_refund_purchase_ids = []

    selected_refund_context = state.get("selected_refund_context")
    if not isinstance(selected_refund_context, str):
        selected_refund_context = None

    active_refund_context = normalize_active_refund_context(
        state.get("active_refund_context")
    )

    return {
        **EMPTY_CONVERSATION_STATE,
        "selected_purchase_type": selected_purchase_type,
        "selected_product": state.get("selected_product")
        if isinstance(state.get("selected_product"), str)
        else None,
        "selected_purchase_id": state.get("selected_purchase_id")
        if isinstance(state.get("selected_purchase_id"), str)
        else None,
        "selected_purchase_ids": [
            str(purchase_id)
            for purchase_id in selected_purchase_ids
            if isinstance(purchase_id, str)
        ],
        "selected_scope_label": selected_scope_label,
        "selected_policy_scope": selected_policy_scope,
        "selected_date_range": selected_date_range,
        "selected_refund_purchase_ids": [
            str(purchase_id)
            for purchase_id in selected_refund_purchase_ids
            if isinstance(purchase_id, str)
        ],
        "selected_refund_context": selected_refund_context,
        "active_refund_context": active_refund_context,
        "current_page": state.get("current_page")
        if isinstance(state.get("current_page"), dict)
        else None,
    }


def normalize_active_refund_context(value: Any) -> dict[str, Any] | None:
    """Return a validated active refund workflow context."""
    if not isinstance(value, dict):
        return None

    purchase_id = value.get("purchase_id")
    product_name = value.get("product_name")
    purchase_type = value.get("purchase_type")
    eligible = value.get("eligible")
    stage = value.get("stage")
    next_action = value.get("next_action")
    reason_codes = value.get("reason_codes")

    if not isinstance(purchase_id, str) or not purchase_id:
        return None
    if not isinstance(product_name, str) or not product_name:
        return None
    if purchase_type not in {"physical", "digital", "subscription"}:
        return None
    if not isinstance(eligible, bool):
        return None
    if stage not in REFUND_CONTEXT_STAGES:
        return None
    if next_action is not None and not isinstance(next_action, str):
        return None
    if not isinstance(reason_codes, list):
        reason_codes = []

    return {
        "purchase_id": purchase_id,
        "product_name": product_name,
        "purchase_type": purchase_type,
        "eligible": eligible,
        "stage": stage,
        "next_action": next_action,
        "reason_codes": [
            reason_code for reason_code in reason_codes if isinstance(reason_code, str)
        ],
    }


def normalize_page_context(
    page_context: dict[str, Any] | None,
    *,
    fallback_purchase_id: str | None = None,
) -> dict[str, Any]:
    """Return the compact current-page context accepted from the frontend."""
    page_context = page_context or {}
    surface = page_context.get("surface")
    if surface not in {"purchase_history", "purchase_detail"}:
        surface = "purchase_detail" if fallback_purchase_id else "purchase_history"

    purchase_id = page_context.get("purchase_id") or fallback_purchase_id
    if not isinstance(purchase_id, str):
        purchase_id = None

    return {
        "surface": surface,
        "purchase_id": purchase_id if surface == "purchase_detail" else None,
    }


def resolve_page_reference(
    application_service: ApplicationService | None,
    customer_id: str | None,
    page_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve the current page to a small backend-grounded reference."""
    normalized_context = normalize_page_context(page_context)
    if normalized_context["surface"] != "purchase_detail":
        return {"surface": "purchase_history", "purchase": None}

    purchase = resolve_purchase_by_id(
        application_service,
        customer_id,
        normalized_context["purchase_id"],
    )
    if purchase is None:
        return {"surface": "purchase_detail", "purchase": None}

    return {"surface": "purchase_detail", "purchase": purchase}


def resolve_refund_policy_query(
    message: str,
    *,
    conversation_state: dict[str, Any] | None,
    page_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve a policy lookup from explicit text plus compact conversation state."""
    policy_query, _resolved_purchase, _unresolved_product_reference = (
        resolve_refund_policy_query_with_purchase(
            message,
            conversation_state=conversation_state,
            page_context=page_context,
            application_service=None,
            customer_id=None,
        )
    )
    return policy_query


def resolve_refund_policy_query_with_purchase(
    message: str,
    *,
    conversation_state: dict[str, Any] | None,
    page_context: dict[str, Any] | None,
    application_service: ApplicationService | None,
    customer_id: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    """Resolve policy lookup arguments and an optional product match."""
    normalized_state = normalize_conversation_state(conversation_state)
    product_reference = extract_product_reference(message)
    policy_query = parse_refund_policy_query(
        message,
        conversation_state=normalized_state,
    )
    normalized_message = message.casefold()
    page_purchase = None
    if has_page_context_reference(normalized_message) and product_reference is None:
        page_purchase = resolve_purchase_by_id(
            application_service,
            customer_id,
            normalize_page_context(page_context).get("purchase_id"),
        )
    selected_single_purchase = resolve_selected_single_purchase(
        application_service,
        customer_id,
        message,
        normalized_state,
    )
    selected_set_purchase = resolve_purchase_from_selected_set(
        application_service,
        customer_id,
        message,
        normalized_state,
    )

    if policy_query is not None:
        resolved_purchase = None
        if product_reference is not None:
            resolved_purchase = resolve_purchase_reference(
                application_service,
                customer_id,
                product_reference,
            )
            if resolved_purchase is None:
                return None, None, product_reference
        else:
            resolved_purchase = (
                page_purchase or selected_single_purchase or selected_set_purchase
            )
            if resolved_purchase is None and policy_query.get("purchase_type") is None:
                resolved_purchase = resolve_purchase_mention(
                    application_service,
                    customer_id,
                    message,
                ) or resolve_global_ranked_purchase(
                    application_service,
                    customer_id,
                    message,
                )
        if resolved_purchase is not None:
            policy_query = {
                **policy_query,
                "scope": "product_type",
                "purchase_type": resolved_purchase["purchase_type"],
            }
        return policy_query, resolved_purchase, None

    if not has_policy_follow_up_intent(message, normalized_state):
        return None, None, None

    resolved_purchase = None
    if product_reference is not None:
        resolved_purchase = resolve_purchase_reference(
            application_service,
            customer_id,
            product_reference,
        )
        if resolved_purchase is None:
            return None, None, product_reference
    if resolved_purchase is None:
        resolved_purchase = page_purchase or selected_single_purchase or selected_set_purchase
    if resolved_purchase is None:
        resolved_purchase = resolve_purchase_mention(
            application_service,
            customer_id,
            message,
        ) or resolve_global_ranked_purchase(
            application_service,
            customer_id,
            message,
        )

    if resolved_purchase is not None:
        return (
            {
                "scope": normalized_state.get("selected_policy_scope") or "product_type",
                "purchase_type": resolved_purchase["purchase_type"],
            },
            resolved_purchase,
            None,
        )

    selected_purchase_type = normalized_state.get("selected_purchase_type")
    if selected_purchase_type is None:
        return None, None, None

    return (
        {
            "scope": normalized_state.get("selected_policy_scope") or "product_type",
            "purchase_type": selected_purchase_type,
        },
        None,
        None,
    )


def resolve_refund_eligibility_query(
    message: str,
    *,
    conversation_state: dict[str, Any] | None,
    page_context: dict[str, Any] | None,
    application_service: ApplicationService | None,
    customer_id: str | None,
) -> EligibilityResolution | None:
    """Resolve read-only refund eligibility intent to active-customer purchase ids."""
    normalized_state = normalize_conversation_state(conversation_state)
    if not has_refund_eligibility_intent(
        message,
        conversation_state=normalized_state,
    ):
        return None
    if application_service is None or customer_id is None:
        return EligibilityResolution([], "customer_context_required")

    product_reference = extract_product_reference(message)
    if product_reference is not None:
        resolved_purchase = resolve_purchase_reference(
            application_service,
            customer_id,
            product_reference,
        )
        if resolved_purchase is None:
            return EligibilityResolution(
                [],
                "product",
                unresolved_product_reference=product_reference,
            )
        return EligibilityResolution(
            [resolved_purchase["id"]],
            "product",
            resolved_purchase=resolved_purchase,
        )

    normalized_message = message.casefold()
    if has_context_reference(normalized_message):
        page_purchase = resolve_purchase_by_id(
            application_service,
            customer_id,
            normalize_page_context(page_context).get("purchase_id"),
        )
        if page_purchase is not None and has_page_context_reference(normalized_message):
            return EligibilityResolution(
                [page_purchase["id"]],
                "current_page",
                resolved_purchase=page_purchase,
            )

        selected_purchase = resolve_selected_single_purchase(
            application_service,
            customer_id,
            message,
            normalized_state,
        )
        if selected_purchase is not None:
            return EligibilityResolution(
                [selected_purchase["id"]],
                "selected_purchase",
                resolved_purchase=selected_purchase,
            )

        selected_ids = selected_purchase_ids_for_refund_context(
            application_service,
            customer_id,
            message,
            normalized_state,
        )
        if selected_ids:
            resolved_purchase = (
                resolve_purchase_by_id(application_service, customer_id, selected_ids[0])
                if len(selected_ids) == 1
                else None
            )
            return EligibilityResolution(
                selected_ids,
                "selected_set",
                resolved_purchase=resolved_purchase,
            )

    purchase_type = parse_purchase_type_filter(message)
    if purchase_type is not None:
        purchase_ids = [
            str(purchase["id"])
            for purchase in application_service.list_user_purchases(customer_id)
            if purchase.get("purchase_type") == purchase_type
        ]
        return EligibilityResolution(purchase_ids, purchase_type)

    date_range_query = parse_date_range_query(message)
    if date_range_query is not None:
        date_range_result = get_purchase_history_by_date_range(
            application_service,
            customer_id,
            start_date=date_range_query["start_date"],
            end_date=date_range_query["end_date"],
            timezone_name=date_range_query["timezone"],
            label=date_range_query.get("label"),
        )
        return EligibilityResolution(
            [
                str(purchase["id"])
                for purchase in date_range_result.get("purchases", [])
                if isinstance(purchase.get("id"), str)
            ],
            "date_range",
        )

    purchase_mention = resolve_purchase_mention(application_service, customer_id, message)
    if purchase_mention is not None:
        return EligibilityResolution(
            [purchase_mention["id"]],
            "product",
            resolved_purchase=purchase_mention,
        )

    purchase_ids = [
        str(purchase["id"])
        for purchase in application_service.list_user_purchases(customer_id)
        if isinstance(purchase.get("id"), str)
    ]
    return EligibilityResolution(purchase_ids, "all_purchases")


def has_refund_eligibility_intent(
    message: str,
    *,
    conversation_state: dict[str, Any] | None = None,
) -> bool:
    """Return whether text asks for backend-evaluated refund eligibility."""
    normalized_message = message.casefold()
    normalized_state = normalize_conversation_state(conversation_state)
    if parse_refund_workflow_mutation_intent(message) is not None:
        return False

    eligibility_patterns = (
        r"\bwhich\b.+\b(?:can|could)\s+be\s+refund(?:ed|able)\b",
        r"\bwhich\b.+\b(?:eligible|eligibility)\b",
        r"\bcan\s+i\s+refund\b",
        r"\bcould\s+i\s+refund\b",
        r"\bcan\s+i\s+get\s+my\s+money\s+back\b",
        r"\bam\s+i\s+eligible\b",
        r"\bis\b.+\beligible\s+for\s+(?:a\s+)?refund\b",
        r"\bcan\b.+\bbe\s+refund(?:ed|able)\b",
        r"\brefund\s+eligibility\b",
    )
    if any(re.search(pattern, normalized_message) for pattern in eligibility_patterns):
        return True

    has_prior_refund_context = bool(
        normalized_state.get("selected_refund_purchase_ids")
        or normalized_state.get("selected_refund_context")
    )
    return has_prior_refund_context and has_context_reference(normalized_message)


def parse_refund_workflow_mutation_intent(message: str) -> str | None:
    """Return a blocked future-phase refund workflow mutation intent, if present."""
    normalized_message = message.casefold()
    if "refund" not in normalized_message and "return" not in normalized_message:
        return None

    mutation_patterns = (
        r"\bstart\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bbegin\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bsubmit\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bprocess\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bissue\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bprepare\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\bfile\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"\brequest\s+(?:the\s+|a\s+|my\s+)?refund\b",
        r"^\s*refund\s+(?:it|this|that|me|my\s+card|my\s+payment)\b",
        r"\bgo\s+ahead\s+and\s+refund\b",
        r"\bmake\s+the\s+refund\b",
        r"\bcancel\s+and\s+refund\b",
    )
    if any(re.search(pattern, normalized_message) for pattern in mutation_patterns):
        return "workflow"

    return None


def parse_refund_workflow_continuation_intent(message: str) -> str | None:
    """Return whether text asks to continue the active refund workflow."""
    normalized_message = message.casefold()
    continuation_patterns = (
        r"\bgenerate\s+(?:the\s+|a\s+)?return\s+label\b",
        r"\bcreate\s+(?:the\s+|a\s+)?return\s+label\b",
        r"\bstart\s+(?:the\s+|a\s+|my\s+)?return\b",
        r"\bi(?:'d| would)\s+like\s+to\s+return\s+(?:it|the\s+item|this\s+item|that\s+item)\b",
        r"\breturn\s+(?:it|the\s+item|this\s+item|that\s+item)\b",
        r"^\s*proceed\s*[.!?]*\s*$",
        r"^\s*yes,?\s+continue\s*[.!?]*\s*$",
    )
    if any(re.search(pattern, normalized_message) for pattern in continuation_patterns):
        return "workflow_continuation"

    return None


def build_refund_workflow_action_not_wired_response(
    active_refund_context: dict[str, Any],
) -> str:
    """Return a deterministic Phase 3 response for a resolved workflow action."""
    product_name = active_refund_context["product_name"]
    next_action = active_refund_context.get("next_action")

    if active_refund_context.get("eligible") is not True:
        return (
            f"{product_name} is not eligible for a refund workflow, so there is "
            "no refund action to continue."
        )

    if next_action == "generate_return_label":
        return (
            f"{product_name} is eligible, and the next required step is generating "
            "a return label. That workflow action is not wired yet."
        )

    if isinstance(next_action, str) and next_action:
        return (
            f"{product_name} is eligible, and the next required step is "
            f"{humanize_refund_action(next_action)}. That workflow action is not "
            "wired yet."
        )

    return (
        f"{product_name} is eligible for a refund workflow. The next workflow "
        "action is not wired yet."
    )


def humanize_refund_action(action: str) -> str:
    """Return user-facing text for backend refund action keys."""
    labels = {
        "generate_return_label": "generating a return label",
        "invalidate_code": "invalidating the issued code",
        "invalidate_digital_entitlement": "invalidating the issued code",
        "cancel_subscription": "cancelling the subscription",
        "await_carrier_acceptance": "waiting for carrier acceptance",
        "issue_funds": "issuing funds",
        "request_refund": "preparing the refund",
    }
    return labels.get(action, action.replace("_", " "))


def selected_purchase_ids_for_refund_context(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
    conversation_state: dict[str, Any],
) -> list[str]:
    """Resolve selected purchase ids for eligibility pronoun follow-ups."""
    normalized_message = message.casefold()
    selected_ids = conversation_state.get("selected_refund_purchase_ids") or conversation_state.get(
        "selected_purchase_ids"
    )
    if not selected_ids:
        return []

    if has_temporal_purchase_reference(normalized_message) or has_reference_phrase(
        normalized_message,
        "that one",
    ):
        selected_purchase = resolve_purchase_from_selected_set(
            application_service,
            customer_id,
            message,
            {**conversation_state, "selected_purchase_ids": selected_ids},
        )
        return [selected_purchase["id"]] if selected_purchase is not None else []

    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("those", "them", "these")
    ):
        return [str(purchase_id) for purchase_id in selected_ids if isinstance(purchase_id, str)]

    if has_reference_phrase(normalized_message, "one"):
        selected_purchase = resolve_purchase_from_selected_set(
            application_service,
            customer_id,
            message,
            {**conversation_state, "selected_purchase_ids": selected_ids},
        )
        return [selected_purchase["id"]] if selected_purchase is not None else []

    return []


def has_policy_follow_up_intent(message: str, conversation_state: dict[str, Any]) -> bool:
    """Return whether a short follow-up can reuse prior policy context."""
    if conversation_state.get("selected_policy_scope") is None:
        return False

    normalized_message = message.casefold()
    follow_up_terms = (
        "one",
        "that",
        "that one",
        "those",
        "those purchases",
        "them",
        "it",
        "its",
        "this",
        "this item",
        "this purchase",
        "most recent one",
        "latest one",
        "newest",
        "oldest",
        "earliest",
        "first",
        "what about",
    )
    return any(has_reference_phrase(normalized_message, term) for term in follow_up_terms)


def extract_product_reference(message: str) -> str | None:
    """Extract a likely named product/SKU/order reference from supported follow-up text."""
    stripped_message = message.strip().strip("?.! ")
    normalized_message = stripped_message.casefold()
    if not stripped_message or has_purchase_ranking_reference(normalized_message):
        return None

    patterns = (
        r"\bcan\s+i\s+refund\s+(?:my\s+|the\s+)?(.+)$",
        r"\bcan\s+i\s+get\s+my\s+money\s+back\s+for\s+(?:my\s+|the\s+)?(.+)$",
        r"\bcan\s+(?:my\s+|the\s+)?(.+?)\s+be\s+refunded\b",
        r"\bwhat\s+about\s+(?:the\s+)?(.+)$",
        r"\brefund\s+policy\s+for\s+(?:the\s+)?(.+)$",
        r"\bpolicy\s+for\s+(?:the\s+)?(.+)$",
        r"\brules?\s+for\s+(?:the\s+)?(.+)$",
        r"\brequirements?\s+for\s+(?:the\s+)?(.+)$",
        r"\bfor\s+(?:the\s+)?(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, stripped_message, flags=re.IGNORECASE)
        if match is None:
            continue

        candidate = clean_product_reference(match.group(1))
        if is_named_product_reference(candidate):
            return candidate

    return None


def clean_product_reference(value: str) -> str:
    """Remove common trailing policy words around an extracted product reference."""
    candidate = value.strip().strip("?.! ")
    candidate = re.sub(
        r"\b(refund|return)\s+(policy|rules?|requirements?|window)\b",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    return " ".join(candidate.split())


def is_named_product_reference(candidate: str) -> bool:
    """Return whether a candidate looks like a concrete product/order reference."""
    if not candidate:
        return False

    normalized_candidate = normalize_match_text(candidate)
    if normalized_candidate in {
        "that",
        "that one",
        "those",
        "those purchases",
        "this",
        "this item",
        "this product",
        "this purchase",
        "this order",
        "it",
        "its",
        "one",
        "last one",
        "last purchase",
        "first one",
        "first purchase",
        "latest one",
        "most recent one",
        "latest",
        "most recent",
        "newest",
        "newest one",
        "oldest",
        "oldest one",
        "earliest",
        "earliest one",
        "first",
        "cheapest",
        "least expensive",
        "lowest price",
        "lowest priced",
        "most expensive",
        "highest price",
        "highest priced",
    }:
        return False
    if is_generic_purchase_type_reference(normalized_candidate):
        return False

    return True


def is_generic_purchase_type_reference(normalized_candidate: str) -> bool:
    """Return whether text is a product-type phrase rather than a named product."""
    if parse_policy_purchase_type(normalized_candidate) is None:
        return False

    terms = set(normalized_candidate.split())
    generic_terms = {
        "a",
        "an",
        "my",
        "our",
        "the",
        "purchase",
        "purchases",
        "product",
        "products",
        "return",
        "returns",
        "digital",
        "physical",
        "subscription",
        "subscriptions",
    }
    return terms.issubset(generic_terms)


def resolve_purchase_reference(
    application_service: ApplicationService | None,
    customer_id: str | None,
    product_reference: str,
) -> dict[str, Any] | None:
    """Resolve a named product, SKU, or order number against purchase history."""
    if application_service is None or customer_id is None:
        return None

    purchases = application_service.list_user_purchases(customer_id)
    return match_purchase_reference(product_reference, purchases)


def match_purchase_reference(
    product_reference: str,
    purchases: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Match product references by exact, normalized, partial, fuzzy, SKU, or order."""
    reference = product_reference.strip()
    normalized_reference = normalize_match_text(reference)
    if not normalized_reference:
        return None

    for purchase in purchases:
        if str(purchase.get("product_name", "")).casefold() == reference.casefold():
            return build_resolved_purchase(purchase)

    for purchase in purchases:
        searchable_values = purchase_search_values(purchase)
        if normalized_reference in searchable_values:
            return build_resolved_purchase(purchase)

    partial_matches = [
        purchase
        for purchase in purchases
        if any(
            normalized_reference in value or value in normalized_reference
            for value in purchase_search_values(purchase)
            if value
        )
    ]
    if len(partial_matches) == 1:
        return build_resolved_purchase(partial_matches[0])
    if len(partial_matches) > 1:
        return None

    fuzzy_matches = sorted(
        (
            (
                max(
                    SequenceMatcher(None, normalized_reference, value).ratio()
                    for value in purchase_search_values(purchase)
                    if value
                ),
                purchase,
            )
            for purchase in purchases
            if purchase_search_values(purchase)
        ),
        reverse=True,
        key=lambda match: match[0],
    )
    if fuzzy_matches and fuzzy_matches[0][0] >= 0.78:
        if len(fuzzy_matches) > 1 and fuzzy_matches[1][0] >= 0.74:
            return None
        return build_resolved_purchase(fuzzy_matches[0][1])

    return None


def purchase_search_values(purchase: dict[str, Any]) -> list[str]:
    """Return normalized purchase identifiers for entity resolution."""
    return [
        normalize_match_text(str(value))
        for value in (
            purchase.get("id"),
            purchase.get("product_name"),
            purchase.get("sku"),
            purchase.get("order_number"),
        )
        if value
    ]


def build_unresolved_product_response(product_reference: str) -> str:
    """Return a grounded clarification when product entity resolution fails."""
    return (
        f"I couldn't find a purchase matching '{product_reference}' in your account history. "
        "Could you confirm the product name, order number, SKU, or purchase date? "
        f"I can also help with {SUPPORTED_ACCOUNT_TOPICS}."
    )


def resolve_purchase_mention(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
) -> dict[str, Any] | None:
    """Resolve exact, partial, or fuzzy product mentions to a purchase row."""
    if application_service is None or customer_id is None:
        return None

    normalized_message = normalize_match_text(message)
    if not normalized_message:
        return None

    return match_purchase_reference(
        normalized_message,
        application_service.list_user_purchases(customer_id),
    )


def resolve_selected_single_purchase(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
    conversation_state: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve vague singular follow-ups to the selected purchase before set scope."""
    if not has_selected_single_purchase_reference(message):
        return None

    selected_purchase_id = conversation_state.get("selected_purchase_id")
    if not isinstance(selected_purchase_id, str):
        return None

    return resolve_purchase_by_id(application_service, customer_id, selected_purchase_id)


def resolve_purchase_from_selected_set(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
    conversation_state: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve pronoun and ranking follow-ups inside the selected purchase set."""
    if not has_selected_set_reference(message):
        return None

    selected_purchase_ids = conversation_state.get("selected_purchase_ids")
    if not selected_purchase_ids:
        return None

    purchases = list_purchases_by_ids(application_service, customer_id, selected_purchase_ids)
    if not purchases:
        return None

    if len(purchases) == 1:
        return build_resolved_purchase(purchases[0])

    normalized_message = message.casefold()
    ranking_reference = parse_purchase_ranking_reference(normalized_message)
    ranked_purchase = select_ranked_purchase(purchases, ranking_reference)
    if ranked_purchase is not None:
        return build_resolved_purchase(ranked_purchase)
    if has_reference_phrase(normalized_message, "one"):
        return build_resolved_purchase(sort_purchases_by_recency(purchases)[0])

    selected_purchase_type = conversation_state.get("selected_purchase_type")
    if selected_purchase_type in {"digital", "physical", "subscription"}:
        matching_type_purchases = [
            purchase
            for purchase in purchases
            if purchase.get("purchase_type") == selected_purchase_type
        ]
        if matching_type_purchases:
            return build_resolved_purchase(sort_purchases_by_recency(matching_type_purchases)[0])

    return None


def has_selected_single_purchase_reference(message: str) -> bool:
    """Return whether text points at the current selected purchase, not a set."""
    normalized_message = message.casefold()
    if has_purchase_ranking_reference(normalized_message):
        return False
    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("those", "them", "these", "those purchases")
    ):
        return False
    return any(
        has_reference_phrase(normalized_message, term)
        for term in (
            "it",
            "its",
            "that",
            "that item",
            "that purchase",
            "that product",
            "this item",
            "this purchase",
            "this product",
        )
    )


def resolve_global_ranked_purchase(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
) -> dict[str, Any] | None:
    """Resolve global ranked references only when no selected set exists."""
    ranking_reference = parse_purchase_ranking_reference(message.casefold())
    if ranking_reference is None:
        return None
    if application_service is None or customer_id is None:
        return None

    purchases = application_service.list_user_purchases(customer_id)
    if not purchases:
        return None

    ranked_purchase = select_ranked_purchase(purchases, ranking_reference)
    return build_resolved_purchase(ranked_purchase) if ranked_purchase is not None else None


def resolve_ranked_purchase_context(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
    conversation_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve non-policy ranked purchase questions from backend purchase rows."""
    normalized_state = normalize_conversation_state(conversation_state)
    ranking_reference = parse_purchase_ranking_reference(message)
    if ranking_reference is None:
        return None

    selected_purchase_ids = normalized_state.get("selected_purchase_ids")
    purchases = (
        list_purchases_by_ids(application_service, customer_id, selected_purchase_ids)
        if selected_purchase_ids
        else (
            application_service.list_user_purchases(customer_id)
            if application_service is not None and customer_id is not None
            else []
        )
    )
    ranked_purchase = select_ranked_purchase(purchases, ranking_reference)
    return (
        build_resolved_purchase_fact(ranked_purchase)
        if ranked_purchase is not None
        else None
    )


def resolve_purchase_fact_context(
    application_service: ApplicationService | None,
    customer_id: str | None,
    message: str,
    conversation_state: dict[str, Any] | None,
    page_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve deterministic purchase facts before honoring model tool choices."""
    normalized_message = message.casefold()
    normalized_state = normalize_conversation_state(conversation_state)

    if has_page_context_reference(normalized_message):
        page_purchase = resolve_purchase_fact_by_id(
            application_service,
            customer_id,
            normalize_page_context(page_context).get("purchase_id"),
        )
        if page_purchase is not None:
            return page_purchase

    product_reference = extract_product_reference(message)
    if product_reference is not None:
        explicit_purchase = resolve_purchase_reference_fact(
            application_service,
            customer_id,
            product_reference,
        )
        if explicit_purchase is not None:
            return explicit_purchase

    if has_selected_single_purchase_reference(message):
        selected_purchase = resolve_purchase_fact_by_id(
            application_service,
            customer_id,
            normalized_state.get("selected_purchase_id"),
        )
        if selected_purchase is not None:
            return selected_purchase

    return resolve_ranked_purchase_context(
        application_service,
        customer_id,
        message,
        normalized_state,
    )


def select_ranked_purchase(
    purchases: list[dict[str, Any]],
    ranking_reference: str | None,
) -> dict[str, Any] | None:
    """Select one purchase by a parsed ranking reference."""
    if not purchases or ranking_reference is None:
        return None
    if ranking_reference == "newest":
        return sort_purchases_by_recency(purchases)[0]
    if ranking_reference == "oldest":
        return sort_purchases_by_recency(purchases)[-1]
    if ranking_reference == "cheapest":
        return min(purchases, key=lambda purchase: int(purchase.get("amount_cents") or 0))
    if ranking_reference == "most_expensive":
        return max(purchases, key=lambda purchase: int(purchase.get("amount_cents") or 0))
    return None


def list_purchases_by_ids(
    application_service: ApplicationService | None,
    customer_id: str | None,
    purchase_ids: list[str],
) -> list[dict[str, Any]]:
    """Return active-customer purchase rows matching the provided ids."""
    if application_service is None or customer_id is None:
        return []

    selected_ids = set(purchase_ids)
    return [
        purchase
        for purchase in application_service.list_user_purchases(customer_id)
        if str(purchase.get("id")) in selected_ids
    ]


def resolve_purchase_reference_fact(
    application_service: ApplicationService | None,
    customer_id: str | None,
    product_reference: str,
) -> dict[str, Any] | None:
    """Resolve a named purchase reference and return fact fields."""
    resolved_purchase = resolve_purchase_reference(
        application_service,
        customer_id,
        product_reference,
    )
    if resolved_purchase is None:
        return None
    return resolve_purchase_fact_by_id(
        application_service,
        customer_id,
        resolved_purchase["id"],
    )


def resolve_purchase_fact_by_id(
    application_service: ApplicationService | None,
    customer_id: str | None,
    purchase_id: str | None,
) -> dict[str, Any] | None:
    """Resolve one purchase id to model-facing fact fields."""
    if application_service is None or customer_id is None or purchase_id is None:
        return None

    for purchase in application_service.list_user_purchases(customer_id):
        if str(purchase.get("id")) == purchase_id:
            return build_resolved_purchase_fact(purchase)

    return None


def sort_purchases_by_recency(purchases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort purchase rows from newest to oldest."""
    return sorted(
        purchases,
        key=lambda purchase: purchase.get("purchased_at") or datetime.min,
        reverse=True,
    )


def resolve_purchase_by_id(
    application_service: ApplicationService | None,
    customer_id: str | None,
    purchase_id: str | None,
) -> dict[str, Any] | None:
    """Resolve one current-page purchase id against the active customer's rows."""
    if application_service is None or customer_id is None or purchase_id is None:
        return None

    for purchase in application_service.list_user_purchases(customer_id):
        if str(purchase.get("id")) == purchase_id:
            return build_resolved_purchase(purchase)

    return None


def build_resolved_purchase(purchase: dict[str, Any]) -> dict[str, Any]:
    """Return the small resolved purchase shape stored in conversation state."""
    return {
        "id": str(purchase["id"]),
        "product_name": str(purchase["product_name"]),
        "sku": str(purchase.get("sku", "")),
        "order_number": str(purchase.get("order_number", "")),
        "purchase_type": purchase["purchase_type"],
    }


def build_resolved_purchase_fact(purchase: dict[str, Any]) -> dict[str, Any]:
    """Return a small resolved purchase shape for model-facing account facts."""
    amount_cents = int(purchase.get("amount_cents") or 0)
    return {
        **build_resolved_purchase(purchase),
        "amount_cents": amount_cents,
        "amount_display": format_cents(amount_cents),
        "purchased_at": purchase.get("purchased_at"),
    }


def normalize_match_text(value: str) -> str:
    """Normalize text for lightweight product resolution."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def has_selected_set_reference(message: str) -> bool:
    """Return whether text refers back to an item in the selected purchase set."""
    normalized_message = message.casefold()
    reference_terms = (
        "one",
        "that one",
        "those",
        "last one",
        "last purchase",
        "first one",
        "first purchase",
        "latest",
        "most recent",
        "newest",
        "oldest",
        "earliest",
        "first",
        "cheapest",
        "least expensive",
        "lowest price",
        "most expensive",
        "highest price",
        "most recent one",
        "latest one",
    )
    return any(has_reference_phrase(normalized_message, term) for term in reference_terms)


def has_recent_purchase_reference(message: str) -> bool:
    """Return whether text asks for the latest purchase in the active scope."""
    return parse_temporal_purchase_reference(message) == "newest"


def has_temporal_purchase_reference(message: str) -> bool:
    """Return whether text asks for a temporal purchase in the active scope."""
    return parse_temporal_purchase_reference(message) is not None


def has_purchase_ranking_reference(message: str) -> bool:
    """Return whether text asks for a ranked purchase in the active scope."""
    return parse_purchase_ranking_reference(message) is not None


def parse_purchase_ranking_reference(message: str) -> str | None:
    """Return a supported purchase ranking reference from user text."""
    normalized_message = message.casefold()
    temporal_reference = parse_temporal_purchase_reference(normalized_message)
    if temporal_reference is not None:
        return temporal_reference
    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("cheapest", "least expensive", "lowest price", "lowest priced")
    ):
        return "cheapest"
    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("most expensive", "highest price", "highest priced")
    ):
        return "most_expensive"
    return None


def parse_temporal_purchase_reference(message: str) -> str | None:
    """Return newest/oldest when text asks for a temporal purchase reference."""
    normalized_message = message.casefold()
    if any(
        has_reference_phrase(normalized_message, term)
        for term in (
            "latest",
            "latest one",
            "most recent",
            "most recent one",
            "newest",
            "newest one",
            "last one",
            "last purchase",
        )
    ):
        return "newest"

    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("oldest", "oldest one", "earliest", "earliest one")
    ):
        return "oldest"
    if any(
        has_reference_phrase(normalized_message, term)
        for term in ("first one", "first purchase")
    ) or (
        has_reference_phrase(normalized_message, "first")
        and not any(
            has_reference_phrase(normalized_message, term)
            for term in ("first week", "first month", "first quarter")
        )
    ):
        return "oldest"

    return None


def has_reference_phrase(message: str, phrase: str) -> bool:
    """Match context-reference phrases without treating product substrings as pronouns."""
    pattern = r"(?<![a-z0-9])" + r"\s+".join(
        re.escape(part) for part in phrase.casefold().split()
    ) + r"(?![a-z0-9])"
    return re.search(pattern, message.casefold()) is not None


def update_conversation_state(
    message: str,
    *,
    current_state: dict[str, Any] | None,
    tool_results: list[dict[str, Any]],
    policy_lookup_query: dict[str, Any] | None,
    eligibility_resolution: EligibilityResolution | None,
    resolved_purchase: dict[str, Any] | None,
    page_reference: dict[str, Any] | None,
) -> dict[str, Any]:
    """Update the compact state from deterministic tool outputs and routing."""
    next_state = normalize_conversation_state(current_state)

    explicit_type = parse_policy_purchase_type(message.casefold()) or parse_purchase_type_filter(
        message
    )
    if explicit_type is not None:
        next_state["selected_purchase_type"] = explicit_type

    if resolved_purchase is not None:
        active_refund_context = next_state.get("active_refund_context")
        selected_purchase_ids = next_state.get("selected_purchase_ids") or []
        next_state["selected_purchase_id"] = resolved_purchase["id"]
        next_state["selected_product"] = resolved_purchase["product_name"]
        next_state["selected_purchase_type"] = resolved_purchase["purchase_type"]
        if (
            selected_purchase_ids
            and resolved_purchase["id"] not in selected_purchase_ids
            and has_explicit_resolved_purchase_reference(message, resolved_purchase)
        ):
            next_state["selected_purchase_ids"] = []
            next_state["selected_scope_label"] = None
        if (
            isinstance(active_refund_context, dict)
            and active_refund_context.get("purchase_id") != resolved_purchase["id"]
        ):
            next_state["active_refund_context"] = None

    if page_reference is not None:
        next_state["current_page"] = page_reference

    if policy_lookup_query is not None:
        next_state["selected_policy_scope"] = policy_lookup_query["scope"]
        if policy_lookup_query.get("purchase_type") is not None:
            next_state["selected_purchase_type"] = policy_lookup_query["purchase_type"]

    if eligibility_resolution is not None and eligibility_resolution.purchase_ids:
        next_state["selected_refund_purchase_ids"] = eligibility_resolution.purchase_ids
        next_state["selected_refund_context"] = eligibility_resolution.context
        next_state["selected_purchase_ids"] = eligibility_resolution.purchase_ids
        if eligibility_resolution.resolved_purchase is not None:
            next_state["selected_purchase_id"] = eligibility_resolution.resolved_purchase["id"]
            next_state["selected_product"] = eligibility_resolution.resolved_purchase[
                "product_name"
            ]
            next_state["selected_purchase_type"] = eligibility_resolution.resolved_purchase[
                "purchase_type"
            ]

    for tool_result in tool_results:
        result = tool_result.get("result", {})
        if tool_result.get("name") == "get_purchase_count_by_amount_threshold":
            matching_purchase_ids = result.get("matching_purchase_ids")
            if isinstance(matching_purchase_ids, list):
                next_state["selected_purchase_ids"] = [
                    str(purchase_id)
                    for purchase_id in matching_purchase_ids
                    if isinstance(purchase_id, str)
                ]
                next_state["selected_scope_label"] = build_threshold_scope_label(result)
                next_state["selected_policy_scope"] = None
        if tool_result.get("name") == "get_purchase_history_by_date_range":
            date_range = result.get("date_range")
            next_state["selected_date_range"] = date_range
            next_state["selected_purchase_ids"] = [
                str(purchase["id"])
                for purchase in result.get("purchases", [])
                if isinstance(purchase.get("id"), str)
            ]
            next_state["selected_scope_label"] = build_date_range_scope_label(date_range)
            next_state["selected_policy_scope"] = None
        if tool_result.get("name") in {
            "get_customer_purchase_history",
            "get_purchase_history_by_date_range",
        }:
            selected_type = parse_purchase_type_filter(message)
            if selected_type is not None:
                matching_purchases = [
                    purchase
                    for purchase in result.get("purchases", [])
                    if purchase.get("purchase_type") == selected_type
                ]
                next_state["selected_purchase_ids"] = [
                    str(purchase["id"])
                    for purchase in matching_purchases
                    if isinstance(purchase.get("id"), str)
                ]
                next_state["selected_scope_label"] = build_purchase_type_scope_label(
                    selected_type
                )
                next_state["selected_policy_scope"] = None
                if len(matching_purchases) == 1:
                    next_state["selected_purchase_id"] = matching_purchases[0]["id"]
                    next_state["selected_product"] = matching_purchases[0]["product_name"]
        if tool_result.get("name") == "get_refund_eligibility":
            active_refund_context = build_active_refund_context_from_eligibility_result(
                result
            )
            next_state["active_refund_context"] = active_refund_context

    return next_state


def build_purchase_type_scope_label(purchase_type: str) -> str:
    """Return customer-facing scope labels for purchase-type aggregates."""
    labels = {
        "digital": "your digital purchases",
        "physical": "your physical purchases",
        "subscription": "your subscriptions",
    }
    return labels.get(purchase_type, "your purchases")


def build_date_range_scope_label(date_range: Any) -> str | None:
    """Return customer-facing scope labels for date-range aggregates."""
    if not isinstance(date_range, dict):
        return None
    label = date_range.get("label")
    if not isinstance(label, str) or not label.strip():
        return None
    normalized_label = label.casefold()
    if normalized_label in {"last week", "this week"}:
        return f"{normalized_label}'s purchases"
    return f"purchases from {label}"


def build_threshold_scope_label(result: dict[str, Any]) -> str | None:
    """Return customer-facing scope labels for amount-threshold aggregates."""
    comparison = result.get("comparison")
    threshold_dollars = result.get("threshold_dollars")
    if comparison not in {"gt", "gte", "lt", "lte"} or not isinstance(
        threshold_dollars,
        str,
    ):
        return None
    comparison_labels = {
        "gt": "over",
        "gte": "at least",
        "lt": "under",
        "lte": "at most",
    }
    return f"purchases {comparison_labels[comparison]} ${threshold_dollars}"


def has_explicit_resolved_purchase_reference(
    message: str,
    resolved_purchase: dict[str, Any],
) -> bool:
    """Return whether text explicitly names the resolved purchase or identifiers."""
    normalized_message = normalize_match_text(message)
    for key in ("id", "product_name", "sku", "order_number"):
        value = resolved_purchase.get(key)
        if not isinstance(value, str):
            continue
        normalized_value = normalize_match_text(value)
        if normalized_value and normalized_value in normalized_message:
            return True
    return extract_product_reference(message) is not None


def build_active_refund_context_from_eligibility_result(
    result: dict[str, Any],
) -> dict[str, Any] | None:
    """Build active refund context from a single resolved eligibility result."""
    purchases = result.get("purchases")
    if not isinstance(purchases, list) or len(purchases) != 1:
        return None

    purchase = purchases[0]
    if not isinstance(purchase, dict):
        return None

    purchase_id = purchase.get("id")
    product_name = purchase.get("product_name")
    purchase_type = purchase.get("purchase_type")
    required_action = purchase.get("required_action")
    eligible = purchase.get("can_enter_refund_workflow") is True
    if (
        not isinstance(purchase_id, str)
        or not isinstance(product_name, str)
        or purchase_type not in {"physical", "digital", "subscription"}
    ):
        return None

    next_action = required_action if isinstance(required_action, str) else None
    if next_action == "none":
        next_action = None

    if not eligible:
        stage = "ineligible"
        next_action = None
    elif next_action == "generate_return_label":
        stage = "awaiting_return_label"
    else:
        stage = "eligibility_confirmed"

    reasons = purchase.get("reasons")
    if not isinstance(reasons, list):
        reasons = []

    return {
        "purchase_id": purchase_id,
        "product_name": product_name,
        "purchase_type": purchase_type,
        "eligible": eligible,
        "stage": stage,
        "next_action": next_action,
        "reason_codes": [reason for reason in reasons if isinstance(reason, str)],
    }


def update_conversation_state_for_page_reference(
    current_state: dict[str, Any] | None,
    page_reference: dict[str, Any] | None,
) -> dict[str, Any]:
    """Update only current-page state when a request is blocked before tool execution."""
    next_state = normalize_conversation_state(current_state)
    if page_reference is not None:
        next_state["current_page"] = page_reference
    return next_state


def parse_purchase_type_filter(message: str) -> PolicyPurchaseType | None:
    """Return a purchase type named in account-history text."""
    return parse_policy_purchase_type(message.casefold())


def parse_refund_policy_query(
    message: str,
    *,
    conversation_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Parse refund policy lookup intent into deterministic tool arguments."""
    normalized_message = message.casefold()
    normalized_state = normalize_conversation_state(conversation_state)
    has_refund_domain = "refund" in normalized_message or "return" in normalized_message
    has_release_intent = has_funds_release_intent(normalized_message)
    if not has_refund_domain and not has_release_intent:
        return None
    if has_refund_eligibility_intent(message):
        return None
    if parse_refund_workflow_mutation_intent(message) is not None:
        return None

    purchase_type = parse_policy_purchase_type(normalized_message)
    if purchase_type is None and has_context_reference(normalized_message):
        purchase_type = normalized_state.get("selected_purchase_type")
    if has_administrative_review_intent(normalized_message):
        return {"scope": "administrative_review", "purchase_type": purchase_type}
    if has_release_intent:
        return {"scope": "funds_release", "purchase_type": purchase_type}
    if has_policy_lookup_intent(normalized_message):
        return {
            "scope": "product_type" if purchase_type is not None else "general",
            "purchase_type": purchase_type,
        }
    return None


def has_context_reference(message: str) -> bool:
    """Return whether text points at a prior selected entity or group."""
    reference_terms = (
        "one",
        "that",
        "that one",
        "those",
        "them",
        "it",
        "its",
        "this",
        "this item",
        "this purchase",
        "these",
        "latest",
        "most recent",
        "newest",
        "oldest",
        "earliest",
        "first",
        "most recent one",
        "latest one",
    )
    return any(has_reference_phrase(message, term) for term in reference_terms)


def has_page_context_reference(message: str) -> bool:
    """Return whether text explicitly points at the current page purchase."""
    reference_terms = (
        "this",
        "this item",
        "this product",
        "this purchase",
        "this order",
    )
    return any(has_reference_phrase(message, term) for term in reference_terms)


def parse_blocked_refund_intent(message: str) -> str | None:
    """Return blocked refund mutation intent for backward-compatible callers."""
    return parse_refund_workflow_mutation_intent(message)


def has_policy_lookup_intent(message: str) -> bool:
    """Return whether text asks for refund policy information."""
    policy_terms = (
        "guideline",
        "guidelines",
        "policy",
        "policies",
        "requirement",
        "requirements",
        "rule",
        "rules",
        "window",
    )
    return any(term in message for term in policy_terms)


def has_funds_release_intent(message: str) -> bool:
    """Return whether text asks about refund processing or fund release timing."""
    release_terms = (
        "3-10",
        "business day",
        "business days",
        "complete",
        "completed",
        "funds",
        "how long",
        "money back",
        "payment method",
        "processed",
        "processing",
        "released",
        "takes",
        "timeline",
    )
    return any(term in message for term in release_terms)


def has_administrative_review_intent(message: str) -> bool:
    """Return whether text asks about administrative review policy."""
    review_terms = (
        "admin review",
        "administrative review",
        "additional review",
        "fraud",
        "investigation",
        "manual review",
        "review",
        "suspected abuse",
    )
    return any(term in message for term in review_terms)


def parse_policy_purchase_type(message: str) -> PolicyPurchaseType | None:
    """Return a product type mentioned in policy lookup text."""
    if "digital" in message or "license" in message or "code" in message:
        return "digital"
    if "physical" in message or "shipment" in message or "shipping" in message:
        return "physical"
    if "subscription" in message or "billing period" in message or "auto-renew" in message:
        return "subscription"
    return None


def parse_model_refund_policy_arguments(arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Validate model-provided refund-policy arguments before tool execution."""
    scope = arguments.get("scope")
    purchase_type = arguments.get("purchase_type")
    if scope not in {"general", "product_type", "funds_release", "administrative_review"}:
        return None
    if purchase_type is not None and purchase_type not in {"digital", "physical", "subscription"}:
        return None
    return {"scope": scope, "purchase_type": purchase_type}


def parse_model_refund_eligibility_arguments(arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Validate model-provided refund-eligibility arguments before tool execution."""
    purchase_ids = arguments.get("purchase_ids")
    context = arguments.get("context", "model_requested")
    if not isinstance(purchase_ids, list) or not purchase_ids:
        return None
    if not all(isinstance(purchase_id, str) for purchase_id in purchase_ids):
        return None
    if not isinstance(context, str) or not context:
        context = "model_requested"
    return {"purchase_ids": purchase_ids, "context": context}


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


def get_refund_policy_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for deterministic refund policy lookup."""
    return {
        "name": "get_refund_policy",
        "description": (
            "Retrieve read-only RefundsAI refund policy sections scoped to the "
            "customer's policy question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": [
                        "general",
                        "product_type",
                        "funds_release",
                        "administrative_review",
                    ],
                    "description": "Policy lookup scope needed to answer the question.",
                },
                "purchase_type": {
                    "type": "string",
                    "enum": ["digital", "physical", "subscription"],
                    "description": "Optional product type when the question names one.",
                },
            },
            "required": ["scope"],
            "additionalProperties": False,
        },
    }


def get_refund_eligibility_tool_schema() -> dict[str, Any]:
    """Return the OpenAI tool schema for read-only backend refund eligibility."""
    return {
        "name": "get_refund_eligibility",
        "description": (
            "Evaluate read-only refund eligibility for backend-resolved purchase ids. "
            "This tool does not start, prepare, submit, process, or issue refunds."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "purchase_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Purchase ids already resolved by the backend chat graph.",
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Small context label such as product, digital, current_page, "
                        "selected_set, date_range, or all_purchases."
                    ),
                },
            },
            "required": ["purchase_ids"],
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


def get_refund_eligibility(
    application_service: ApplicationService,
    customer_id: str,
    *,
    purchase_ids: list[str],
    context: str,
) -> dict[str, Any]:
    """Return backend-evaluated read-only refund eligibility for active purchases."""
    active_purchases = {
        str(purchase["id"]): purchase
        for purchase in application_service.list_user_purchases(customer_id)
    }
    resolved_purchase_ids = [
        purchase_id
        for purchase_id in dict.fromkeys(purchase_ids)
        if isinstance(purchase_id, str) and purchase_id in active_purchases
    ]
    rows: list[dict[str, Any]] = []
    timezone = get_timezone(DEFAULT_CUSTOMER_TIMEZONE)

    for purchase_id in resolved_purchase_ids:
        purchase = active_purchases[purchase_id]
        workflow = application_service.get_refund_workflow(purchase_id)
        amount_cents = int(purchase["amount_cents"])
        refundable_amount_cents = int(workflow["refundable_amount_cents"])
        rows.append(
            {
                "id": purchase_id,
                "order_number": purchase["order_number"],
                "sku": purchase.get("sku"),
                "product_name": purchase["product_name"],
                "purchase_type": purchase["purchase_type"],
                "status": purchase["status"],
                "amount_cents": amount_cents,
                "amount_dollars": cents_to_dollar_string(amount_cents),
                "amount_display": format_cents(amount_cents),
                "purchased_at": purchase["purchased_at"],
                "purchased_date_display": format_date(purchase["purchased_at"], timezone),
                "refund_stage": workflow["refund_stage"],
                "can_enter_refund_workflow": workflow["can_enter_refund_workflow"],
                "can_prepare_refund": workflow["can_prepare_refund"],
                "can_issue_funds": workflow["can_issue_funds"],
                "required_action": workflow["required_action"],
                "refund_outcome": workflow["refund_outcome"],
                "refundable_amount_cents": refundable_amount_cents,
                "refundable_amount_dollars": cents_to_dollar_string(refundable_amount_cents),
                "refundable_amount_display": format_cents(refundable_amount_cents),
                "reasons": workflow["reasons"],
                "policy_facts": workflow["policy_facts"],
            }
        )

    return {
        "customer_id": customer_id,
        "context": context,
        "requested_purchase_ids": purchase_ids,
        "resolved_purchase_ids": resolved_purchase_ids,
        "purchase_count": len(rows),
        "eligible_count": sum(
            1 for row in rows if row["can_enter_refund_workflow"] is True
        ),
        "blocked_count": sum(1 for row in rows if row["refund_stage"] == "blocked"),
        "prepared_count": sum(1 for row in rows if row["refund_stage"] == "prepared"),
        "issued_count": sum(1 for row in rows if row["refund_stage"] == "issued"),
        "purchases": rows,
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
        "%s",
        format_trace_console_message(event),
    )
    return {**state, "trace_step": step + 1}


def format_trace_console_message(event: dict[str, Any]) -> str:
    """Return a compact, human-readable console summary for one trace event."""
    event_type = str(event.get("type", "unknown"))
    step = event.get("step", "?")
    message = str(event.get("message", "")).strip()
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    details = trace_console_details(event_type, data)
    summary = f"AI graph step {step}: {humanize_event_type(event_type)}"
    if message:
        summary = f"{summary} - {message}"
    if details:
        summary = f"{summary} ({details})"
    return summary


def build_model_context_summary(
    state: dict[str, Any],
    *,
    tool_results: list[dict[str, Any]] | None = None,
    page_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return compact context describing what the model can use."""
    effective_tool_results = tool_results
    if effective_tool_results is None:
        maybe_tool_results = state.get("tool_results")
        effective_tool_results = maybe_tool_results if isinstance(maybe_tool_results, list) else []

    return {
        "conversation_state": summarize_conversation_state(
            state.get("conversation_state")
        ),
        "page_context": page_context_label(state.get("page_context")),
        "page_reference": page_reference_label(page_reference or state.get("page_reference")),
        "tool_results": summarize_tool_results_for_context(effective_tool_results),
        "intents": summarize_intents(state),
        "blocked_intent": state.get("blocked_intent"),
    }


def build_compact_model_context_message(
    state: dict[str, Any],
    *,
    tool_results: list[dict[str, Any]] | None = None,
    page_reference: dict[str, Any] | None = None,
) -> dict[str, str] | None:
    """Return a small model-visible context message for follow-up grounding."""
    payload = compact_model_context_payload(
        state,
        tool_results=tool_results,
        page_reference=page_reference,
    )
    if not payload:
        return None

    return {
        "role": "user",
        "content": (
            "Compact conversation context for resolving follow-up references: "
            f"{json.dumps(payload, default=str, sort_keys=True)}"
        ),
    }


def compact_model_context_payload(
    state: dict[str, Any],
    *,
    tool_results: list[dict[str, Any]] | None = None,
    page_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return only model-relevant state, without transcript or page payloads."""
    conversation_state = normalize_conversation_state(state.get("conversation_state"))
    payload: dict[str, Any] = {}

    compact_state: dict[str, Any] = {}
    for key in (
        "selected_purchase_type",
        "selected_product",
        "selected_purchase_id",
        "selected_scope_label",
        "selected_policy_scope",
        "selected_refund_context",
    ):
        value = conversation_state.get(key)
        if value:
            compact_state[key] = value

    selected_purchase_ids = [
        str(purchase_id)
        for purchase_id in conversation_state.get("selected_purchase_ids", [])
        if isinstance(purchase_id, str)
    ]
    if selected_purchase_ids:
        compact_state["selected_purchase_ids"] = {
            "count": len(selected_purchase_ids),
            "ids": [short_id(purchase_id) for purchase_id in selected_purchase_ids[:5]],
        }

    selected_refund_purchase_ids = [
        str(purchase_id)
        for purchase_id in conversation_state.get("selected_refund_purchase_ids", [])
        if isinstance(purchase_id, str)
    ]
    if selected_refund_purchase_ids:
        compact_state["selected_refund_purchase_ids"] = {
            "count": len(selected_refund_purchase_ids),
            "ids": [
                short_id(purchase_id) for purchase_id in selected_refund_purchase_ids[:5]
            ],
        }

    active_refund_context = conversation_state.get("active_refund_context")
    if isinstance(active_refund_context, dict):
        compact_state["active_refund_context"] = {
            key: active_refund_context[key]
            for key in (
                "purchase_id",
                "product_name",
                "purchase_type",
                "eligible",
                "stage",
                "next_action",
            )
            if key in active_refund_context
        }

    current_page = page_reference or conversation_state.get("current_page")
    if isinstance(current_page, dict) and current_page.get("surface") == "purchase_detail":
        current_page_purchase = current_page.get("purchase")
        if not isinstance(current_page_purchase, dict):
            current_page_purchase = current_page
        compact_page_purchase: dict[str, Any] = {}
        purchase_id = current_page.get("purchase_id") or current_page_purchase.get("id")
        if purchase_id:
            compact_page_purchase["purchase_id"] = purchase_id
        for key in ("product_name", "purchase_type"):
            if current_page_purchase.get(key):
                compact_page_purchase[key] = current_page_purchase[key]
        if compact_page_purchase:
            compact_state["current_page_purchase"] = compact_page_purchase

    if compact_state:
        payload["conversation_state"] = compact_state

    resolved_purchase = state.get("resolved_context_purchase")
    if isinstance(resolved_purchase, dict):
        payload["resolved_purchase"] = {
            key: resolved_purchase[key]
            for key in ("id", "product_name", "purchase_type", "amount_display", "purchased_at")
            if resolved_purchase.get(key)
        }

    effective_tool_results = tool_results
    if effective_tool_results is None:
        maybe_tool_results = state.get("tool_results")
        effective_tool_results = maybe_tool_results if isinstance(maybe_tool_results, list) else []
    if effective_tool_results:
        payload["available_tool_results"] = summarize_tool_results_for_context(
            effective_tool_results
        )

    blocked_intent = state.get("blocked_intent")
    if blocked_intent:
        payload["blocked_intent"] = blocked_intent

    return payload


def humanize_event_type(event_type: str) -> str:
    """Convert a dotted trace event type into readable console text."""
    labels = {
        "graph.started": "Graph started",
        "graph.stopped": "Graph stopped",
        "message.received": "Message received",
        "model.failure": "Model unavailable",
        "model.invalid_tool_output": "Invalid model tool output",
        "model.requested": "Model requested",
        "response.blocked": "Response blocked",
        "response.generated": "Response generated",
        "route.response_returned": "Route response returned",
        "tool_call.completed": "Tool completed",
        "tool_call.executing": "Tool executing",
        "tool_call.forced": "Tool forced",
        "tool_call.ignored": "Tool ignored",
        "tool_call.overridden": "Tool overridden",
        "tool_call.requested": "Tool requested",
        "tool_call.skipped": "Tool skipped",
    }
    return labels.get(event_type, event_type.replace("_", " ").replace(".", " ").title())


def trace_console_details(event_type: str, data: dict[str, Any]) -> str:
    """Return event-specific details without dumping nested payloads."""
    if event_type == "message.received":
        return join_trace_fields(
            message=shorten_text(data.get("message")),
            customer=short_id(data.get("customer_id")),
            purchase=short_id(data.get("purchase_id")),
            page=page_context_label(data.get("page_context")),
            state=summarize_conversation_state(data.get("conversation_state")),
        )

    if event_type == "graph.started":
        return join_trace_fields(
            customer=short_id(data.get("customer_id")),
            purchase=short_id(data.get("purchase_id")),
            page=page_context_label(data.get("page_context")),
            model=data.get("model"),
        )

    if event_type == "model.requested":
        return join_trace_fields(
            phase=data.get("phase"),
            model=data.get("model"),
            messages=count_items(data.get("messages")),
            tools=tool_names(data.get("tools")),
            context=summarize_model_context(data.get("model_context")),
        )

    if event_type == "tool_call.requested":
        return join_trace_fields(
            tools=tool_call_names(data.get("tool_calls")),
            content=shorten_text(data.get("model_content")),
        )

    if event_type in {
        "tool_call.executing",
        "tool_call.completed",
        "tool_call.forced",
        "tool_call.overridden",
        "tool_call.ignored",
    }:
        return tool_trace_details(event_type, data)

    if event_type == "tool_call.skipped":
        return join_trace_fields(reason=data.get("reason"))

    if event_type == "response.blocked":
        return join_trace_fields(
            reason=data.get("reason"),
            product=data.get("product_reference"),
            context=summarize_model_context(data.get("model_context")),
        )

    if event_type == "response.generated":
        return join_trace_fields(
            model=data.get("model"),
            tools=data.get("tool_result_count"),
            response=shorten_text(data.get("assistant_response")),
        )

    if event_type == "route.response_returned":
        response = data.get("response") if isinstance(data.get("response"), dict) else {}
        message = response.get("message") if isinstance(response.get("message"), dict) else {}
        return join_trace_fields(
            model=data.get("model"),
            graph_ready=data.get("graph_ready"),
            response=shorten_text(message.get("content")),
            state=summarize_conversation_state(response.get("conversation_state")),
        )

    if event_type in {"graph.stopped", "model.failure", "model.invalid_tool_output"}:
        return join_trace_fields(
            reason=data.get("reason"),
            model=data.get("model"),
            detail=shorten_text(data.get("detail")),
        )

    return summarize_flat_trace_data(data)


def tool_trace_details(event_type: str, data: dict[str, Any]) -> str:
    """Return concise details for one tool-related trace event."""
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    return join_trace_fields(
        tool=data.get("tool_name"),
        requested=data.get("requested_tool_name"),
        reason=data.get("reason"),
        customer=short_id(data.get("customer_id") or data.get("effective_customer_id")),
        purchase_ids=summarize_ids(data.get("purchase_ids") or data.get("effective_purchase_ids")),
        context=data.get("context"),
        result=summarize_tool_result(result) if result else None,
        arguments="invalid" if event_type == "tool_call.ignored" else None,
    )


def summarize_tool_result(result: dict[str, Any]) -> str:
    """Return a compact description of model-facing tool output."""
    if "aggregates" in result and isinstance(result["aggregates"], dict):
        aggregates = result["aggregates"]
        return (
            f"{aggregates.get('total_purchase_count', 0)} purchases, "
            f"${aggregates.get('total_amount_dollars', '0.00')}"
        )
    if "purchase_count" in result:
        return (
            f"{result.get('purchase_count', 0)} purchases, "
            f"{result.get('eligible_count', 0)} eligible, "
            f"{result.get('blocked_count', 0)} blocked"
        )
    if "count" in result:
        return f"{result.get('count', 0)} matches"
    if "sections" in result:
        sections = result.get("sections")
        return f"{count_items(sections)} policy sections"
    return summarize_flat_trace_data(result)


def summarize_model_context(value: Any) -> str | None:
    """Return compact context the model had available for an event."""
    if not isinstance(value, dict):
        return None
    return join_trace_fields(
        state=value.get("conversation_state"),
        page=value.get("page_context"),
        page_ref=value.get("page_reference"),
        provided=value.get("tool_results"),
        intents=value.get("intents"),
        blocked=value.get("blocked_intent"),
    )


def summarize_conversation_state(value: Any) -> str | None:
    """Return compact selected conversation state without full payloads."""
    if not isinstance(value, dict):
        return None

    selected_ids = value.get("selected_purchase_ids")
    refund_ids = value.get("selected_refund_purchase_ids")
    date_range = value.get("selected_date_range")
    current_page = value.get("current_page")
    active_refund_context = value.get("active_refund_context")
    return join_trace_fields(
        type=value.get("selected_purchase_type"),
        product=value.get("selected_product"),
        purchase=short_id(value.get("selected_purchase_id")),
        selected=count_items(selected_ids),
        scope=value.get("selected_scope_label"),
        policy=value.get("selected_policy_scope"),
        date=date_range.get("label") if isinstance(date_range, dict) else None,
        refund_selected=count_items(refund_ids),
        refund_context=value.get("selected_refund_context"),
        active_refund=active_refund_context_label(active_refund_context),
        page=page_reference_label(current_page),
    )


def summarize_tool_results_for_context(tool_results: list[dict[str, Any]]) -> str | None:
    """Return compact summary of tool data made available to the model."""
    if not tool_results:
        return None

    summaries = []
    for tool_result in tool_results[:3]:
        if not isinstance(tool_result, dict):
            continue
        name = tool_result.get("name")
        result = tool_result.get("result")
        if isinstance(name, str) and isinstance(result, dict):
            summaries.append(f"{name}:{summarize_tool_result(result)}")

    if not summaries:
        return None
    suffix = f"; +{len(tool_results) - 3}" if len(tool_results) > 3 else ""
    return "; ".join(summaries) + suffix


def summarize_intents(state: dict[str, Any]) -> str | None:
    """Return compact graph intent flags that affect model/tool routing."""
    labels = []
    intent_fields = (
        ("account", "account_fact_intent"),
        ("policy", "policy_lookup_intent"),
        ("eligibility", "eligibility_lookup_intent"),
    )
    for label, intent_field in intent_fields:
        if state.get(intent_field) is True:
            labels.append(label)
    return ",".join(labels) if labels else None


def active_refund_context_label(value: Any) -> str | None:
    """Return a compact label for active refund workflow state."""
    if not isinstance(value, dict):
        return None
    return join_trace_fields(
        product=value.get("product_name"),
        purchase=short_id(value.get("purchase_id")),
        stage=value.get("stage"),
        next=value.get("next_action"),
    )


def summarize_flat_trace_data(data: dict[str, Any]) -> str:
    """Summarize shallow scalar data while ignoring nested payloads."""
    fields: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str | int | float | bool) or value is None:
            fields[key] = shorten_text(value)
    return join_trace_fields(**fields)


def join_trace_fields(**fields: Any) -> str:
    """Join non-empty trace fields into a stable compact string."""
    parts = []
    for key, value in fields.items():
        if value is None or value == "" or value == []:
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def count_items(value: Any) -> int | None:
    """Return item count for list-like trace fields."""
    return len(value) if isinstance(value, list) else None


def tool_names(tools: Any) -> str | None:
    """Return compact model tool names from OpenAI tool schemas."""
    if not isinstance(tools, list):
        return None
    names = [str(tool.get("name")) for tool in tools if isinstance(tool, dict) and tool.get("name")]
    if not names:
        return "none"
    return ", ".join(names)


def tool_call_names(tool_calls: Any) -> str | None:
    """Return compact model-requested tool names."""
    if not isinstance(tool_calls, list):
        return None
    names = [
        str(call.get("name"))
        for call in tool_calls
        if isinstance(call, dict) and call.get("name")
    ]
    return ", ".join(names) if names else "none"


def page_context_label(page_context: Any) -> str | None:
    """Return a compact page context label."""
    if not isinstance(page_context, dict):
        return None
    surface = page_context.get("surface")
    purchase_id = page_context.get("purchase_id")
    if purchase_id:
        return f"{surface}:{short_id(purchase_id)}"
    return str(surface) if surface else None


def page_reference_label(page_reference: Any) -> str | None:
    """Return a compact resolved page reference label."""
    if not isinstance(page_reference, dict):
        return None

    surface = page_reference.get("surface")
    purchase = page_reference.get("purchase")
    if isinstance(purchase, dict):
        product = purchase.get("product_name")
        purchase_type = purchase.get("purchase_type")
        purchase_id = short_id(purchase.get("id"))
        return join_trace_fields(
            surface=surface,
            product=product,
            type=purchase_type,
            id=purchase_id,
        )
    return str(surface) if surface else None


def summarize_ids(value: Any) -> str | None:
    """Return compact id list summary."""
    if not isinstance(value, list):
        return None
    if not value:
        return "none"
    visible = [short_id(item) for item in value[:3]]
    suffix = f"+{len(value) - 3}" if len(value) > 3 else ""
    return ",".join(item for item in visible if item) + suffix


def short_id(value: Any) -> str | None:
    """Return a short readable identifier for UUID-like values."""
    if not isinstance(value, str) or not value:
        return None
    if len(value) >= 8 and "-" in value:
        return value[:8]
    return value


def shorten_text(value: Any, *, limit: int = 96) -> str | None:
    """Return compact single-line text for console logs."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def parse_tool_arguments(arguments: str | None) -> dict[str, Any]:
    """Parse model tool-call arguments defensively."""
    if not arguments:
        return {}

    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}
