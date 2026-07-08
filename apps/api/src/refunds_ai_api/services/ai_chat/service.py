"""High-level AI chat service entrypoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from refunds_ai_api.services.application import ApplicationService
from refunds_ai_api.services.audit import ModelAuditSession, ModelAuditWriterService

from .graph import build_chat_graph
from .logging import logger
from .models import AIChatResult, ChatGraphState, ChatModelClient
from .nodes import (
    execute_tools_node,
    generate_final_response_node,
    request_tool_call_node,
    validate_context_node,
)
from .responses import CHAT_UNAVAILABLE_RESPONSE
from .state import normalize_conversation_state, normalize_page_context


@dataclass(frozen=True)
class AIChatService:
    """Run read-only purchase-history chat through a LangGraph workflow."""

    application_service: ApplicationService
    model: str
    model_client: ChatModelClient | None
    audit_writer: ModelAuditWriterService | None = None

    def create_response(
        self,
        *,
        message: str,
        customer_id: str | None,
        purchase_id: str | None,
        page_context: dict[str, Any] | None = None,
        conversation_state: dict[str, Any] | None = None,
        trace_step_start: int = 1,
        audit_session: ModelAuditSession | None = None,
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
                    "audit_session": audit_session,
                    "audit_writer": self.audit_writer,
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
            err_conv_state = normalize_conversation_state(conversation_state)
            err_conv_state["_turn_processed"] = True
            return AIChatResult(
                content=CHAT_UNAVAILABLE_RESPONSE,
                graph_ready=self.model_client is not None,
                conversation_state=err_conv_state,
                side_effects=[],
                next_trace_step=trace_step_start,
                audit_failed=True,
            )

        final_conv_state = state.get("conversation_state") or normalize_conversation_state(conversation_state)
        final_conv_state["_turn_processed"] = True

        return AIChatResult(
            content=state.get("assistant_response") or CHAT_UNAVAILABLE_RESPONSE,
            graph_ready=self.model_client is not None,
            conversation_state=final_conv_state,
            side_effects=[
                side_effect
                for side_effect in state.get("side_effects", [])
                if isinstance(side_effect, dict)
            ],
            next_trace_step=int(state.get("trace_step", trace_step_start)),
            token_usage=state.get("audit_token_usage"),
            audit_failed=state.get("error")
            in {
                "missing_openai_api_key",
                "model_request_failed",
                "final_model_request_failed",
            },
        )

    def _build_graph(self):
        """Build the LangGraph workflow for this service instance."""
        return build_chat_graph(self)

    def _validate_context(self, state: ChatGraphState) -> ChatGraphState:
        """Compatibility wrapper for the context-validation graph node."""
        return validate_context_node(self, state)

    def _request_tool_call(self, state: ChatGraphState) -> ChatGraphState:
        """Compatibility wrapper for the tool-selection graph node."""
        return request_tool_call_node(self, state)

    def _execute_tools(self, state: ChatGraphState) -> ChatGraphState:
        """Compatibility wrapper for the tool-execution graph node."""
        return execute_tools_node(self, state)

    def _generate_final_response(self, state: ChatGraphState) -> ChatGraphState:
        """Compatibility wrapper for the final-response graph node."""
        return generate_final_response_node(self, state)
