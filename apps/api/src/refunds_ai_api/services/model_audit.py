"""Read service for model audit sessions and events."""

from __future__ import annotations

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
