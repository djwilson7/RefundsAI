from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg
from fastapi.testclient import TestClient

from refunds_ai_api.main import create_app
from refunds_ai_api.repositories.application import RepositoryConfigurationError
from refunds_ai_api.repositories.audit import AuditSessionNotFoundError
from refunds_ai_api.routes.admin_audit import (
    get_model_audit_service,
    get_model_audit_stream_service,
)
from refunds_ai_api.services.audit import ModelAuditEventKey
from refunds_ai_api.services.model_audit import format_sse_event

SESSION_ID = UUID("70000000-0000-4000-8000-000000000001")
TRACE_ID = UUID("71000000-0000-4000-8000-000000000001")
CUSTOMER_ID = UUID("20000000-0000-4000-8000-000000000001")
STARTED_AT = datetime(2026, 7, 7, 14, 0, tzinfo=UTC)
COMPLETED_AT = datetime(2026, 7, 7, 14, 0, 1, tzinfo=UTC)


def session_row() -> dict[str, Any]:
    return {
        "id": SESSION_ID,
        "trace_id": TRACE_ID,
        "conversation_id": None,
        "customer_id": CUSTOMER_ID,
        "request_id": "req-123",
        "model_name": "gpt-5.4-mini",
        "status": "succeeded",
        "prompt_tokens": 10,
        "completion_tokens": 13,
        "total_tokens": 23,
        "started_at": STARTED_AT,
        "completed_at": COMPLETED_AT,
        "latency_ms": 1000,
        "event_count": 2,
        "created_at": STARTED_AT,
        "updated_at": COMPLETED_AT,
    }


def event_row() -> dict[str, Any]:
    return {
        "id": UUID("73000000-0000-4000-8000-000000000001"),
        "session_id": SESSION_ID,
        "trace_id": TRACE_ID,
        "sequence_number": 1,
        "event_key": ModelAuditEventKey.REQUEST_RECEIVED,
        "display_name": "Request received",
        "category": "request",
        "description": "The chat request was accepted.",
        "display_order": 10,
        "workflow_kind": None,
        "tool_name": None,
        "summary": "Request accepted.",
        "input_json": {"message_length": 19},
        "output_json": None,
        "metadata_json": {"trace_event_type": "message.received"},
        "created_at": STARTED_AT,
    }


class StubModelAuditService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.limit: int | None = None
        self.offset = 0
        self.session_requests: list[UUID] = []
        self.event_requests: list[UUID] = []

    def list_sessions(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if self.error:
            raise self.error
        self.limit = limit
        self.offset = offset
        return [session_row()]

    def get_session(self, session_id: UUID) -> dict[str, Any]:
        if self.error:
            raise self.error
        self.session_requests.append(session_id)
        return session_row()

    def list_events(self, session_id: UUID) -> list[dict[str, Any]]:
        if self.error:
            raise self.error
        self.event_requests.append(session_id)
        return [event_row()]

    def stream_events(self, *, session_id: UUID | None = None):
        yield format_sse_event(
            {
                "id": str(event_row()["id"]),
                "session_id": str(session_id or SESSION_ID),
                "trace_id": str(TRACE_ID),
                "sequence_number": 1,
                "event_key": ModelAuditEventKey.REQUEST_RECEIVED,
            }
        )


def build_client(service: StubModelAuditService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_model_audit_service] = lambda: service
    app.dependency_overrides[get_model_audit_stream_service] = lambda: service
    return TestClient(app)


def test_list_audit_sessions_returns_recent_sessions() -> None:
    service = StubModelAuditService()
    client = build_client(service)

    response = client.get("/api/admin/audit/sessions?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert service.limit == 10
    assert service.offset == 0
    assert body["data"]["sessions"][0]["id"] == str(SESSION_ID)
    assert body["data"]["sessions"][0]["event_count"] == 2
    assert body["data"]["sessions"][0]["total_tokens"] == 23
    assert body["error"] is None
    assert "timestamp" in body["meta"]


def test_list_audit_sessions_accepts_offset() -> None:
    service = StubModelAuditService()
    client = build_client(service)

    response = client.get("/api/admin/audit/sessions?limit=10&offset=20")

    assert response.status_code == 200
    assert service.limit == 10
    assert service.offset == 20


def test_list_audit_sessions_without_limit_returns_all_sessions() -> None:
    service = StubModelAuditService()
    client = build_client(service)

    response = client.get("/api/admin/audit/sessions")

    assert response.status_code == 200
    assert service.limit is None
    assert response.json()["data"]["sessions"][0]["id"] == str(SESSION_ID)


def test_get_audit_session_returns_one_session() -> None:
    service = StubModelAuditService()
    client = build_client(service)

    response = client.get(f"/api/admin/audit/sessions/{SESSION_ID}")

    assert response.status_code == 200
    assert service.session_requests == [SESSION_ID]
    body = response.json()
    assert body["data"]["session"]["trace_id"] == str(TRACE_ID)
    assert body["data"]["session"]["customer_id"] == str(CUSTOMER_ID)


def test_list_audit_session_events_returns_ordered_events() -> None:
    service = StubModelAuditService()
    client = build_client(service)

    response = client.get(f"/api/admin/audit/sessions/{SESSION_ID}/events")

    assert response.status_code == 200
    assert service.event_requests == [SESSION_ID]
    event = response.json()["data"]["events"][0]
    assert event["event_key"] == ModelAuditEventKey.REQUEST_RECEIVED
    assert event["display_name"] == "Request received"
    assert event["category"] == "request"
    assert event["input_json"] == {"message_length": 19}


def test_stream_audit_events_returns_sse_frames() -> None:
    client = build_client(StubModelAuditService())

    response = client.get(f"/api/admin/audit/events/stream?session_id={SESSION_ID}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: model_audit_event" in response.text
    assert f'"session_id": "{SESSION_ID}"' in response.text
    assert '"event_key": "REQUEST_RECEIVED"' in response.text


def test_format_sse_event_returns_keepalive_comment() -> None:
    assert format_sse_event({"type": "keepalive"}) == ": keepalive\n\n"


def test_get_audit_session_returns_not_found() -> None:
    client = build_client(
        StubModelAuditService(error=AuditSessionNotFoundError("Model audit session was not found."))
    )

    response = client.get(f"/api/admin/audit/sessions/{SESSION_ID}")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "AUDIT_SESSION_NOT_FOUND",
        "message": "Model audit session was not found.",
    }


def test_list_audit_sessions_returns_database_configuration_error() -> None:
    client = build_client(
        StubModelAuditService(
            error=RepositoryConfigurationError("SUPABASE_DB_URL is not configured.")
        )
    )

    response = client.get("/api/admin/audit/sessions")

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "DATABASE_NOT_CONFIGURED",
        "message": "SUPABASE_DB_URL is not configured.",
    }


def test_list_audit_sessions_returns_controlled_timeout_error(caplog) -> None:
    client = build_client(
        StubModelAuditService(error=psycopg.errors.ConnectionTimeout("connection timed out"))
    )

    with caplog.at_level("WARNING", logger="refunds_ai_api.audit"):
        response = client.get("/api/admin/audit/sessions")

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"] == {
        "code": "audit_store_unavailable",
        "message": "Audit logs are temporarily unavailable.",
    }
    assert caplog.records[0].event["type"] == "audit.store_unavailable"
