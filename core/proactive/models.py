from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AttentionLevel(StrEnum):
    QUIET = "quiet"
    DIGEST = "digest"
    NOTIFY = "notify"
    URGENT = "urgent"


class ProactiveSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    kind: str
    title: str
    summary: str
    importance: float = Field(default=0.0, ge=0.0, le=1.0)
    urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    dedupe_key: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AttentionDecision(BaseModel):
    signal_id: str
    level: AttentionLevel
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    should_deliver: bool = False
    should_queue: bool = False


class ProactiveMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    message: str
    level: AttentionLevel
    signal_id: str
    source: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    delivered: bool = False
