"""GitHub repository selection helpers for the FRIDAY UI and chat context."""

from __future__ import annotations

from typing import Any

from tools.github.repository_agent import _accessible_repositories


async def list_selectable_repositories(limit: int = 100) -> list[dict[str, Any]]:
    """Return a compact, stable repository list for the frontend selector."""
    repositories = await _accessible_repositories(limit=limit)
    return [
        {
            "name": item.get("name"),
            "full_name": item.get("full_name"),
            "private": bool(item.get("private")),
            "default_branch": item.get("default_branch"),
            "archived": bool(item.get("archived")),
            "description": item.get("description"),
            "language": item.get("language"),
            "updated_at": item.get("updated_at"),
            "pushed_at": item.get("pushed_at"),
            "html_url": item.get("html_url"),
        }
        for item in repositories
        if item.get("full_name") and not item.get("archived")
    ]
