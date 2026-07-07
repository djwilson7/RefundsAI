"""AI chat endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, Response, status

from refunds_ai_api.config import Settings, get_settings
from refunds_ai_api.repositories.application import ApplicationRepository, PsycopgConnectionProvider
from refunds_ai_api.repositories.audit import (
    ModelAuditRepository,
    PsycopgAuditConnectionProvider,
)
from refunds_ai_api.schemas.chat import ChatMessageCreate, ChatResponseRead
from refunds_ai_api.schemas.responses import ApiResponse
from refunds_ai_api.services.ai_chat import (
    AIChatService,
    OpenAIChatCompletionsModelClient,
    log_trace_step,
)
from refunds_ai_api.services.application import ApplicationService
from refunds_ai_api.services.audit import ModelAuditSession, ModelAuditWriterService

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
    audit_repository = ModelAuditRepository(PsycopgAuditConnectionProvider(settings))
    audit_writer = ModelAuditWriterService(audit_repository)
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
        audit_writer=audit_writer,
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

    audit_writer = getattr(chat_service, "audit_writer", None)
    audit_session = start_audit_session(
        audit_writer=audit_writer,
        model_name=settings.openai_model,
        customer_id=payload.customer_id,
    )
    trace_state = log_trace_step(
        {
            "trace_step": 1,
            "audit_session": audit_session,
            "audit_writer": audit_writer,
        },
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
        audit_session=audit_session,
    )
    chat_response = ChatResponseRead(
        message={"role": "assistant", "content": ai_response.content},
        model=settings.openai_model,
        graph_ready=ai_response.graph_ready,
        conversation_state=ai_response.conversation_state,
        side_effects=ai_response.side_effects,
    )

    log_trace_step(
        {
            "trace_step": ai_response.next_trace_step,
            "audit_session": audit_session,
            "audit_writer": audit_writer,
        },
        message="FastAPI chat route returning assistant response payload.",
        event_type="route.response_returned",
        data={
            "model": settings.openai_model,
            "graph_ready": ai_response.graph_ready,
            "response": chat_response.model_dump(mode="json"),
        },
    )
    complete_audit_session(
        audit_writer=audit_writer,
        audit_session=audit_session,
        audit_failed=ai_response.audit_failed,
        token_usage=ai_response.token_usage,
    )

    return ApiResponse(
        success=True,
        data=chat_response.model_dump(mode="json"),
        error=None,
        meta=response_meta(),
    )


def start_audit_session(
    *,
    audit_writer: ModelAuditWriterService | None,
    model_name: str,
    customer_id: str | None,
) -> ModelAuditSession | None:
    """Start an audit session for one chat request when audit writing is configured."""
    if audit_writer is None:
        return None
    try:
        return audit_writer.start_session(
            model_name=model_name,
            customer_id=parse_optional_uuid(customer_id),
            request_id=str(uuid4()),
        )
    except Exception:
        return None


def complete_audit_session(
    *,
    audit_writer: ModelAuditWriterService | None,
    audit_session: ModelAuditSession | None,
    audit_failed: bool,
    token_usage,
) -> None:
    """Finalize the audit session after the route response trace event is persisted."""
    if audit_writer is None or audit_session is None:
        return
    try:
        if audit_failed:
            audit_writer.fail_session(session=audit_session, token_usage=token_usage)
            return
        audit_writer.complete_session(session=audit_session, token_usage=token_usage)
    except Exception:
        return


def parse_optional_uuid(value: str | None) -> UUID | None:
    """Parse UUID request fields for audit metadata without changing route validation."""
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
