"""Intent-driven OSIRIS intelligence routing for FRIDAY.

The router selects a small, deterministic set of read-only OSIRIS feeds from a
user's intelligence topic. It never performs arbitrary URL requests and never
calls the AI analysis/recon/scanner endpoints.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tools.osiris.osiris_tools import osiris_intelligence


_TOPIC_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "news": ("news", "live_news"),
    "weather": ("weather", "air_quality"),
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
    "cyber": ("cyber_threats", "cyber_attacks", "news"),
    "infrastructure": ("infrastructure", "gdelt", "news"),
    "maritime": ("maritime", "news"),
    "global": ("gdelt", "news", "conflicts", "weather"),
    "world": ("gdelt", "news", "conflicts", "weather"),
}


def _normalise_topic(topic: str) -> str:
    return " ".join((topic or "").lower().strip().split())


def _select_endpoints(topic: str) -> tuple[str, ...]:
    normalized = _normalise_topic(topic)
    for key, endpoints in _TOPIC_ENDPOINTS.items():
        if key in normalized:
            return endpoints
    return ("news",)


async def osiris_intelligence_brief(
    topic: str,
    query: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    max_sources: int = 4,
) -> dict[str, Any]:
    """Gather a bounded multi-feed OSIRIS snapshot for an intelligence topic.

    Use this when a user asks for a broad situation rather than one specific
    feed. For a narrow request, prefer the individual osiris.* tools instead.
    """
    endpoints = _select_endpoints(topic)[: max(1, min(int(max_sources or 4), 5))]

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
