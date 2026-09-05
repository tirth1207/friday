from core.runtime.permissions import get_workspace_root, validate_workspace_path


async def search_files(query: str, path: str = ".") -> list[str]:
    """
    Search the filesystem recursively for files matching query in name or content.
    Returns relative paths.
    """
    root = validate_workspace_path(path)
    workspace_root = get_workspace_root()

    if not root.exists():
        raise FileNotFoundError(f"Directory does not exist: {path}")

    results = []
    query_lower = query.lower()

    ignored = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".next",
        "dist",
        "build",
        ".pytest_cache",
    }

    for item in root.rglob("*"):
        if any(part in ignored for part in item.parts):
            continue

        if not item.is_file():
            continue

        # Match filename
        matches_name = query_lower in item.name.lower()
        matches_content = False

        if not matches_name and item.stat().st_size < 500_000:
            try:
                content = item.read_text(encoding="utf-8", errors="ignore")
                if query_lower in content.lower():
                    matches_content = True
            except Exception:
                pass

        if matches_name or matches_content:
            try:
                rel_path = str(item.relative_to(workspace_root))
            except ValueError:
                rel_path = str(item)
            results.append(rel_path)

        if len(results) >= 100:
            break

    return results
