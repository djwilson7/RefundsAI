"""AI chat infrastructure endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response, status

from refunds_ai_api.config import Settings, get_settings
from refunds_ai_api.schemas.chat import ChatMessageCreate, ChatResponseRead
from refunds_ai_api.schemas.responses import ApiResponse

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger("refunds_ai_api.chat")

PLACEHOLDER_RESPONSE = (
    "I can help answer questions about your purchases. The AI workflow "
    "infrastructure is connected, and LangGraph orchestration will be enabled "
    "in a later phase."
)


def response_meta() -> dict[str, str]:
    """Return standard response metadata."""
    return {"timestamp": datetime.now(UTC).isoformat()}


@router.post("/chat", response_model=ApiResponse)
def create_chat_message(
    payload: Annotated[ChatMessageCreate, Body()],
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiResponse:
    """Return a static phase-one assistant response without invoking a model."""
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

    logger.info(
        "ai.chat.message_received",
        extra={
            "event": {
                "type": "message.received",
                "message_length": len(message),
                "customer_id": payload.customer_id,
                "purchase_id": payload.purchase_id,
            }
        },
    )

    chat_response = ChatResponseRead(
        message={"role": "assistant", "content": PLACEHOLDER_RESPONSE},
        model=settings.openai_model,
        graph_ready=False,
    )

    logger.info(
        "ai.chat.response_generated",
        extra={
            "event": {
                "type": "response.generated",
                "model": settings.openai_model,
                "graph_ready": False,
            }
        },
    )

    return ApiResponse(
        success=True,
        data=chat_response.model_dump(mode="json"),
        error=None,
        meta=response_meta(),
    )
