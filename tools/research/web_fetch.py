"""Fetch and extract readable text from a public webpage."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup
from langchain.tools import tool

TIMEOUT_SECONDS = 15
_MAX_RESPONSE_BYTES = 2_000_000
_MAX_TEXT_CHARS = 40_000


def _validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only absolute HTTP(S) URLs are supported.")
    return url.strip()


@tool("web_fetch")
async def web_fetch(url: str) -> dict[str, Any]:
    """Fetch a public HTTP(S) page and return bounded readable text."""
    url = _validate_url(url)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
    headers = {"Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5", "User-Agent": "FRIDAY/1.0"}
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.content_length and response.content_length > _MAX_RESPONSE_BYTES:
                    raise RuntimeError(f"Web response too large: {response.content_length} bytes")
                raw = await response.content.read(_MAX_RESPONSE_BYTES + 1)
                if len(raw) > _MAX_RESPONSE_BYTES:
                    raise RuntimeError("Web response exceeded the safety size limit")
                if response.status >= 400:
                    detail = raw.decode("utf-8", errors="replace")[:500]
                    raise RuntimeError(f"Web server returned HTTP {response.status}: {detail}")
                content_type = response.headers.get("Content-Type", "")
                text = raw.decode("utf-8", errors="replace")
                if "html" in content_type.lower() or "xhtml" in content_type.lower():
                    soup = BeautifulSoup(text, "html.parser")
                    for node in soup(["script", "style", "noscript", "svg"]):
                        node.decompose()
                    title = soup.title.get_text(" ", strip=True) if soup.title else ""
                    text = soup.get_text(" ", strip=True)
                else:
                    title = ""
                text = " ".join(text.split())[:_MAX_TEXT_CHARS]
                return {"url": str(response.url), "status": response.status, "content_type": content_type, "title": title, "text": text}
    except asyncio.TimeoutError as error:
        raise RuntimeError(f"Web fetch timed out after {TIMEOUT_SECONDS}s") from error
    except aiohttp.ClientError as error:
        raise RuntimeError(f"Web fetch failed: {error}") from error
