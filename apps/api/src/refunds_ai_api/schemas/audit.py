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
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None
    event_count: int
    total_model_calls: int = 0
    total_tool_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_reasoning_tokens: int = 0
    total_model_latency_ms: int = 0
    total_tool_latency_ms: int = 0
    total_workflow_latency_ms: int | None = None
    total_workflow_steps: int = 0
    backend_read_count: int = 0
    backend_validation_count: int = 0
    backend_verification_count: int = 0
    backend_mutation_count: int = 0
    external_api_call_count: int = 0
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
    model_call_id: str | None = None
    phase: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    status: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    tool_call_id: str | None = None
    source: str | None = None
    operation: str | None = None
    backend_category: str | None = None
    available_tools_count: int | None = None
    tool_results_provided: int | None = None
    conversation_state_summary: dict[str, Any] | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    customer_id: str | None = None
    purchase_id: str | None = None
    created_at: datetime
