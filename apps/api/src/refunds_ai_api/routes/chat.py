"""AI chat endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response, status

from refunds_ai_api.config import Settings, get_settings
from refunds_ai_api.repositories.application import ApplicationRepository, PsycopgConnectionProvider
from refunds_ai_api.schemas.chat import ChatMessageCreate, ChatResponseRead
from refunds_ai_api.schemas.responses import ApiResponse
from refunds_ai_api.services.ai_chat import (
    AIChatService,
    OpenAIChatCompletionsModelClient,
    log_trace_step,
)
from refunds_ai_api.services.application import ApplicationService

router = APIRouter(prefix="/api", tags=["chat"])


def response_meta() -> dict[str, str]:
    """Return standard response metadata."""
    return {"timestamp": datetime.now(UTC).isoformat()}


def get_ai_chat_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AIChatService:
    """Build the AI chat service with backend-owned read-only tools."""
    connection_provider = PsycopgConnectionProvider(settings)
    repository = ApplicationRepository(connection_provider)
    application_service = ApplicationService(repository)
    model_client = (
        OpenAIChatCompletionsModelClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        if settings.openai_api_key
        else None
    )

    return AIChatService(
        application_service=application_service,
        model=settings.openai_model,
        model_client=model_client,
    )


@router.post("/chat", response_model=ApiResponse)
def create_chat_message(
    payload: Annotated[ChatMessageCreate, Body()],
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    chat_service: Annotated[AIChatService, Depends(get_ai_chat_service)],
) -> ApiResponse:
    """Run read-only purchase-history chat through the AI graph."""
    message = payload.message.strip() if payload.message else ""

    if not message:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ApiResponse(
            success=False,
            data=None,
            error={
                "code": "INVALID_CHAT_MESSAGE",
                "message": "Chat message must not be empty.",
            },
            meta=response_meta(),
        )

    trace_state = log_trace_step(
        {"trace_step": 1},
        message="FastAPI chat route received validated customer message.",
        event_type="message.received",
        data={
            "message": message,
            "message_length": len(message),
            "customer_id": payload.customer_id,
            "purchase_id": payload.purchase_id,
            "page_context": payload.page_context,
            "conversation_state": payload.conversation_state,
        },
    )

    ai_response = chat_service.create_response(
        message=message,
        customer_id=payload.customer_id,
        purchase_id=payload.purchase_id,
        page_context=payload.page_context,
        conversation_state=payload.conversation_state,
        trace_step_start=trace_state["trace_step"],
    )
    chat_response = ChatResponseRead(
        message={"role": "assistant", "content": ai_response.content},
        model=settings.openai_model,
        graph_ready=ai_response.graph_ready,
        conversation_state=ai_response.conversation_state,
    )

    log_trace_step(
        {"trace_step": ai_response.next_trace_step},
        message="FastAPI chat route returning assistant response payload.",
        event_type="route.response_returned",
        data={
            "model": settings.openai_model,
            "graph_ready": ai_response.graph_ready,
            "response": chat_response.model_dump(mode="json"),
        },
    )

    return ApiResponse(
        success=True,
        data=chat_response.model_dump(mode="json"),
        error=None,
        meta=response_meta(),
    )
