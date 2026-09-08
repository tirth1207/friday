"""General-purpose web search for FRIDAY research tasks."""

from __future__ import annotations

import asyncio
from typing import Any

from ddgs import DDGS
from langchain.tools import tool

MAX_RESULTS = 8


def _search_sync(query: str, max_results: int) -> list[dict[str, Any]]:
    with DDGS() as client:
        rows = client.text(query, max_results=max_results)
        return [
            {
                "title": row.get("title"),
                "url": row.get("href") or row.get("url"),
                "snippet": row.get("body") or row.get("snippet"),
            }
            for row in rows
        ]


@tool("web_search")
async def web_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search the public web and return bounded result metadata/snippets."""
    query = query.strip()
    if not query:
        raise ValueError("Search query cannot be empty.")
    max_results = max(1, min(max_results, MAX_RESULTS))
    try:
        return await asyncio.to_thread(_search_sync, query, max_results)
    except Exception as error:
        raise RuntimeError(f"Web search failed: {error}") from error


WEB_SEARCH_TOOL = web_search
