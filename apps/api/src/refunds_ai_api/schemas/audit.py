"""Response schemas for admin model audit APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ModelAuditSessionRead(BaseModel):
    """Admin-facing summary for one audited model request."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    trace_id: UUID
    conversation_id: UUID | None = None
    customer_id: UUID | None = None
    request_id: str | None = None
    model_name: str
    status: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None
    event_count: int
    created_at: datetime
    updated_at: datetime


class ModelAuditEventRead(BaseModel):
    """Admin-facing timeline event with normalized lookup metadata."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    session_id: UUID
    trace_id: UUID
    sequence_number: int
    event_key: str
    display_name: str
    category: str
    description: str | None = None
    display_order: int
    workflow_kind: str | None = None
    tool_name: str | None = None
    summary: str | None = None
    input_json: dict[str, Any] | None = None
    output_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
