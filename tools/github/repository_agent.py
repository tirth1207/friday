"""Deterministic GitHub repository analysis workflow."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
MAX_FILE_CHARS = 150_000
MAX_TREE_ITEMS = 20_000
MAX_REPOSITORY_PAGES = 5


class GitHubAgentSettings(BaseSettings):
    username: str = ""
    pat: str = ""
    api_version: str = GITHUB_API_VERSION

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_prefix="GITHUB_",
        extra="ignore",
    )


settings = GitHubAgentSettings()

TEXT_EXTENSIONS = {
    ".md", ".mdx", ".txt", ".json", ".jsonc", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".env", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".go", ".java", ".kt", ".rs", ".php", ".rb", ".cs", ".cpp",
    ".c", ".h", ".hpp", ".sql", ".graphql", ".gql", ".prisma", ".vue",
    ".svelte", ".css", ".scss", ".html", ".xml", ".sh", ".ps1",
}

IMPORTANT_EXACT = {
    "readme.md", "readme.mdx", "package.json", "pnpm-workspace.yaml", "turbo.json",
    "nx.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt",
    "cargo.toml", "go.mod", "pom.xml", "build.gradle", "dockerfile",
    "docker-compose.yml", "docker-compose.yaml", "next.config.js", "next.config.mjs",
    "next.config.ts", "vite.config.ts", "vite.config.js", "tsconfig.json",
    "vercel.json", "supabase/config.toml", ".env.example", "schema.prisma",
}

IMPORTANT_DIRS = (
    "src/", "app/", "apps/", "api/", "server/", "backend/", "frontend/",
    "core/", "services/", "lib/", "components/", "routes/", "models/",
    "database/", "db/", "supabase/", "prisma/", "docs/", "documents/",
)

SKIP_PREFIXES = (
    ".git/", ".next/", "node_modules/", "dist/", "build/", "coverage/",
    "__pycache__/", ".venv/", "venv/", "vendor/", "target/",
)


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": settings.api_version or GITHUB_API_VERSION,
        "User-Agent": "FRIDAY-Personal-AI",
    }
    if settings.pat.strip():
        headers["Authorization"] = f"Bearer {settings.pat.strip()}"
    return headers


async def _request(path: str, params: dict[str, Any] | None = None) -> Any:
    timeout = httpx.Timeout(20.0, connect=7.0, read=20.0, write=20.0, pool=10.0)
    async with httpx.AsyncClient(base_url=GITHUB_API, headers=_headers(), timeout=timeout) as client:
        try:
            response = await client.get(path, params=params)
        except httpx.RequestError as error:
            raise RuntimeError(f"GitHub network request failed: {error}") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("message", "GitHub request failed")
            except Exception:
                detail = response.text[:300]
            if response.status_code in {401, 403} and not settings.pat.strip():
                raise RuntimeError(
                    f"GitHub API {response.status_code}: {detail}. This repository or endpoint requires GITHUB_PAT."
                )
            raise RuntimeError(f"GitHub API {response.status_code}: {detail}")
        return response.json()


def _normalize_repository_value(value: str) -> str:
    """Normalize repository labels accidentally prepended by the chat/UI."""
    raw = value.strip()
    raw = raw.removeprefix("Repository:").removeprefix("repository:").strip()
    # The UI has historically emitted `Repositorytirth1207/friday` without a separator.
    raw = re.sub(r"^repository(?=[A-Za-z0-9_.-]+/)", "", raw, flags=re.IGNORECASE)
    return raw.strip()


def _repo_parts(value: str) -> tuple[str | None, str]:
    raw = _normalize_repository_value(value).removesuffix(".git").strip("/")
    if raw.startswith(("https://github.com/", "http://github.com/")):
        parsed = urlparse(raw)
        parts = [part for part in parsed.path.split("/") if part]
    else:
        parts = [part for part in raw.split("/") if part]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return settings.username.strip() or None, parts[0]
    raise ValueError(f"Invalid GitHub repository: {value}")


async def _accessible_repositories(limit: int = 100) -> list[dict[str, Any]]:
    """Return repositories visible to the configured GitHub account."""
    if not settings.pat.strip():
        return []

    repositories: list[dict[str, Any]] = []
    per_page = max(1, min(limit, 100))
    for page in range(1, MAX_REPOSITORY_PAGES + 1):
        data = await _request(
            "/user/repos",
            {
                "visibility": "all",
                "affiliation": "owner,collaborator,organization_member",
                "sort": "pushed",
                "direction": "desc",
                "per_page": per_page,
                "page": page,
            },
        )
        if not isinstance(data, list):
            break
        repositories.extend(data)
        if len(data) < per_page:
            break
    return repositories


def _repository_name_candidates(name: str) -> tuple[str, str]:
    raw = name.strip().removesuffix(".git")
    normalized = raw.casefold()
    collapsed = "".join(char for char in normalized if char.isalnum())
    return normalized, collapsed


def _match_repositories(items: list[dict[str, Any]], requested_name: str) -> list[dict[str, Any]]:
    normalized, collapsed = _repository_name_candidates(requested_name)
    exact = [item for item in items if str(item.get("name") or "").casefold() == normalized]
    if exact:
        return exact
    if collapsed:
        return [
            item for item in items
            if "".join(char for char in str(item.get("name") or "").casefold() if char.isalnum()) == collapsed
        ]
    return []


def _match_repository(items: list[dict[str, Any]], requested_name: str) -> dict[str, Any] | None:
    matches = _match_repositories(items, requested_name)
    return matches[0] if matches else None


async def _resolve_repository(value: str) -> str:
    owner, name = _repo_parts(value)

    if owner and "/" in _normalize_repository_value(value):
        data = await _request(f"/repos/{owner}/{name}")
        return str(data.get("full_name") or f"{owner}/{name}")
