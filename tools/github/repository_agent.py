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
                    f"GitHub API {response.status_code}: {detail}. "
                    "This repository or endpoint requires GITHUB_PAT."
                )
            raise RuntimeError(f"GitHub API {response.status_code}: {detail}")
        return response.json()


def _repo_parts(value: str) -> tuple[str | None, str]:
    raw = value.strip().removesuffix(".git").strip("/")
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
    """Return repositories visible to the configured GitHub account.

    /user/repos is intentionally preferred over search for authenticated repository
    resolution because it includes private repositories the token can access.
    """
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


def _repository_name_candidates(name: str) -> list[str]:
    """Generate stable normalized forms for natural-language repository matching."""
    raw = name.strip().removesuffix(".git")
    normalized = raw.casefold()
    collapsed = "".join(char for char in normalized if char.isalnum())
    return [normalized, collapsed]


def _match_repository(items: list[dict[str, Any]], requested_name: str) -> dict[str, Any] | None:
    """Match a repository name without depending on its exact capitalization."""
    requested_forms = _repository_name_candidates(requested_name)

    # Exact repository-name match, case-insensitive, always wins.
    for item in items:
        repo_name = str(item.get("name") or "")
        if repo_name.casefold() == requested_forms[0]:
            return item

    # Then tolerate harmless punctuation/case differences in natural language.
    requested_collapsed = requested_forms[1]
    if requested_collapsed:
        for item in items:
            repo_name = str(item.get("name") or "")
            candidate = "".join(char for char in repo_name.casefold() if char.isalnum())
            if candidate == requested_collapsed:
                return item
    return None


async def _resolve_repository(value: str) -> str:
    owner, name = _repo_parts(value)

    # Fully qualified repositories are authoritative. This preserves support for
    # repositories outside the configured user's account when the PAT can access them.
    if owner:
        try:
            data = await _request(f"/repos/{owner}/{name}")
            return str(data.get("full_name") or f"{owner}/{name}")
        except RuntimeError as error:
            # For a one-part name that was expanded using GITHUB_USERNAME, do not
            # immediately fail: the repository may differ only by case or be a
            # collaborator/organization repository. Resolve it from /user/repos.
            if owner != settings.username.strip() or "404" not in str(error):
                raise

    # Natural-language repository names should resolve against repositories the
    # authenticated account can actually access. This is what makes names such as
    # "minor_project-TPO", "orbit", and "ai_test" reliable, including private repos.
    accessible = await _accessible_repositories()
    match = _match_repository(accessible, name)
    if match:
        return str(match.get("full_name"))

    # Public fallback: this still works when no PAT is configured.
    data = await _request(
        "/search/repositories",
        {"q": f"{name} in:name", "per_page": 10},
    )
    items = data.get("items") or []
    exact = _match_repository(items, name)
    chosen = exact or (items[0] if items else None)
    if not chosen:
        raise RuntimeError(f"Could not resolve GitHub repository: {name}")
    return str(chosen.get("full_name"))


def _score_path(path: str) -> int:
    clean = path.replace("\\", "/").lower()
    name = clean.rsplit("/", 1)[-1]
    if any(clean.startswith(prefix) for prefix in SKIP_PREFIXES):
        return -10000
    score = 0
    if clean in IMPORTANT_EXACT:
        score += 1000
    if name in {"readme.md", "readme.mdx"}:
        score += 900
    if name in {"package.json", "pyproject.toml", "requirements.txt", "go.mod", "cargo.toml"}:
        score += 850
    if any(clean.startswith(prefix) for prefix in IMPORTANT_DIRS):
        score += 120
    for keyword, points in {
        "architecture": 180, "api": 150, "server": 140, "backend": 140,
        "frontend": 130, "database": 130, "schema": 130, "auth": 120,
        "route": 110, "controller": 110, "service": 100, "model": 90,
        "config": 90, "main": 80, "index": 70, "app": 60, "layout": 50,
        "document": 40, "test": 25,
    }.items():
        if keyword in clean:
            score += points
    if ".github/" in clean:
        score += 60
    if clean.endswith(tuple(TEXT_EXTENSIONS)):
        score += 20
    return score


def _select_files(tree: list[dict[str, Any]], max_files: int) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = str(item.get("path") or "")
        lower = path.lower()
        if not lower.endswith(tuple(TEXT_EXTENSIONS)) and lower.rsplit("/", 1)[-1] not in IMPORTANT_EXACT:
            continue
        score = _score_path(path)
        if score > -1000:
            candidates.append((score, path))
    candidates.sort(key=lambda pair: (-pair[0], pair[1]))
    return [path for _, path in candidates[:max_files]]


async def _repository_metadata(repository: str) -> dict[str, Any]:
    data = await _request(f"/repos/{repository}")
    return {
        "name": data.get("name"), "full_name": data.get("full_name"),
        "private": data.get("private"), "fork": data.get("fork"),
        "archived": data.get("archived"), "description": data.get("description"),
        "language": data.get("language"), "default_branch": data.get("default_branch"),
        "stars": data.get("stargazers_count", 0), "forks": data.get("forks_count", 0),
        "open_issues": data.get("open_issues_count", 0), "size_kb": data.get("size", 0),
        "created_at": data.get("created_at"), "updated_at": data.get("updated_at"),
        "pushed_at": data.get("pushed_at"), "homepage": data.get("homepage"),
        "license": (data.get("license") or {}).get("spdx_id"),
        "topics": data.get("topics", []), "owner": (data.get("owner") or {}).get("login"),
        "permissions": data.get("permissions", {}), "html_url": data.get("html_url"),
    }


async def _tree(repository: str, ref: str) -> tuple[list[dict[str, Any]], bool]:
    commit = await _request(f"/repos/{repository}/commits/{quote(ref, safe='')}")
    tree_sha = ((commit.get("commit") or {}).get("tree") or {}).get("sha")
    if not tree_sha:
        raise RuntimeError(f"Could not resolve Git tree for {repository}@{ref}")
    data = await _request(f"/repos/{repository}/git/trees/{tree_sha}", {"recursive": "1"})
    partial = bool(data.get("truncated"))
    items = list(data.get("tree", []))[:MAX_TREE_ITEMS]
    return [
        {"path": item.get("path"), "mode": item.get("mode"), "type": item.get("type"), "sha": item.get("sha"), "size": item.get("size"), "url": item.get("url")}
        for item in items
    ], partial


async def _read_file(repository: str, path: str, ref: str) -> dict[str, Any]:
    encoded_path = quote(path.strip().lstrip("/"), safe="/")
    data = await _request(f"/repos/{repository}/contents/{encoded_path}", {"ref": ref})
    content = data.get("content") or ""
    if data.get("encoding") == "base64":
        try:
            content = base64.b64decode(content).decode("utf-8")
        except UnicodeDecodeError:
            return {"path": path, "binary": True, "size": data.get("size")}
    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + "\n\n[OUTPUT TRUNCATED]"
    return {"path": path, "size": data.get("size"), "content": content}


async def _recent_commits(repository: str, limit: int) -> list[dict[str, Any]]:
    data = await _request(f"/repos/{repository}/commits", {"per_page": limit})
    return [
        {"sha": item.get("sha"), "message": (item.get("commit") or {}).get("message", "").split("\n", 1)[0],
         "author": (item.get("author") or {}).get("login") or (item.get("commit") or {}).get("author", {}).get("name"),
         "date": (item.get("commit") or {}).get("author", {}).get("date"), "html_url": item.get("html_url")}
        for item in data
    ]


async def github_analyze_repository(repository: str, ref: str | None = None, max_files: int = 16, commit_limit: int = 8) -> dict[str, Any]:
    """Build a bounded evidence dossier for any accessible GitHub repository."""
    max_files = max(4, min(max_files, 30))
    commit_limit = max(0, min(commit_limit, 20))
    canonical = await _resolve_repository(repository)
    metadata = await _repository_metadata(canonical)
    target_ref = ref or str(metadata.get("default_branch") or "main")
    tree, partial = await _tree(canonical, target_ref)
    selected_paths = _select_files(tree, max_files)
    files: list[dict[str, Any]] = []
    for path in selected_paths:
        try:
            files.append(await _read_file(canonical, path, target_ref))
        except Exception as error:
            files.append({"path": path, "error": str(error)})
    commits = await _recent_commits(canonical, commit_limit) if commit_limit else []
    return {
        "repository": metadata, "ref": target_ref, "tree": tree, "tree_count": len(tree),
        "tree_is_partial": partial, "selected_files": selected_paths, "files": files,
        "recent_commits": commits,
        "access": "private-authenticated" if metadata.get("private") else "public",
        "analysis_notes": [
            "Repository identity was resolved from GitHub.",
            "Natural-language names are matched against repositories accessible to the authenticated account before public search fallback.",
            "The Git tree was requested recursively; very large repositories may return a partial tree.",
            "Files were prioritized by documentation, configuration, architecture, and application entry-point relevance.",
            "Use github.file.read or github.code.search for deeper targeted inspection after this dossier.",
        ],
    }
