from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


EventType = Literal[
    "thinking",
    "planning",
    "agent_created",
    "agent_started",
    "agent_completed",
    "tool_started",
    "tool_completed",
    "tool_error",
    "verification",
    "message",
    "error",
]


class FridayEvent(BaseModel):
    """
    Safe execution event sent to the FRIDAY frontend.

    This is an execution trace only.
    It must NOT contain private chain-of-thought,
    API keys, passwords, tokens, or other secrets.
    """

    # Automatically generate an ID.
    # This fixes:
    #
    # 1 validation error for FridayEvent
    # id
    # Field required
    #
    id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    type: EventType

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    title: str

    description: str | None = None

    agent: str | None = None

    tool: str | None = None

    status: str | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )