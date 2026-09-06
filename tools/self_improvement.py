"""Safe introspection tools for FRIDAY's own codebase."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.runtime.permissions import get_workspace_root, validate_workspace_path

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", ".next", "dist", "build",
    "__pycache__", "coverage", ".pytest_cache",
}
SENSITIVE_NAMES = {".env", ".env.local", "friday_memory.db"}
IMPORTANT_FILES = {
    "core/main.py", "core/orchestrator.py", "core/orchestrator_structured.py",
    "core/events.py", "core/agents/runtime.py", "core/agents/specialized.py",
    "core/runtime/executor.py", "core/runtime/registry.py", "core/runtime/permissions.py",
    "core/memory/context.py", "providers/nvidia/client.py", "providers/nvidia/config.py",
    "tools/__init__.py", "tools/github/repository_agent.py", "requirements.txt",
    ".env.example",
}


def _safe_relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


async def self_inspect() -> dict[str, Any]:
    """Build a safe map of FRIDAY's source, tests, configuration, and Git metadata files."""
    root = get_workspace_root()
    if not root.exists():
        raise RuntimeError(f"FRIDAY workspace does not exist: {root}")

    files: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = _safe_relative(path, root)
        parts = relative.split("/")
        if any(part in SKIP_DIRS for part in parts):
            continue
        if path.name.lower() in SENSITIVE_NAMES:
            continue
        if path.suffix.lower() in {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".toml", ".yml", ".yaml", ".txt"}:
            files.append(relative)

    files.sort()
    important = [path for path in files if path.lower() in {item.lower() for item in IMPORTANT_FILES}]
    return {
        "workspace": str(root),
        "file_count": len(files),
        "files": files[:5000],
        "important_files": important,
        "policy": "Read-only introspection. No secrets are returned and no files are modified.",
    }


async def self_read_file(path: str) -> dict[str, Any]:
    """Read a non-sensitive text file from FRIDAY's own workspace for self-diagnosis."""
    target = validate_workspace_path(path)
    if target.name.lower() in SENSITIVE_NAMES:
        raise PermissionError(f"Self-inspection cannot read sensitive file: {path}")
    if not target.is_file():
        raise FileNotFoundError(path)
    content = target.read_text(encoding="utf-8")
    if len(content) > 150_000:
        content = content[:150_000] + "\n\n[OUTPUT TRUNCATED]"
    return {"path": str(target), "content": content}
