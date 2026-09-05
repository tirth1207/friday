from core.runtime.permissions import validate_workspace_path


async def write_file(path: str, content: str) -> str:
    """Write content to a file safely within workspace limits."""
    target_path = validate_workspace_path(path)

    # Ensure parent directories exist
    target_path.parent.mkdir(parents=True, exist_ok=True)

    target_path.write_text(content, encoding="utf-8")
    return f"Successfully wrote {len(content)} characters to {path}"
