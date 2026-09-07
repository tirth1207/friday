"""Read-only OSIRIS intelligence tools for FRIDAY."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlencode

import aiohttp

OSIRIS_BASE_URL = "https://osirisai.live"
OSIRIS_TIMEOUT_SECONDS = 15
_MAX_RESPONSE_BYTES = 2_000_000

_ENDPOINTS = {
    "health": "/api/health", "stats": "/api/stats", "flights": "/api/flights", "satellites": "/api/satellites",
    "space_weather": "/api/space-weather", "earthquakes": "/api/earthquakes", "fires": "/api/fires",
    "weather": "/api/weather", "air_quality": "/api/air-quality", "radar": "/api/radar", "sentinel": "/api/sentinel",
    "conflicts": "/api/conflicts", "frontlines": "/api/frontlines", "gdelt": "/api/gdelt", "country_risk": "/api/country-risk",
    "region_dossier": "/api/region-dossier", "news": "/api/news", "live_news": "/api/live-news", "markets": "/api/markets",
    "crypto": "/api/crypto", "maritime": "/api/maritime", "infrastructure": "/api/infrastructure",
    "cyber_threats": "/api/cyber-threats", "cyber_attacks": "/api/cyber-attacks",
}


def osiris_endpoint_catalog() -> dict[str, str]:
    """Return a copy of the allow-listed logical endpoint catalog."""
    return dict(_ENDPOINTS)


def _validate_endpoint(endpoint: str) -> str:
    path = _ENDPOINTS.get(endpoint)
    if path is None:
        raise ValueError(f"Unsupported OSIRIS endpoint: {endpoint}")
    return path


async def _request(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    path = _validate_endpoint(endpoint)
    query = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    url = f"{OSIRIS_BASE_URL}{path}"
    if query:
        url = f"{url}?{urlencode(query, doseq=True)}"
    timeout = aiohttp.ClientTimeout(total=OSIRIS_TIMEOUT_SECONDS)
    headers = {"Accept": "application/json", "User-Agent": "FRIDAY/1.0"}
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as response:
                if response.content_length and response.content_length > _MAX_RESPONSE_BYTES:
                    raise RuntimeError(f"OSIRIS response too large: {response.content_length} bytes")
                raw = await response.content.read(_MAX_RESPONSE_BYTES + 1)
                if len(raw) > _MAX_RESPONSE_BYTES:
                    raise RuntimeError("OSIRIS response exceeded the safety size limit")
                if response.status >= 400:
                    detail = raw.decode("utf-8", errors="replace")[:1000]
                    raise RuntimeError(f"OSIRIS returned HTTP {response.status}: {detail}")
                try:
                    data = await response.json(content_type=None)
                except Exception as error:
                    raise RuntimeError(f"OSIRIS returned non-JSON content: {error}") from error
    except asyncio.TimeoutError as error:
        raise RuntimeError(f"OSIRIS request timed out after {OSIRIS_TIMEOUT_SECONDS}s") from error
    except aiohttp.ClientError as error:
        raise RuntimeError(f"OSIRIS request failed: {error}") from error
    return {"source": "OSIRIS Intelligence", "endpoint": path, "url": url, "data": data}


async def osiris_intelligence(endpoint: str, query: str = "", latitude: float | None = None, longitude: float | None = None, radius_km: float | None = None) -> dict[str, Any]:
    """Call one allow-listed OSIRIS read endpoint."""
    params: dict[str, Any] = {}
    if query: params["q"] = query
    if latitude is not None: params["lat"] = latitude
    if longitude is not None: params["lon"] = longitude
    if radius_km is not None: params["radius_km"] = radius_km
    return await _request(endpoint, params)


async def osiris_health() -> dict[str, Any]: return await _request("health")
async def osiris_stats() -> dict[str, Any]: return await _request("stats")
async def osiris_news(query: str = "") -> dict[str, Any]: return await _request("news", {"q": query} if query else None)
async def osiris_live_news(query: str = "") -> dict[str, Any]: return await _request("live_news", {"q": query} if query else None)
async def osiris_weather() -> dict[str, Any]: return await _request("weather")
async def osiris_air_quality() -> dict[str, Any]: return await _request("air_quality")
async def osiris_radar() -> dict[str, Any]: return await _request("radar")
async def osiris_conflicts() -> dict[str, Any]: return await _request("conflicts")
async def osiris_frontlines() -> dict[str, Any]: return await _request("frontlines")
async def osiris_satellites() -> dict[str, Any]: return await _request("satellites")
async def osiris_flights() -> dict[str, Any]: return await _request("flights")
async def osiris_earthquakes() -> dict[str, Any]: return await _request("earthquakes")
async def osiris_fires() -> dict[str, Any]: return await _request("fires")
async def osiris_space_weather() -> dict[str, Any]: return await _request("space_weather")
async def osiris_gdelt() -> dict[str, Any]: return await _request("gdelt")
async def osiris_country_risk() -> dict[str, Any]: return await _request("country_risk")
async def osiris_markets() -> dict[str, Any]: return await _request("markets")
async def osiris_crypto() -> dict[str, Any]: return await _request("crypto")
async def osiris_maritime() -> dict[str, Any]: return await _request("maritime")
async def osiris_infrastructure() -> dict[str, Any]: return await _request("infrastructure")
async def osiris_cyber_threats() -> dict[str, Any]: return await _request("cyber_threats")
async def osiris_cyber_attacks() -> dict[str, Any]: return await _request("cyber_attacks")
async def osiris_region_dossier(latitude: float, longitude: float) -> dict[str, Any]: return await _request("region_dossier", {"lat": latitude, "lon": longitude})
