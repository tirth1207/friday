"""Spotify playback controls for FRIDAY."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import aiohttp
from langchain.tools import tool
from pydantic_settings import BaseSettings, SettingsConfigDict


class SpotifySettings(BaseSettings):
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    access_token: str = ""
    device_id: str = ""

    model_config = SettingsConfigDict(env_file=str(Path(__file__).resolve().parents[2] / ".env"), env_prefix="SPOTIFY_", extra="ignore")


settings = SpotifySettings()
_cached_token = ""
_cached_expires_at = 0.0


async def _access_token() -> str:
    global _cached_token, _cached_expires_at
    if _cached_token and _cached_expires_at > time.time() + 60:
        return _cached_token
    if settings.access_token.strip():
        return settings.access_token.strip()
    if not settings.client_id.strip() or not settings.client_secret.strip() or not settings.refresh_token.strip():
        raise RuntimeError("Spotify is not configured. Set SPOTIFY_ACCESS_TOKEN or the client credentials plus SPOTIFY_REFRESH_TOKEN.")
    auth = aiohttp.BasicAuth(settings.client_id.strip(), settings.client_secret.strip())
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        async with session.post("https://accounts.spotify.com/api/token", data={"grant_type": "refresh_token", "refresh_token": settings.refresh_token.strip()}, auth=auth) as response:
            data = await response.json(content_type=None)
            if response.status >= 400 or not data.get("access_token"):
                raise RuntimeError(f"Spotify token refresh failed: {data.get('error_description') or data.get('error') or response.status}")
    _cached_token = str(data["access_token"])
    _cached_expires_at = time.time() + int(data.get("expires_in", 3600))
    return _cached_token


async def _spotify(method: str, path: str, *, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> Any:
    token = await _access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if settings.device_id.strip() and method in {"PUT", "POST"}:
        params = {**(params or {}), "device_id": settings.device_id.strip()}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15), headers=headers) as session:
        async with session.request(method, f"https://api.spotify.com/v1{path}", params=params, json=body) as response:
            if response.status == 204:
                return {"status": "ok"}
            data = await response.json(content_type=None)
            if response.status >= 400:
                raise RuntimeError(f"Spotify API error {response.status}: {data}")
            return data


@tool("music_play")
async def music_play(query: str) -> dict[str, Any]:
    """Search Spotify for a track/artist and start the top matching track."""
    query = query.strip()
    if not query:
        raise ValueError("Music query cannot be empty.")
    results = await _spotify("GET", "/search", params={"q": query, "type": "track", "limit": 1})
    tracks = ((results.get("tracks") or {}).get("items") or [])
    if not tracks:
        raise RuntimeError(f"No Spotify track found for '{query}'.")
    track = tracks[0]
    await _spotify("PUT", "/me/player/play", body={"uris": [track["uri"]]})
    return {"status": "playing", "name": track.get("name"), "artist": ", ".join(a.get("name", "") for a in track.get("artists", [])), "uri": track.get("uri")}


@tool("music_pause")
async def music_pause() -> dict[str, str]:
    """Pause Spotify playback."""
    return await _spotify("PUT", "/me/player/pause")


@tool("music_next")
async def music_next() -> dict[str, str]:
    """Skip to the next Spotify track."""
    return await _spotify("POST", "/me/player/next")


@tool("music_current")
async def music_current() -> dict[str, Any]:
    """Return the current Spotify playback state."""
    data = await _spotify("GET", "/me/player")
    if not data:
        return {"playing": False, "track": None}
    item = data.get("item") or {}
    return {"playing": bool(data.get("is_playing")), "track": item.get("name"), "artist": ", ".join(a.get("name", "") for a in item.get("artists", [])), "device": (data.get("device") or {}).get("name")}


MUSIC_LANGCHAIN_TOOLS = [music_play, music_pause, music_next, music_current]
