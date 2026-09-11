"""Read-only OSIRIS live-intelligence tools for FRIDAY.

The OSIRIS public API is an upstream read layer. FRIDAY intentionally keeps
writes, active scanning, ingest, webhooks and AI POST routes outside this tool
surface so live awareness cannot silently become external side effects.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlencode

import aiohttp

OSIRIS_BASE_URL = "https://osirisai.live"
OSIRIS_TIMEOUT_SECONDS = 15
_MAX_RESPONSE_BYTES = 2_000_000

# Public read-only routes documented by OSIRIS' current API catalog.
_ENDPOINTS: dict[str, str] = {
    # System
    "health": "/api/health",
    "stats": "/api/stats",
    # Aviation & space
    "flights": "/api/flights",
    "satellites": "/api/satellites",
    "space_weather": "/api/space-weather",
    # Earth & environment
    "earthquakes": "/api/earthquakes",
    "fires": "/api/fires",
    "weather": "/api/weather",
    "air_quality": "/api/air-quality",
    "radar": "/api/radar",
    "sentinel": "/api/sentinel",
    # Geopolitical
    "conflicts": "/api/conflicts",
    "frontlines": "/api/frontlines",
    "gdelt": "/api/gdelt",
    "country_risk": "/api/country-risk",
    "region_dossier": "/api/region-dossier",
    # Media & markets
    "news": "/api/news",
    "live_news": "/api/live-news",
    "markets": "/api/markets",
    "crypto": "/api/crypto",
    "scm_suppliers": "/api/scm-suppliers",
    # Surveillance & infrastructure (read-only data/probes)
    "cctv": "/api/cctv",
    "cctv_stream_status": "/api/cctv/stream-status",
    "infrastructure": "/api/infrastructure",
    "maritime": "/api/maritime",
    "arcgis": "/api/arcgis",
    "geo": "/api/geo",
    # Cyber telemetry
    "cyber_threats": "/api/cyber-threats",
    "cyber_attacks": "/api/cyber-attacks",
    "malware": "/api/malware",
    # Passive OSINT lookups
    "osint_dns": "/api/osint/dns",
    "osint_whois": "/api/osint/whois",
    "osint_certs": "/api/osint/certs",
    "osint_ip": "/api/osint/ip",
    "osint_shodan": "/api/osint/shodan",
    "osint_bgp": "/api/osint/bgp",
    "osint_mac": "/api/osint/mac",
    "osint_phone": "/api/osint/phone",
    "osint_github": "/api/osint/github",
    "osint_leaks": "/api/osint/leaks",
    "osint_hudsonrock": "/api/osint/hudsonrock",
    "osint_cve": "/api/osint/cve",
    "osint_sanctions": "/api/osint/sanctions",
    "osint_threats": "/api/osint/threats",
    "osint_sweep": "/api/osint/sweep",
    # Entity graph
    "entity_expand": "/api/entity/expand",
}

# Query parameters are explicit rather than passed through blindly. This keeps
# the read layer constrained to documented input shapes.
_ENDPOINT_PARAMS: dict[str, frozenset[str]] = {
    "news": frozenset({"q"}),
    "live_news": frozenset({"q"}),
    "sentinel": frozenset({"lat", "lng", "radius", "days"}),
    "cctv": frozenset({"region", "lat", "lng", "radius"}),
    "cctv_stream_status": frozenset({"url"}),
    "maritime": frozenset(),
    "arcgis": frozenset({"service", "q", "bbox"}),
    "region_dossier": frozenset({"lat", "lng"}),
    "geo": frozenset(),
    "osint_dns": frozenset({"domain"}),
    "osint_whois": frozenset({"domain"}),
    "osint_certs": frozenset({"domain"}),
    "osint_ip": frozenset({"ip"}),
    "osint_shodan": frozenset({"ip"}),
    "osint_bgp": frozenset({"query"}),
    "osint_mac": frozenset({"mac"}),
    "osint_phone": frozenset({"number"}),
    "osint_github": frozenset({"user"}),
    "osint_leaks": frozenset({"email"}),
    "osint_hudsonrock": frozenset({"query", "type"}),
    "osint_cve": frozenset({"cve"}),
    "osint_sanctions": frozenset({"query", "schema", "limit"}),
    "osint_threats": frozenset({"query"}),
    "osint_sweep": frozenset({"ip", "cidr"}),
    "entity_expand": frozenset({"id", "type"}),
}


def osiris_endpoint_catalog() -> dict[str, str]:
    """Return the logical read-only OSIRIS endpoint catalog."""
    return dict(_ENDPOINTS)


def _validate_endpoint(endpoint: str) -> str:
    path = _ENDPOINTS.get(endpoint)
    if path is None:
        raise ValueError(f"Unsupported OSIRIS endpoint: {endpoint}")
    return path


def _build_params(
    endpoint: str,
    query: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build only documented parameters for a logical endpoint.

    Generic arguments are retained for backwards compatibility with the
    original FRIDAY integration; endpoint-specific callers use ``extra``.
    """
    supported = _ENDPOINT_PARAMS.get(endpoint, frozenset())
    candidates: dict[str, Any] = {
        "q": query,
        "lat": latitude,
        "lng": longitude,
        "radius": radius_km,
        **extra,
    }
    return {
        key: value
        for key, value in candidates.items()
        if key in supported and value is not None and value != ""
    }


async def _request(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    path = _validate_endpoint(endpoint)
    query = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    url = f"{OSIRIS_BASE_URL}{path}"
    if query:
        url = f"{url}?{urlencode(query, doseq=True)}"

    timeout = aiohttp.ClientTimeout(total=OSIRIS_TIMEOUT_SECONDS)
    headers = {"Accept": "application/json", "User-Agent": "FRIDAY/1.1"}
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

    return {
        "source": "OSIRIS Intelligence",
        "endpoint": path,
        "url": url,
        "data": data,
    }


async def osiris_intelligence(
    endpoint: str,
    query: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Call one allow-listed, read-only OSIRIS endpoint."""
    return await _request(
        endpoint,
        _build_params(
            endpoint,
            query=query,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            **extra,
        ),
    )


async def osiris_health() -> dict[str, Any]: return await _request("health")
async def osiris_stats() -> dict[str, Any]: return await _request("stats")
async def osiris_news(query: str = "") -> dict[str, Any]: return await osiris_intelligence("news", query=query)
async def osiris_live_news(query: str = "") -> dict[str, Any]: return await osiris_intelligence("live_news", query=query)
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
async def osiris_malware() -> dict[str, Any]: return await _request("malware")
async def osiris_scm_suppliers() -> dict[str, Any]: return await _request("scm_suppliers")


async def osiris_sentinel(latitude: float, longitude: float, radius_km: float = 50, days: int = 30) -> dict[str, Any]:
    return await osiris_intelligence(
        "sentinel", latitude=latitude, longitude=longitude, radius_km=radius_km, days=days,
    )


async def osiris_cctv(region: str = "", latitude: float | None = None, longitude: float | None = None,
                      radius_km: float | None = None) -> dict[str, Any]:
    return await osiris_intelligence(
        "cctv", region=region, latitude=latitude, longitude=longitude, radius_km=radius_km,
    )


async def osiris_cctv_stream_status(url: str) -> dict[str, Any]:
    return await osiris_intelligence("cctv_stream_status", url=url)


async def osiris_arcgis(service: str = "", query: str = "", bbox: str = "") -> dict[str, Any]:
    return await osiris_intelligence("arcgis", service=service, q=query, bbox=bbox)


async def osiris_region_dossier(latitude: float, longitude: float) -> dict[str, Any]:
    return await osiris_intelligence("region_dossier", latitude=latitude, longitude=longitude)


async def osiris_osint_lookup(kind: str, value: str, secondary: str = "", limit: int | None = None) -> dict[str, Any]:
    """Run a passive OSINT lookup using an explicit logical lookup type."""
    endpoint = f"osint_{kind.strip().lower()}"
    if endpoint not in _ENDPOINTS:
        raise ValueError(f"Unsupported OSINT lookup: {kind}")
    param_by_kind = {
        "dns": {"domain": value},
        "whois": {"domain": value},
        "certs": {"domain": value},
        "ip": {"ip": value},
        "shodan": {"ip": value},
        "bgp": {"query": value},
        "mac": {"mac": value},
        "phone": {"number": value},
        "github": {"user": value},
        "leaks": {"email": value},
        "hudsonrock": {"query": value, "type": secondary},
        "cve": {"cve": value},
        "sanctions": {"query": value, "schema": secondary, "limit": limit},
        "threats": {"query": value},
        "sweep": {"ip": value, "cidr": secondary},
    }
    params = param_by_kind.get(kind.strip().lower())
    if params is None:
        raise ValueError(f"Unsupported OSINT lookup: {kind}")
    return await _request(endpoint, _build_params(endpoint, **params))


async def osiris_entity_expand(entity_id: str, entity_type: str) -> dict[str, Any]:
    return await osiris_intelligence("entity_expand", id=entity_id, type=entity_type)
