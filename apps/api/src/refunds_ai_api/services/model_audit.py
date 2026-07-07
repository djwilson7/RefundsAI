"""Read service for model audit sessions and events."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class ModelAuditReadRepositoryProtocol(Protocol):
    """Repository operations required by admin audit read APIs."""

    def list_sessions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent audit sessions."""
        ...

    def get_session(self, session_id: UUID) -> dict[str, Any]:
        """Return one audit session."""
        ...

    def list_events(self, session_id: UUID) -> list[dict[str, Any]]:
        """Return ordered audit events for one session."""
        ...

    def listen_events(
        self,
        *,
        session_id: UUID | None = None,
        timeout_seconds: int = 15,
    ) -> Iterator[dict[str, Any]]:
        """Yield realtime audit event notifications."""
        ...


@dataclass(frozen=True)
class ModelAuditReadService:
    """Coordinate read-only admin access to model audit data."""

    repository: ModelAuditReadRepositoryProtocol

    def list_sessions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent audit sessions."""
        return self.repository.list_sessions(limit=limit)

    def get_session(self, session_id: UUID) -> dict[str, Any]:
        """Return one audit session."""
        return self.repository.get_session(session_id)

    def list_events(self, session_id: UUID) -> list[dict[str, Any]]:
        """Return ordered events after confirming the session exists."""
        self.repository.get_session(session_id)
        return self.repository.list_events(session_id)

    def stream_events(self, *, session_id: UUID | None = None) -> Iterator[str]:
        """Yield server-sent event frames for database-broadcast audit events."""
        for event in self.repository.listen_events(session_id=session_id):
            yield format_sse_event(event)


def format_sse_event(event: dict[str, Any]) -> str:
    """Format one audit notification as a server-sent event frame."""
    if event.get("type") == "keepalive":
        return ": keepalive\n\n"
    payload = json.dumps(event, default=str, sort_keys=True)
    return f"event: model_audit_event\ndata: {payload}\n\n"
