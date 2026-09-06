"""Cognition primitives for FRIDAY: planning, experience learning, recall, and curiosity."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.memory import memory_store


_ALLOWED_KINDS = {"lesson", "decision", "failure", "pattern", "preference"}


def learn_experience(kind: str, title: str, lesson: str, context: str = "") -> dict[str, Any]:
    """Persist a compact, reusable experience without storing secrets or raw credentials."""
    normalized_kind = (kind or "lesson").strip().lower()
    if normalized_kind not in _ALLOWED_KINDS:
        normalized_kind = "lesson"
    payload = {
        "kind": normalized_kind,
        "title": (title or "Untitled experience").strip()[:200],
        "lesson": (lesson or "").strip()[:4000],
        "context": (context or "").strip()[:1500],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    memory_store.add_experience(payload)
    return {"stored": True, "experience": payload}


def recall_experiences(query: str = "", limit: int = 8) -> list[dict[str, Any]]:
    """Recall relevant past experiences using simple lexical matching."""
    return memory_store.search_experiences(query=(query or "").strip(), limit=max(1, min(int(limit or 8), 20)))


def curiosity_probe(goal: str, known: str = "", limit: int = 6) -> dict[str, Any]:
    """Turn uncertainty into concrete, bounded questions FRIDAY can investigate with existing tools."""
    goal_text = (goal or "").strip()
    known_text = (known or "").strip()
    questions = [
        "What evidence is missing to verify the goal is actually complete?",
        "Which assumption, dependency, or integration could invalidate the current plan?",
        "What is the smallest experiment that would reduce the biggest uncertainty?",
        "What edge case is most likely to fail after the main path works?",
        "What existing project pattern should be reused instead of introducing a new abstraction?",
        "What verification signal would prove this change works in the real environment?",
    ]
    if known_text:
        questions.insert(0, "Which part of the known evidence is weakest or contradictory?")
    return {
        "goal": goal_text,
        "known": known_text,
        "questions": questions[: max(1, min(int(limit or 6), 10))],
        "instruction": "Investigate only questions that can materially improve the current task; do not explore endlessly.",
    }


def task_checkpoint(goal: str, completed: list[str] | None = None, remaining: list[str] | None = None) -> dict[str, Any]:
    """Create a durable checkpoint for long-running work."""
    checkpoint = {
        "goal": (goal or "").strip()[:1000],
        "completed": list(completed or [])[:50],
        "remaining": list(remaining or [])[:50],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    memory_store.set_preference("last_task_checkpoint", checkpoint)
    return checkpoint
