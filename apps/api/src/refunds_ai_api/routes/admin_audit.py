"""Admin model audit read endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse

from refunds_ai_api.config import get_settings
from refunds_ai_api.repositories.application import RepositoryConfigurationError
from refunds_ai_api.repositories.audit import (
    AuditSessionNotFoundError,
    ModelAuditRepository,
    PsycopgAuditConnectionProvider,
)
from refunds_ai_api.schemas.audit import ModelAuditEventRead, ModelAuditSessionRead
from refunds_ai_api.schemas.responses import ApiResponse
from refunds_ai_api.services.model_audit import ModelAuditReadService

router = APIRouter(prefix="/api/admin/audit", tags=["admin-audit"])


def response_meta() -> dict[str, str]:
    """Return standard response metadata."""
    return {"timestamp": datetime.now(UTC).isoformat()}


def get_model_audit_service() -> ModelAuditReadService:
    """Build the model audit read service from backend database settings."""
    repository = ModelAuditRepository(PsycopgAuditConnectionProvider(get_settings()))
    return ModelAuditReadService(repository)


@router.get("/sessions", response_model=ApiResponse)
def list_audit_sessions(
    service: Annotated[ModelAuditReadService, Depends(get_model_audit_service)],
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse:
    """Return recent model audit sessions."""
    try:
        sessions = [
            ModelAuditSessionRead.model_validate(session).model_dump(mode="json")
            for session in service.list_sessions(limit=limit)
        ]
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(
        success=True,
        data={"sessions": sessions},
        error=None,
        meta=response_meta(),
    )


@router.get("/sessions/{session_id}", response_model=ApiResponse)
def get_audit_session(
    session_id: UUID,
    service: Annotated[ModelAuditReadService, Depends(get_model_audit_service)],
    response: Response,
) -> ApiResponse:
    """Return one model audit session summary."""
    try:
        session = ModelAuditSessionRead.model_validate(
            service.get_session(session_id)
        ).model_dump(mode="json")
    except AuditSessionNotFoundError as exc:
        return not_found_response(response, "AUDIT_SESSION_NOT_FOUND", str(exc))
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(
        success=True,
        data={"session": session},
        error=None,
        meta=response_meta(),
    )


@router.get("/sessions/{session_id}/events", response_model=ApiResponse)
def list_audit_session_events(
    session_id: UUID,
    service: Annotated[ModelAuditReadService, Depends(get_model_audit_service)],
    response: Response,
) -> ApiResponse:
    """Return ordered model audit events for one session."""
    try:
        events = [
            ModelAuditEventRead.model_validate(event).model_dump(mode="json")
            for event in service.list_events(session_id)
        ]
    except AuditSessionNotFoundError as exc:
        return not_found_response(response, "AUDIT_SESSION_NOT_FOUND", str(exc))
    except RepositoryConfigurationError as exc:
        return service_unavailable_response(response, "DATABASE_NOT_CONFIGURED", str(exc))

    return ApiResponse(
        success=True,
        data={"events": events},
        error=None,
        meta=response_meta(),
    )


@router.get("/events/stream")
def stream_audit_events(
    service: Annotated[ModelAuditReadService, Depends(get_model_audit_service)],
    session_id: UUID | None = None,
) -> StreamingResponse:
    """Stream database-broadcast model audit events as SSE frames."""
    return StreamingResponse(
        service.stream_events(session_id=session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def not_found_response(response: Response, code: str, message: str) -> ApiResponse:
    """Return a standardized not-found API response."""
    response.status_code = status.HTTP_404_NOT_FOUND
    return ApiResponse(
        success=False,
        data=None,
        error={"code": code, "message": message},
        meta=response_meta(),
    )


def service_unavailable_response(response: Response, code: str, message: str) -> ApiResponse:
    """Return a standardized service-unavailable API response."""
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ApiResponse(
        success=False,
        data=None,
        error={"code": code, "message": message},
        meta=response_meta(),
    )
