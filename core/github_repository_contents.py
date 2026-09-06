"""Repository analysis using GitHub's Contents API.

This module is intentionally independent from the Git Trees endpoint. GitHub App user
access can expose repository metadata and contents while individual Git data endpoints
may vary by token/permission configuration, so repository explanation must not fail
because an optional enrichment endpoint is unavailable.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from tools.github.repository_agent import (
    MAX_TREE_ITEMS,
    _read_file,
    _recent_commits,
    _repository_metadata,
    _resolve_repository,
    _score_path,
    _request,
)

SKIP_PREFIXES = (
    ".git/", ".next/", "node_modules/", "dist/", "build/", "coverage/",
    "__pycache__/", ".venv/", "venv/", "vendor/", "target/",
)

EXPLANATION_CONTRACT = {
    "format": "Markdown",
    "required_sections": [
        "## Overview",
        "## What the project does",
        "## Main features",
        "## Architecture",
        "## Technology stack",
        "## Repository structure",
        "## How it works",
        "## Important files",
        "## Integrations and dependencies",
        "## Security and permissions",
        "## Testing and quality",
        "## Risks and gaps",
        "## Summary",
    ],
    "rules": [
        "Start with a concise 2-4 sentence overview before detailed sections.",
        "Use Markdown headings, bullets, numbered lists, tables, and fenced code blocks only when they improve clarity.",
        "Use backticks for file paths, directories, commands, package names, APIs, and code symbols.",
        "Explain relationships between components instead of only listing files.",
        "For architecture, show a compact ASCII diagram when the evidence supports a clear flow.",
        "Separate observed facts from reasonable inferences; label inferences explicitly.",
        "If evidence is missing, say 'Not verified from the inspected files' rather than guessing.",
        "Do not claim a feature exists solely because a dependency could support it.",
        "Do not expose tokens, credentials, environment values, or private configuration contents.",
        "Do not mention the internal evidence payload, model, prompt, or tool execution process.",
    ],
}


def _build_repository_map(tree: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Create a compact structural map that helps the synthesizer explain the codebase."""
    directories: list[str] = []
    root_files: list[str] = []
    source_roots: list[str] = []

    for item in tree:
        path = str(item.get("path") or "")
        item_type = str(item.get("type") or "")
        if not path:
            continue
        if item_type in {"tree", "dir"}:
            directories.append(path)
            if "/" not in path:
                source_roots.append(path)
        elif "/" not in path:
            root_files.append(path)

    return {
        "root_files": sorted(root_files),
        "top_level_directories": sorted(source_roots),
        "directories_discovered": sorted(directories)[:80],
    }


async def contents_tree(repository: str, ref: str, max_items: int = MAX_TREE_ITEMS) -> tuple[list[dict[str, Any]], bool]:
    """Recursively collect repository structure through the Contents API."""
    tree: list[dict[str, Any]] = []
    queue = [""]
    partial = False

    while queue and len(tree) < max_items:
        path = queue.pop(0)
        endpoint = (
            f"/repos/{repository}/contents/{quote(path, safe='/')}"
            if path
            else f"/repos/{repository}/contents"
        )
        try:
            data = await _request(endpoint, {"ref": ref})
        except Exception as error:
            raise RuntimeError(
                f"GitHub repository contents request failed for {repository}@{ref} "
                f"at {endpoint}: {error}"
            ) from error

        items = data if isinstance(data, list) else [data]
        for item in items:
            item_path = str(item.get("path") or "")
            item_type = str(item.get("type") or "")
            if not item_path or any(item_path.startswith(prefix) for prefix in SKIP_PREFIXES):
                continue

            tree.append({
                "path": item_path,
                "mode": None,
                "type": "blob" if item_type == "file" else item_type,
                "sha": item.get("sha"),
                "size": item.get("size"),
                "url": item.get("html_url") or item.get("url"),
            })

            if len(tree) >= max_items:
                partial = True
                break
            if item_type == "dir":
                queue.append(item_path)

    if queue:
        partial = True
    return tree, partial


async def analyze_repository(
    repository: str,
    ref: str | None = None,
    max_files: int = 18,
    commit_limit: int = 8,
) -> dict[str, Any]:
    """Build a bounded repository dossier without requiring Git Trees."""
    canonical = await _resolve_repository(repository)
    metadata = await _repository_metadata(canonical)
    target_ref = ref or str(metadata.get("default_branch") or "main")

    tree, partial = await contents_tree(canonical, target_ref)
    blobs = [item for item in tree if item.get("type") == "blob"]
    blobs.sort(
        key=lambda item: (
            -_score_path(str(item.get("path") or "")),
            str(item.get("path") or ""),
        )
    )
    selected_paths = [
        str(item["path"])
        for item in blobs[: max(4, min(max_files, 30))]
    ]

    files: list[dict[str, Any]] = []
    for path in selected_paths:
        try:
            files.append(await _read_file(canonical, path, target_ref))
        except Exception as error:
            files.append({"path": path, "error": str(error)})

    commits: list[dict[str, Any]] = []
    commit_error: str | None = None
    if commit_limit:
        try:
            commits = await _recent_commits(
                canonical,
                max(0, min(commit_limit, 20)),
            )
        except Exception as error:
            commit_error = str(error)

    notes = [
        "Repository identity was resolved from GitHub.",
        "Repository structure was collected through the Contents API.",
        "The low-level Git Trees endpoint is intentionally avoided for repository analysis.",
        "Files were prioritized by documentation, configuration, architecture, and application entry-point relevance.",
    ]
    if partial:
        notes.append("The repository tree is bounded and may be partial; do not describe uninspected paths as exhaustive.")
    if commit_error:
        notes.append(f"Recent commits were unavailable and were skipped: {commit_error}")

    return {
        "repository": metadata,
        "ref": target_ref,
        "tree": tree,
        "tree_count": len(tree),
        "tree_is_partial": partial,
        "repository_map": _build_repository_map(tree),
        "selected_files": selected_paths,
        "files": files,
        "recent_commits": commits,
        "access": "private-authenticated" if metadata.get("private") else "public",
        "analysis_notes": notes,
        "explanation_contract": EXPLANATION_CONTRACT,
    }
