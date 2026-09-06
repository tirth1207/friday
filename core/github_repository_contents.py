"""Repository analysis using the GitHub Contents API."""

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

SKIP_PREFIXES = (".git/", ".next/", "node_modules/", "dist/", "build/", "coverage/", "__pycache__/", ".venv/", "venv/", "vendor/", "target/")


async def _contents_tree(repository: str, ref: str, max_items: int = MAX_TREE_ITEMS) -> tuple[list[dict[str, Any]], bool]:
    tree: list[dict[str, Any]] = []
    queue = [""]
    partial = False
    while queue and len(tree) < max_items:
        path = queue.pop(0)
        endpoint = f"/repos/{repository}/contents/{quote(path, safe='/')}" if path else f"/repos/{repository}/contents"
        data = await _request(endpoint, {"ref": ref})
        items = data if isinstance(data, list) else [data]
        for item in items:
            item_path = str(item.get("path") or "")
            item_type = str(item.get("type") or "")
            if not item_path or any(item_path.startswith(prefix) for prefix in SKIP_PREFIXES):
                continue
            tree.append({"path": item_path, "mode": None, "type": "blob" if item_type == "file" else item_type, "sha": item.get("sha"), "size": item.get("size"), "url": item.get("html_url") or item.get("url")})
            if len(tree) >= max_items:
                partial = True
                break
            if item_type == "dir":
                queue.append(item_path)
    if queue:
        partial = True
    return tree, partial


async def analyze_repository(repository: str, ref: str | None = None, max_files: int = 18, commit_limit: int = 8) -> dict[str, Any]:
    canonical = await _resolve_repository(repository)
    metadata = await _repository_metadata(canonical)
    target_ref = ref or str(metadata.get("default_branch") or "main")
    tree, partial = await _contents_tree(canonical, target_ref)
    blobs = [item for item in tree if item.get("type") == "blob"]
    blobs.sort(key=lambda item: (-_score_path(str(item.get("path") or "")), str(item.get("path") or "")))
    selected_paths = [str(item["path"]) for item in blobs[:max(4, min(max_files, 30))]]
    files = []
    for path in selected_paths:
        try:
            files.append(await _read_file(canonical, path, target_ref))
        except Exception as error:
            files.append({"path": path, "error": str(error)})
    commits = await _recent_commits(canonical, max(0, min(commit_limit, 20))) if commit_limit else []
    return {
        "repository": metadata, "ref": target_ref, "tree": tree, "tree_count": len(tree), "tree_is_partial": partial,
        "selected_files": selected_paths, "files": files, "recent_commits": commits,
        "access": "private-authenticated" if metadata.get("private") else "public",
        "analysis_notes": [
            "Repository identity was resolved from GitHub.",
            "Repository structure was collected through the Contents API.",
            "The low-level Git Trees endpoint is intentionally avoided for GitHub App compatibility.",
            "Files were prioritized by documentation, configuration, architecture, and application entry-point relevance.",
        ],
    }
