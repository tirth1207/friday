"""Canonical GitHub repository resolution for FRIDAY.

One-part repository names are resolved against repositories accessible to the
configured GitHub account before any public-search fallback is attempted.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class ResolvedRepository:
    full_name: str
    name: str
    owner: str
    private: bool
    default_branch: str


def normalize_repository_name(value: str) -> str:
    """Normalize a repository name for safe natural-language matching."""
    return "".join(char for char in value.strip().casefold() if char.isalnum())


def parse_repository_reference(value: str) -> tuple[str | None, str]:
    """Parse owner/name, GitHub URLs, or one-part repository names."""
    raw = value.strip().removesuffix(".git").strip("/")
    if raw.startswith(("https://github.com/", "http://github.com/")):
        raw = raw.split("github.com/", 1)[1].split("/", 2)[0] + "/" + raw.split("github.com/", 1)[1].split("/", 2)[1]
    parts = [part for part in raw.split("/") if part]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return None, parts[0]
    raise ValueError(f"Invalid GitHub repository: {value}")


def match_repository(items: list[dict[str, Any]], requested_name: str) -> dict[str, Any] | None:
    """Match exact case-insensitive names first, then normalized punctuation."""
    requested = requested_name.strip().casefold()
    for item in items:
        name = str(item.get("name") or "")
        if name.casefold() == requested:
            return item

    normalized = normalize_repository_name(requested_name)
    if normalized:
        candidates = [
            item for item in items
            if normalize_repository_name(str(item.get("name") or "")) == normalized
        ]
        if len(candidates) == 1:
            return candidates[0]
    return None


class GitHubRepositoryResolver:
    """Resolve repository references without hardcoded project aliases."""

    def __init__(
        self,
        request: Callable[[str, dict[str, Any] | None], Awaitable[Any]],
        username: str = "",
        has_pat: bool = False,
    ) -> None:
        self._request = request
        self._username = username.strip()
        self._has_pat = has_pat

    async def _accessible_repositories(self) -> list[dict[str, Any]]:
        if not self._has_pat:
            return []
        repositories: list[dict[str, Any]] = []
        for page in range(1, 6):
            data = await self._request(
                "/user/repos",
                {
                    "visibility": "all",
                    "affiliation": "owner,collaborator,organization_member",
                    "sort": "pushed",
                    "direction": "desc",
                    "per_page": 100,
                    "page": page,
                },
            )
            if not isinstance(data, list):
                break
            repositories.extend(data)
            if len(data) < 100:
                break
        return repositories

    async def resolve(self, value: str) -> ResolvedRepository:
        owner, name = parse_repository_reference(value)
        attempts: list[str] = []

        # Explicit owner/name is authoritative.
        if owner:
            attempts.append(f"explicit:{owner}/{name}")
            data = await self._request(f"/repos/{owner}/{name}", None)
            return ResolvedRepository(
                full_name=str(data.get("full_name") or f"{owner}/{name}"),
                name=str(data.get("name") or name),
                owner=str((data.get("owner") or {}).get("login") or owner),
                private=bool(data.get("private")),
                default_branch=str(data.get("default_branch") or "main"),
            )

        # One-part names are resolved from the authenticated account first.
        attempts.append("accessible-account-index")
        accessible = await self._accessible_repositories()
        match = match_repository(accessible, name)
        if match:
            return ResolvedRepository(
                full_name=str(match.get("full_name")),
                name=str(match.get("name") or name),
                owner=str((match.get("owner") or {}).get("login") or self._username),
                private=bool(match.get("private")),
                default_branch=str(match.get("default_branch") or "main"),
            )

        # Only use configured username for a secondary direct lookup. This is useful
        # for public repositories when /user/repos is unavailable or not configured.
        if self._username:
            attempts.append(f"configured-owner:{self._username}/{name}")
            try:
                data = await self._request(f"/repos/{self._username}/{name}", None)
                return ResolvedRepository(
                    full_name=str(data.get("full_name") or f"{self._username}/{name}"),
                    name=str(data.get("name") or name),
                    owner=str((data.get("owner") or {}).get("login") or self._username),
                    private=bool(data.get("private")),
                    default_branch=str(data.get("default_branch") or "main"),
                )
            except RuntimeError as error:
                if "404" not in str(error):
                    raise

        # Public search is the final fallback for genuinely public repositories.
        attempts.append("public-search")
        data = await self._request(
            "/search/repositories",
            {"q": f"{name} in:name", "per_page": 10},
        )
        items = data.get("items") or []
        match = match_repository(items, name)
        chosen = match or (items[0] if items else None)
        if chosen:
            return ResolvedRepository(
                full_name=str(chosen.get("full_name")),
                name=str(chosen.get("name") or name),
                owner=str((chosen.get("owner") or {}).get("login") or ""),
                private=bool(chosen.get("private")),
                default_branch=str(chosen.get("default_branch") or "main"),
            )

        raise RuntimeError(
            f"Could not resolve GitHub repository '{name}'. Resolution stages: {', '.join(attempts)}."
        )
