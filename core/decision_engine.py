"""FRIDAY's dependency-free decision layer.

JEV is intentionally not required. This module provides the small internal
decision contract FRIDAY needs today while keeping the interface replaceable
by a richer decision engine later.
"""

from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Decision(BaseModel):
    action: str
    allowed: bool
    requires_confirmation: bool
    risk: RiskLevel
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class DecisionEngine:
    """Conservative policy engine for agent/tool actions."""

    _SAFE = {"read", "search", "inspect", "status", "test", "research", "notify"}
    _CONFIRM = {"write", "create", "modify", "commit", "push", "send", "deploy"}
    _DANGEROUS = {"delete", "format", "shutdown", "credential", "secret"}

    def decide(self, action: str, *, approved: bool = False) -> Decision:
        normalized = (action or "").strip().lower()
        if normalized in self._SAFE:
            return Decision(
                action=normalized, allowed=True, requires_confirmation=False,
                risk=RiskLevel.SAFE, reason="Read-only or non-destructive action.",
                confidence=0.98,
            )
        if normalized in self._DANGEROUS:
            return Decision(
                action=normalized, allowed=approved, requires_confirmation=True,
                risk=RiskLevel.HIGH,
                reason="Potentially destructive or security-sensitive action requires explicit approval.",
                confidence=0.99,
            )
        if normalized in self._CONFIRM:
            return Decision(
                action=normalized, allowed=approved, requires_confirmation=True,
                risk=RiskLevel.MEDIUM,
                reason="Mutation or external side effect requires explicit approval.",
                confidence=0.96,
            )
        return Decision(
            action=normalized or "unknown",
            allowed=False,
            requires_confirmation=True,
            risk=RiskLevel.MEDIUM,
            reason="Unknown actions are denied until a policy is defined.",
            confidence=0.90,
        )


decision_engine = DecisionEngine()
