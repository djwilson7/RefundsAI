"""OpenAI model connectivity health checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from refunds_ai_api.config import Settings


class ModelConnectionError(RuntimeError):
    """Raised when the configured model cannot be reached."""


@dataclass(frozen=True)
class ModelHealth:
    """OpenAI model health result."""

    provider: str
    configured: bool
    connected: bool
    model: str
    detail: str


class ModelHealthChecker(Protocol):
    """Health checker contract for AI model connectivity."""

    def check(self) -> ModelHealth:
        """Return configured model connectivity state."""
        ...


@dataclass(frozen=True)
class OpenAIModelHealthChecker:
    """Check whether the configured OpenAI model can complete a minimal call."""

    settings: Settings

    def check(self) -> ModelHealth:
        """Return OpenAI model readiness without exposing credentials."""
        if not self.settings.openai_api_key:
            return ModelHealth(
                provider="openai",
                configured=False,
                connected=False,
                model=self.settings.openai_model,
                detail="OPENAI_API_KEY is not configured.",
            )

        try:
            client = OpenAI(api_key=self.settings.openai_api_key)
            client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with ok.",
                    }
                ],
                max_completion_tokens=5,
            )
        except Exception as exc:
            raise ModelConnectionError("OpenAI model handshake failed.") from exc

        return ModelHealth(
            provider="openai",
            configured=True,
            connected=True,
            model=self.settings.openai_model,
            detail="OpenAI model handshake succeeded.",
        )
