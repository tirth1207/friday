"""Broad GitHub API tool for FRIDAY's agent runtime.

This complements the semantic GitHub tools with a single LangChain-compatible
escape hatch for GitHub REST operations that do not yet have a dedicated wrapper.
Read operations are safe; mutations require explicit runtime permission.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from langchain.tools import tool

from tools.github.github_tools import GITHUB_API, GITHUB_API_VERSION, _credentials, settings


_ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_MAX_RESPONSE_CHARS = 200_000


def _normalize_path(path: str) -> str:
    value = path.strip()
    if not value:
        raise ValueError("GitHub API path cannot be empty.")
    if value.startswith("https://api.github.com"):
        value = value.removeprefix("https://api.github.com")
    if not value.startswith("/"):
        value = "/" + value
    if "?" in value:
        value = value.split("?", 1)[0]
    if value.startswith("//") or ".." in value.split("/"):
        raise ValueError("Invalid GitHub API path.")
    return value


def _sanitize(value: Any) -> Any:
    """Remove obvious credential fields before returning API responses."""
    secret_names = {"token", "access_token", "authorization", "pat", "password", "client_secret"}
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in secret_names else _sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


async def github_api_request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    """Call an approved GitHub REST API endpoint.

    Use this when no dedicated github.* tool exists. `path` must be a GitHub REST
    path such as `/repos/OWNER/REPO/issues`. Never put credentials in params/body.
    """
    normalized_method = method.strip().upper()
    if normalized_method not in _ALLOWED_METHODS:
        raise ValueError(f"Unsupported GitHub HTTP method: {method}")
    path = _normalize_path(path)
    _, token = _credentials()
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": settings.api_version or GITHUB_API_VERSION,
        "User-Agent": "FRIDAY-Personal-AI",
    }
    timeout = httpx.Timeout(30.0, connect=7.0, read=30.0, write=30.0, pool=10.0)
    async with httpx.AsyncClient(base_url=GITHUB_API, headers=headers, timeout=timeout) as client:
        try:
            response = await client.request(
                normalized_method,
                path,
                params=params or None,
                json=body if normalized_method != "GET" else None,
            )
        except httpx.RequestError as error:
            raise RuntimeError(f"GitHub network request failed: {error}") from error

    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("message", "GitHub request failed") if isinstance(payload, dict) else str(payload)
        except Exception:
            detail = response.text[:500]
        raise RuntimeError(f"GitHub API {response.status_code}: {detail}")

    if not response.content:
        return {"status": response.status_code, "success": True}

    try:
        payload = response.json()
    except Exception:
        text = response.text
        return {"status": response.status_code, "content": text[:_MAX_RESPONSE_CHARS]}

    sanitized = _sanitize(payload)
    if isinstance(sanitized, str) and len(sanitized) > _MAX_RESPONSE_CHARS:
        sanitized = sanitized[:_MAX_RESPONSE_CHARS] + "\n[OUTPUT TRUNCATED]"
    return {"status": response.status_code, "data": sanitized}


@tool("github.api")
async def github_api(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    """Universal GitHub REST API access for operations without a dedicated tool.

    Examples: GET `/repos/owner/repo/releases`, GET `/repos/owner/repo/actions/runs`,
    POST `/repos/owner/repo/issues`, PATCH `/repos/owner/repo/pulls/1`.
    The FRIDAY runtime permission layer must approve mutations.
    """
    return await github_api_request(method, path, params, body)
