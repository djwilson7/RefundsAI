"""Request and response models for AI chat."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ChatMessageCreate(BaseModel):
    """Frontend chat message submitted to the AI chat endpoint."""

    model_config = ConfigDict(extra="forbid")

    message: str | None = None
    customer_id: str | None = None
    purchase_id: str | None = None
    page_context: dict[str, Any] | None = None
    conversation_state: dict[str, Any] | None = None


class ChatMessageRead(BaseModel):
    """Assistant chat message returned to the frontend."""

    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class ChatResponseRead(BaseModel):
    """AI chat response payload."""

    model_config = ConfigDict(extra="forbid")

    message: ChatMessageRead
    model: str
    graph_ready: bool
    conversation_state: dict[str, Any]
