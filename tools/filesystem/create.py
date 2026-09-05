from core.runtime.permissions import validate_workspace_path


async def create_file(path: str, content: str = "", overwrite: bool = False) -> str:
    """Create a new file with content. Fails if file exists unless overwrite is True."""
    target_path = validate_workspace_path(path)

    if target_path.exists() and not overwrite:
        raise FileExistsError(f"File already exists at {path}. Set overwrite=True to replace it.")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return f"Successfully created file {path}"
