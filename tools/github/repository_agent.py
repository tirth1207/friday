"""Deterministic GitHub repository analysis workflow.

This module deliberately does not ask an LLM to decide which GitHub calls to make.
It resolves the repository, fetches its metadata and full tree, then selects the most
useful documentation/configuration/entry-point files for inspection. This makes
repository understanding work even when the NVIDIA model is temporarily unavailable
for native tool calling.
"""

from __future__ import annotations

from typing import Any

from tools.github.github_tools import (
    github_get_repository,
    github_get_tree,
    github_read_file,
    github_list_commits,
)


TEXT_EXTENSIONS = {
    ".md", ".mdx", ".txt", ".json", ".jsonc", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".env", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".go", ".java", ".kt", ".rs", ".php", ".rb", ".cs", ".cpp",
    ".c", ".h", ".hpp", ".sql", ".graphql", ".gql", ".prisma", ".vue",
    ".svelte", ".css", ".scss", ".html", ".xml", ".sh", ".ps1",
}

IMPORTANT_EXACT = {
    "readme.md", "package.json", "pnpm-workspace.yaml", "turbo.json",
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


def _score_path(path: str) -> int:
    clean = path.replace("\\", "/").lower()
    name = clean.rsplit("/", 1)[-1]
    score = 0

    if clean in IMPORTANT_EXACT:
        score += 1000
    if name in {"readme.md", "readme.mdx"}:
        score += 900
    if name in {"package.json", "pyproject.toml", "requirements.txt", "go.mod", "cargo.toml"}:
        score += 850
    if any(clean.startswith(prefix) for prefix in SKIP_PREFIXES):
        return -10000
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
    selected: list[str] = []
    seen: set[str] = set()
    for _, path in candidates:
        if path in seen:
            continue
        seen.add(path)
        selected.append(path)
        if len(selected) >= max_files:
            break
    return selected


async def github_analyze_repository(
    repository: str,
    ref: str | None = None,
    max_files: int = 16,
    commit_limit: int = 8,
) -> dict[str, Any]:
    """Build a bounded repository dossier using GitHub tools only.

    Private repositories are accessed with FRIDAY's configured GitHub PAT; public
    repositories work without a PAT as long as GitHub permits the public request.
    The result contains metadata, the complete tree, recent commits, and contents
    of the most informative text/configuration files.
    """
    max_files = max(4, min(max_files, 30))
    commit_limit = max(0, min(commit_limit, 20))

    metadata = await github_get_repository(repository)
    canonical = str(metadata.get("full_name") or repository)
    tree = await github_get_tree(canonical, ref=ref, recursive=True)
    selected_paths = _select_files(tree, max_files)

    files: list[dict[str, Any]] = []
    for path in selected_paths:
        try:
            result = await github_read_file(canonical, path, ref=ref)
            files.append({
                "path": path,
                "size": result.get("size"),
                "content": result.get("content", ""),
            })
        except Exception as error:
            files.append({"path": path, "error": str(error)})

    commits: list[dict[str, Any]] = []
    if commit_limit:
        try:
            commits = await github_list_commits(canonical, limit=commit_limit)
        except Exception as error:
            commits = [{"error": str(error)}]

    return {
        "repository": metadata,
        "ref": ref or metadata.get("default_branch"),
        "tree": tree,
        "tree_count": len(tree),
        "selected_files": selected_paths,
        "files": files,
        "recent_commits": commits,
        "analysis_notes": [
            "Repository identity and tree were fetched from GitHub.",
            "Selected files were prioritized by documentation, configuration, architecture, and entry-point relevance.",
            "The full tree is included so a later reasoning step can identify additional files to inspect.",
        ],
    }
