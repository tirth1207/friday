"""Intent-driven OSIRIS intelligence routing for FRIDAY.

The router selects a small, deterministic set of read-only OSIRIS feeds from a
user's intelligence topic. It never performs arbitrary URL requests and never
calls the AI analysis, recon, scanner, or other active capabilities.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from tools.osiris.osiris_tools import osiris_intelligence


_TOPIC_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "news": ("news", "live_news"),
    "weather": ("weather", "air_quality", "radar"),
    "war": ("conflicts", "frontlines", "gdelt", "news"),
    "conflict": ("conflicts", "frontlines", "gdelt", "news"),
    "geopolitics": ("conflicts", "country_risk", "gdelt", "news"),
    "satellite": ("satellites", "space_weather"),
    "space": ("satellites", "space_weather"),
    "aviation": ("flights", "weather"),
    "flight": ("flights", "weather"),
    "earthquake": ("earthquakes", "gdelt"),
    "earthquakes": ("earthquakes", "gdelt"),
    "fire": ("fires", "weather"),
    "wildfire": ("fires", "weather"),
    "markets": ("markets", "news"),
    "market": ("markets", "news"),
    "crypto": ("crypto", "news"),
    "cyber": ("cyber_threats", "cyber_attacks", "news"),
    "infrastructure": ("infrastructure", "gdelt", "news"),
    "maritime": ("maritime", "news"),
    "ship": ("maritime", "news"),
    "global": ("gdelt", "news", "conflicts", "weather"),
    "world": ("gdelt", "news", "conflicts", "weather"),
}

_WORD_RE = re.compile(r"[a-z0-9_]+")


def _normalise_topic(topic: str) -> str:
    return " ".join((topic or "").lower().strip().split())


def _select_endpoints(topic: str, max_sources: int = 4) -> tuple[str, ...]:
    normalized = _normalise_topic(topic)
    words = set(_WORD_RE.findall(normalized))
    selected: list[str] = []

    # Exact word matching prevents accidental substring routing such as
    # treating an unrelated word containing "fire" as a wildfire request.
    for key, endpoints in _TOPIC_ENDPOINTS.items():
        if key in words or key.replace("_", " ") in normalized:
            for endpoint in endpoints:
                if endpoint not in selected:
                    selected.append(endpoint)
                if len(selected) >= max_sources:
                    return tuple(selected)
    return tuple(selected or ("news",))


async def osiris_intelligence_brief(
    topic: str,
    query: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    max_sources: int = 4,
) -> dict[str, Any]:
    """Gather a bounded multi-feed OSIRIS snapshot for an intelligence topic."""
    source_limit = max(1, min(int(max_sources or 4), 5))
    endpoints = _select_endpoints(topic, source_limit)

    async def fetch(endpoint: str) -> tuple[str, Any]:
        try:
            result = await osiris_intelligence(
                endpoint=endpoint,
                query=query,
                latitude=latitude,
                longitude=longitude,
            )
            return endpoint, {"ok": True, "result": result}
        except Exception as error:
            return endpoint, {"ok": False, "error": str(error)}

    pairs = await asyncio.gather(*(fetch(endpoint) for endpoint in endpoints))
    sources = {endpoint: payload for endpoint, payload in pairs}
    successful = [name for name, payload in pairs if payload.get("ok")]

    return {
        "topic": topic,
        "query": query,
        "selected_endpoints": list(endpoints),
        "successful_sources": successful,
        "source_count": len(successful),
        "sources": sources,
        "interpretation_policy": "Treat OSIRIS as source data; distinguish reported observations from FRIDAY inference and avoid presenting machine-assessment scores as verified forecasts.",
    }
