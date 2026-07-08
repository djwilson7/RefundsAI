"""Safe, dependency-optional token budget instrumentation for model calls."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger("refunds_ai_api.token_budget")
console_logger = logging.getLogger("uvicorn.error")

COMPONENT_NAMES = (
    "system_prompt",
    "developer_prompt",
    "current_user_message",
    "conversation_history",
    "conversation_state",
    "workflow_state",
    "policy_context",
    "customer_context",
    "purchase_context",
    "tool_definitions",
    "tool_results",
    "other_messages",
)


class TextTokenCounter(Protocol):
    """Count tokens for plain text."""

    name: str

    def count_text(self, value: str) -> int:
        """Return a non-negative token count."""
        ...


@dataclass(frozen=True)
class ApproximateTokenCounter:
    """Dependency-free fallback based on UTF-8-safe Python character length."""

    name: str = "approx_chars_div_4"

    def count_text(self, value: str) -> int:
        if not value:
            return 0
        return max(1, math.ceil(len(value) / 4))


@dataclass(frozen=True)
class TiktokenCounter:
    """Adapter around an available tiktoken encoding."""

    encoding: Any
    name: str

    def count_text(self, value: str) -> int:
        return len(self.encoding.encode(value)) if value else 0


def get_token_counter(model: str, *, force_fallback: bool = False) -> TextTokenCounter:
    """Return tiktoken when available, otherwise the safe approximation."""
    if force_fallback:
        return ApproximateTokenCounter()
    try:
        import tiktoken  # type: ignore[import-not-found]

        try:
            encoding = tiktoken.encoding_for_model(model)
        except Exception:
            encoding = tiktoken.get_encoding("cl100k_base")
        return TiktokenCounter(
            encoding=encoding,
            name=f"tiktoken:{encoding.name}",
        )
    except Exception:
        return ApproximateTokenCounter()


def count_serialized(value: Any, counter: TextTokenCounter) -> int:
    """Count a stable JSON representation, falling back to a safe string."""
    try:
        serialized = json.dumps(
            value,
            default=str,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except Exception:
        serialized = str(value)
    return counter.count_text(serialized)


def build_token_budget_breakdown(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    current_user_message: str,
    request_id: str | None,
    customer_id: str | None,
    page: str | None,
    output_text: str | None = None,
    counter: TextTokenCounter | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Categorize the exact model payload into a safe token budget report."""
    effective_counter = counter or get_token_counter(model)
    try:
        return _build_token_budget_breakdown(
            model=model,
            messages=messages,
            tools=tools,
            current_user_message=current_user_message,
            request_id=request_id,
            customer_id=customer_id,
            page=page,
            output_text=output_text,
            counter=effective_counter,
            diagnostics=diagnostics,
        )
    except Exception:
        if isinstance(effective_counter, ApproximateTokenCounter):
            return _empty_fallback_breakdown(
                model=model,
                request_id=request_id,
                customer_id=customer_id,
                page=page,
            )
        return _build_token_budget_breakdown(
            model=model,
            messages=messages,
            tools=tools,
            current_user_message=current_user_message,
            request_id=request_id,
            customer_id=customer_id,
            page=page,
            output_text=output_text,
            counter=ApproximateTokenCounter(),
            diagnostics=diagnostics,
        )


def _build_token_budget_breakdown(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    current_user_message: str,
    request_id: str | None,
    customer_id: str | None,
    page: str | None,
    output_text: str | None,
    counter: TextTokenCounter,
    diagnostics: dict[str, Any] | None,
) -> dict[str, Any]:
    components = dict.fromkeys(COMPONENT_NAMES, 0)
    uncategorized_labels: list[str] = []
    current_message_counted = False

    for index, message in enumerate(messages):
        role = str(message.get("role") or "unknown")
        content = message.get("content")
        content_text = content if isinstance(content, str) else stable_text(content)
        token_count = counter.count_text(content_text)
        component = categorize_message(
            role=role,
            content=content_text,
            current_user_message=current_user_message,
            current_message_counted=current_message_counted,
        )
        components[component] += token_count
        if component == "current_user_message":
            current_message_counted = True
        if component == "other_messages":
            uncategorized_labels.append(f"{role}_message_{index}")

    components["tool_definitions"] = (
        count_serialized(tools, counter) if tools else 0
    )
    output_tokens = counter.count_text(output_text or "")
    breakdown = {
        "model": model,
        "request_id": request_id,
        "customer_id": customer_id,
        "page": page,
        "input_tokens_total_estimated": sum(components.values()),
        "output_tokens_estimated": output_tokens,
        "tokenizer": counter.name,
        "components": components,
        "uncategorized_labels": uncategorized_labels,
    }
    if diagnostics:
        breakdown.update(diagnostics)
    breakdown.setdefault("tool_schema_tokens", components["tool_definitions"])
    breakdown.setdefault("tool_result_tokens", components["tool_results"])
    breakdown.setdefault("conversation_state_tokens", components["conversation_state"])
    return breakdown


def _empty_fallback_breakdown(
    *,
    model: str,
    request_id: str | None,
    customer_id: str | None,
    page: str | None,
) -> dict[str, Any]:
    """Return a valid zero report if even fallback counting unexpectedly fails."""
    return {
        "model": model,
        "request_id": request_id,
        "customer_id": customer_id,
        "page": page,
        "input_tokens_total_estimated": 0,
        "output_tokens_estimated": 0,
        "tokenizer": "approx_chars_div_4:failed",
        "components": dict.fromkeys(COMPONENT_NAMES, 0),
        "uncategorized_labels": ["token_counting_failed"],
    }


def categorize_message(
    *,
    role: str,
    content: str,
    current_user_message: str,
    current_message_counted: bool,
) -> str:
    """Map one assembled message to a stable budget category."""
    if role == "system":
        return "system_prompt"
    if role == "developer":
        return "developer_prompt"
    if (
        role == "user"
        and not current_message_counted
        and content == current_user_message
    ):
        return "current_user_message"
    normalized = content.casefold()
    if content.startswith("Compact conversation context"):
        return "conversation_state"
    if content.startswith("Read-only account tool result"):
        return "tool_results"
    if "refund policy" in normalized and (
        content.startswith("Policy") or content.startswith("Refund policy")
    ):
        return "policy_context"
    if content.startswith("Backend-resolved purchase context"):
        return "purchase_context"
    if content.startswith("Current page reference"):
        return "purchase_context"
    if content.startswith("Customer context"):
        return "customer_context"
    if content.startswith("Workflow context"):
        return "workflow_state"
    if role in {"assistant", "tool"}:
        return "conversation_history"
    return "other_messages"


def log_token_budget_breakdown(breakdown: dict[str, Any]) -> None:
    """Emit one structured log and one readable console breakdown."""
    components = breakdown["components"]
    compact = ", ".join(
        f"{name}={count}" for name, count in components.items() if count
    )
    logger.info(
        "ai.chat.token_budget %s",
        json.dumps(breakdown, sort_keys=True),
        extra={
            "event": {
                "type": "model.token_budget",
                "data": breakdown,
            }
        },
    )
    lines = [
        "AI model token budget",
        (
            f"model={breakdown['model']}, request={breakdown['request_id']}, "
            f"input={breakdown['input_tokens_total_estimated']}, "
            f"output={breakdown['output_tokens_estimated']}, "
            f"tokenizer={breakdown['tokenizer']}"
        ),
        f"components: {compact or 'none'}",
    ]
    labels = breakdown.get("uncategorized_labels") or []
    if labels:
        lines.append(f"uncategorized: {', '.join(labels)}")
    console_logger.info("\n".join(lines))


def stable_text(value: Any) -> str:
    try:
        return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)
