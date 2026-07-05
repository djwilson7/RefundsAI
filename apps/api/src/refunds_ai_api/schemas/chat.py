"""Request and response models for the AI chat infrastructure seam."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ChatMessageCreate(BaseModel):
    """Frontend chat message submitted to the phase-one AI seam."""

    model_config = ConfigDict(extra="forbid")

    message: str | None = None
    customer_id: str | None = None
    purchase_id: str | None = None


class ChatMessageRead(BaseModel):
    """Assistant chat message returned to the frontend."""

    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class ChatResponseRead(BaseModel):
    """Static phase-one chat response payload."""

    model_config = ConfigDict(extra="forbid")

    message: ChatMessageRead
    model: str
    graph_ready: bool
