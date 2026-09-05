from core.runtime.permissions import validate_workspace_path


async def file_exists(path: str) -> bool:
    """Return whether path exists inside the workspace."""
    try:
        target_path = validate_workspace_path(path)
        return target_path.exists()
    except Exception:
        return False
