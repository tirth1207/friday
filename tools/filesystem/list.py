from typing import Any
from core.runtime.permissions import get_workspace_root, validate_workspace_path


async def list_directory(path: str = ".") -> list[dict[str, Any]]:
    """List files and directories in path with basic metadata."""
    target_path = validate_workspace_path(path)
    workspace = get_workspace_root()

    if not target_path.exists():
        raise FileNotFoundError(f"Directory does not exist: {path}")

    if not target_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    items = []
    for item in target_path.iterdir():
        if item.name in {".git", "__pycache__", ".venv", "node_modules"}:
            continue

        try:
            rel_path = str(item.relative_to(workspace))
        except ValueError:
            rel_path = item.name

        items.append({
            "name": item.name,
            "path": rel_path,
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None,
        })

    return items
