"""Explicit user preference memory tools for FRIDAY."""

from __future__ import annotations

from typing import Any

from langchain.tools import tool

from core.memory.memory import memory_store


@tool("memory_remember")
async def remember(category: str, fact: str, source_message: str = "") -> dict[str, Any]:
    """Persist an explicitly stated user preference or behavior fact."""
    return memory_store.remember_profile(category, fact, source_message)


@tool("memory_recall")
async def recall(query: str = "", limit: int = 8) -> list[dict[str, Any]]:
    """Recall relevant saved user preferences and behavior facts."""
    return memory_store.recall_profile(query, limit)


MEMORY_LANGCHAIN_TOOLS = [remember, recall]
