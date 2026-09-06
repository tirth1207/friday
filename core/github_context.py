"""Persistent active GitHub repository context used by chat and the UI."""

from __future__ import annotations

from typing import Any

from core.memory.memory import memory_store

GITHUB_REPOSITORY_CONTEXT_KEY = "active_github_repository"


def get_active_repository() -> str | None:
    value = memory_store.get_preference(GITHUB_REPOSITORY_CONTEXT_KEY)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def set_active_repository(repository: str | None) -> str | None:
    normalized = (repository or "").strip()
    if normalized:
        memory_store.set_preference(GITHUB_REPOSITORY_CONTEXT_KEY, normalized)
        return normalized
    clear_active_repository()
    return None


def clear_active_repository() -> None:
    memory_store.set_preference(GITHUB_REPOSITORY_CONTEXT_KEY, "")


def github_context_for_prompt() -> dict[str, Any]:
    repository = get_active_repository()
    return {"repository": repository} if repository else {}
