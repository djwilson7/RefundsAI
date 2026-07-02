from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiError(BaseModel):
    """Standard API error payload."""

    code: str
    message: str


class ApiResponse(BaseModel):
    """Standard frontend/backend response envelope."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    data: dict[str, Any] | None
    error: ApiError | None
    meta: dict[str, Any]
